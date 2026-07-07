"""Prompt database layer — global, versioned prompts (no per-user scoping).

Reuses the shared asyncpg pool from api.db. Two tables: `prompts` (one row per
key, pointing at its active version) and `prompt_versions` (append-only history).
Editing inserts a new version and re-points active; rollback re-points active to
an existing version; reset inserts a new version from the registry default.

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
          created_at  TIMESTAMPTZ DEFAULT now(),
          created_by  TEXT DEFAULT ''
        )
        """
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
            INSERT INTO prompt_versions (id, prompt_key, version, content, created_by)
            VALUES ($1, $2, 1, $3, 'system')
            """,
            version_id, d["key"], d["content"],
        )


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
    row = await _fetchrow(
        """
        SELECT v.content
        FROM prompts p
        JOIN prompt_versions v ON v.id = p.active_version_id
        WHERE p.key = $1
        """,
        key,
    )
    return row["content"] if row else None


async def list_versions(key: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT v.id, v.version, v.content, v.created_at, v.created_by,
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
            "createdAt": r["created_at"],
            "createdBy": r["created_by"],
            "isActive": r["is_active"],
        }
        for r in rows
    ]


async def save_version(key: str, content: str, by: str) -> dict | None:
    """Append a new version and make it active. Returns the updated prompt."""
    if not await _fetchrow("SELECT 1 FROM prompts WHERE key = $1", key):
        return None
    next_version = await _db.pool().fetchval(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM prompt_versions WHERE prompt_key = $1",
        key,
    )
    version_id = str(uuid.uuid4())
    await _execute(
        """
        INSERT INTO prompt_versions (id, prompt_key, version, content, created_by)
        VALUES ($1, $2, $3, $4, $5)
        """,
        version_id, key, next_version, content, by,
    )
    await _execute(
        "UPDATE prompts SET active_version_id = $2, updated_at = now() WHERE key = $1",
        key, version_id,
    )
    return await get_prompt(key)


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
    return await save_version(key, default["content"], by)
