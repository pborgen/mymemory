"""Prompt database layer — global, versioned prompts (no per-user scoping).

Reuses the shared asyncpg pool from api.db. Two tables: `prompts` (one row per
key, pointing at its active version) and `prompt_versions` (append-only history).
Editing inserts a new version and re-points active (each save stores a
`change_note` rationale); rollback re-points active to an existing version;
reset inserts a new version from the registry default.

Helpers return camelCase dicts, matching the convention in api.db / memory.db.
"""
from __future__ import annotations

import uuid

import asyncpg

from .. import db as _db
from .defaults import DEFAULTS, DEFAULTS_BY_KEY


async def _execute(query: str, *args) -> str:
    return await _db.pool().execute(query, *args)


async def _fetch(query: str, *args) -> list[asyncpg.Record]:
    return await _db.pool().fetch(query, *args)


async def _fetchrow(query: str, *args) -> asyncpg.Record | None:
    return await _db.pool().fetchrow(query, *args)


async def ensure_prompt_tables() -> None:
    await _execute(
        """
        CREATE TABLE IF NOT EXISTS prompts (
          key               TEXT PRIMARY KEY,
          name              TEXT NOT NULL,
          description       TEXT DEFAULT '',
          variables         JSONB DEFAULT '[]',
          active_version_id UUID,
          created_at        TIMESTAMPTZ DEFAULT now(),
          updated_at        TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute(
        """
        CREATE TABLE IF NOT EXISTS prompt_versions (
          id          UUID PRIMARY KEY,
          prompt_key  TEXT NOT NULL REFERENCES prompts(key),
          version     INT  NOT NULL,
          content     TEXT NOT NULL,
          change_note TEXT NOT NULL DEFAULT '',
          created_at  TIMESTAMPTZ DEFAULT now(),
          created_by  TEXT DEFAULT ''
        )
        """
    )
    # Existing DBs created before change_note: add the column without wiping history.
    await _execute(
        "ALTER TABLE prompt_versions ADD COLUMN IF NOT EXISTS change_note TEXT NOT NULL DEFAULT ''"
    )
    await _execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_versions "
        "ON prompt_versions (prompt_key, version)"
    )


async def seed_prompts() -> None:
    """Insert any missing prompt as version 1. Idempotent; never overwrites edits."""
    for d in DEFAULTS:
        exists = await _fetchrow("SELECT 1 FROM prompts WHERE key = $1", d["key"])
        if exists:
            # Keep metadata fresh (name/description/variables) without touching content.
            await _execute(
                """
                UPDATE prompts
                   SET name = $2, description = $3, variables = $4::jsonb
                 WHERE key = $1
                """,
                d["key"], d["name"], d["description"], d["variables"],
            )
            continue
        version_id = str(uuid.uuid4())
        await _execute(
            """
            INSERT INTO prompts (key, name, description, variables, active_version_id)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            d["key"], d["name"], d["description"], d["variables"], version_id,
        )
        await _execute(
            """
            INSERT INTO prompt_versions
              (id, prompt_key, version, content, change_note, created_by)
            VALUES ($1, $2, 1, $3, $4, 'system')
            """,
            version_id, d["key"], d["content"], "Initial seed",
        )
    await _ensure_remember_gate_classifier()


async def _ensure_remember_gate_classifier() -> None:
    """Activate the 3-way store|recall|chat classifier if still on the old 2-way prompt.

    Does not overwrite custom edits that already include a chat action.
    """
    key = "memory.classifier"
    current = await get_active_resolved(key)
    if not current:
        return
    content = current["content"] or ""
    if '"chat"' in content and "durable" in content.lower():
        return
    new_content = DEFAULTS_BY_KEY[key]["content"]
    if content.strip() == new_content.strip():
        return
    await save_version(
        key,
        new_content,
        by="system",
        change_note="Remember-gate: only store durable facts; chat skips memory",
        activate=True,
    )
    from . import store as prompt_store

    await prompt_store.invalidate(key)


def _prompt_row(r: asyncpg.Record) -> dict:
    return {
        "key": r["key"],
        "name": r["name"],
        "description": r["description"],
        "variables": r["variables"] or [],
        "content": r["content"],
        "activeVersion": r["version"],
        "updatedAt": r["updated_at"],
    }


async def list_prompts() -> list[dict]:
    rows = await _fetch(
        """
        SELECT p.key, p.name, p.description, p.variables, p.updated_at,
               v.content, v.version
        FROM prompts p
        LEFT JOIN prompt_versions v ON v.id = p.active_version_id
        ORDER BY p.key ASC
        """
    )
    return [_prompt_row(r) for r in rows]


async def get_prompt(key: str) -> dict | None:
    row = await _fetchrow(
        """
        SELECT p.key, p.name, p.description, p.variables, p.updated_at,
               v.content, v.version
        FROM prompts p
        LEFT JOIN prompt_versions v ON v.id = p.active_version_id
        WHERE p.key = $1
        """,
        key,
    )
    return _prompt_row(row) if row else None


async def get_active_content(key: str) -> str | None:
    """Active content for a key, or None if the key is unknown."""
    resolved = await get_active_resolved(key)
    return resolved["content"] if resolved else None


async def get_active_resolved(key: str) -> dict | None:
    """Active version metadata + content for a key, or None if unknown.

    Used by the inference path so every chat turn can pin which prompt version
    ran (production debugging / prompt ops).
    """
    row = await _fetchrow(
        """
        SELECT v.id, v.version, v.content
        FROM prompts p
        JOIN prompt_versions v ON v.id = p.active_version_id
        WHERE p.key = $1
        """,
        key,
    )
    if not row:
        return None
    return {
        "versionId": str(row["id"]),
        "version": row["version"],
        "content": row["content"],
    }


async def list_versions(key: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT v.id, v.version, v.content, v.change_note, v.created_at, v.created_by,
               (v.id = p.active_version_id) AS is_active
        FROM prompt_versions v
        JOIN prompts p ON p.key = v.prompt_key
        WHERE v.prompt_key = $1
        ORDER BY v.version DESC
        """,
        key,
    )
    return [
        {
            "id": str(r["id"]),
            "version": r["version"],
            "content": r["content"],
            "changeNote": r["change_note"] or "",
            "createdAt": r["created_at"],
            "createdBy": r["created_by"],
            "isActive": r["is_active"],
        }
        for r in rows
    ]


async def save_version(
    key: str,
    content: str,
    by: str,
    change_note: str = "",
    *,
    activate: bool = True,
) -> dict | None:
    """Append a new version. If activate=True, make it the active pointer."""
    if not await _fetchrow("SELECT 1 FROM prompts WHERE key = $1", key):
        return None
    next_version = await _db.pool().fetchval(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM prompt_versions WHERE prompt_key = $1",
        key,
    )
    version_id = str(uuid.uuid4())
    await _execute(
        """
        INSERT INTO prompt_versions
          (id, prompt_key, version, content, change_note, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        version_id, key, next_version, content, change_note, by,
    )
    if activate:
        await _execute(
            "UPDATE prompts SET active_version_id = $2, updated_at = now() WHERE key = $1",
            key, version_id,
        )
    else:
        await _execute(
            "UPDATE prompts SET updated_at = now() WHERE key = $1",
            key,
        )
    return await get_prompt(key)


async def get_version(key: str, version_id: str) -> dict | None:
    row = await _fetchrow(
        """
        SELECT v.id, v.version, v.content, v.change_note, v.created_at, v.created_by,
               (v.id = p.active_version_id) AS is_active
        FROM prompt_versions v
        JOIN prompts p ON p.key = v.prompt_key
        WHERE v.prompt_key = $1 AND v.id = $2
        """,
        key,
        uuid.UUID(version_id),
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "version": row["version"],
        "content": row["content"],
        "changeNote": row["change_note"] or "",
        "createdAt": row["created_at"],
        "createdBy": row["created_by"],
        "isActive": row["is_active"],
    }


async def set_active(key: str, version_id: str) -> dict | None:
    """Roll back / forward by pointing active at an existing version of this key."""
    owned = await _fetchrow(
        "SELECT 1 FROM prompt_versions WHERE id = $1 AND prompt_key = $2",
        uuid.UUID(version_id), key,
    )
    if not owned:
        return None
    await _execute(
        "UPDATE prompts SET active_version_id = $2, updated_at = now() WHERE key = $1",
        key, version_id,
    )
    return await get_prompt(key)


async def reset_prompt(key: str, by: str) -> dict | None:
    """Append a new version whose content is the registry default, make it active."""
    default = DEFAULTS_BY_KEY.get(key)
    if not default:
        return None
    return await save_version(
        key,
        default["content"],
        by,
        change_note="Reset to registry default",
        activate=True,
    )
