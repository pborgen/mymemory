"""Memory database layer — memories + chat history, with pgvector search.

Reuses the shared asyncpg pool from api.db. Embeddings are stored in a
VECTOR(EMBED_DIM) column; asyncpg sends them as a '[...]' string literal cast
to ::vector. Retrieval is cosine distance (<=>) ascending, scoped per email.

Governance (FinServ demo): pii_tags / sensitivity on memories, soft-delete via
deleted_at, and an append-only memory_audit_log.

Pipeline lineage (data-eng demo): source_uri, ingested_at, pipeline_version.
"""
from __future__ import annotations

import uuid

import asyncpg

from .. import config
from .. import db as _db


async def _execute(query: str, *args) -> str:
    return await _db.pool().execute(query, *args)


async def _fetch(query: str, *args) -> list[asyncpg.Record]:
    return await _db.pool().fetch(query, *args)


async def _fetchrow(query: str, *args) -> asyncpg.Record | None:
    return await _db.pool().fetchrow(query, *args)


def _vec_literal(embedding: list[float]) -> str:
    """pgvector accepts a textual '[a,b,c]' literal cast to ::vector."""
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


async def ensure_memory_tables() -> None:
    # CREATE EXTENSION vector is done in api.db.ensure_tables() before this runs.
    await _execute(
        f"""
        CREATE TABLE IF NOT EXISTS memories (
          id          UUID PRIMARY KEY,
          email       TEXT NOT NULL REFERENCES profiles(email),
          content     TEXT NOT NULL,
          embedding   VECTOR({config.EMBED_DIM}),
          source      TEXT DEFAULT 'chat',
          pii_tags    JSONB DEFAULT '[]',
          sensitivity TEXT NOT NULL DEFAULT 'normal',
          deleted_at  TIMESTAMPTZ,
          source_uri  TEXT NOT NULL DEFAULT '',
          ingested_at TIMESTAMPTZ,
          pipeline_version TEXT NOT NULL DEFAULT '',
          created_at  TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS pii_tags JSONB DEFAULT '[]'"
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS sensitivity TEXT NOT NULL DEFAULT 'normal'"
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS source_uri TEXT NOT NULL DEFAULT ''"
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ"
    )
    await _execute(
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS pipeline_version TEXT NOT NULL DEFAULT ''"
    )
    await _execute("CREATE INDEX IF NOT EXISTS idx_memories_email ON memories (email)")
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_source_uri ON memories (source_uri)"
    )
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_embedding "
        "ON memories USING hnsw (embedding vector_cosine_ops)"
    )

    await _execute(
        """
        CREATE TABLE IF NOT EXISTS memory_chat_history (
          id         UUID PRIMARY KEY,
          email      TEXT NOT NULL REFERENCES profiles(email),
          session_id TEXT NOT NULL,
          role       TEXT NOT NULL,
          content    TEXT NOT NULL,
          sources    JSONB DEFAULT '[]',
          meta       JSONB DEFAULT '{}',
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute(
        "ALTER TABLE memory_chat_history ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'"
    )

    await _execute(
        """
        CREATE TABLE IF NOT EXISTS memory_audit_log (
          id          UUID PRIMARY KEY,
          email       TEXT NOT NULL,
          action      TEXT NOT NULL,
          memory_id   UUID,
          request_id  TEXT DEFAULT '',
          detail      JSONB DEFAULT '{}',
          created_at  TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_audit_email_created "
        "ON memory_audit_log (email, created_at DESC)"
    )

    await _execute(
        """
        CREATE TABLE IF NOT EXISTS memory_entities (
          id         UUID PRIMARY KEY,
          email      TEXT NOT NULL REFERENCES profiles(email),
          name       TEXT NOT NULL,
          key        TEXT NOT NULL,
          type       TEXT NOT NULL DEFAULT 'other',
          created_at TIMESTAMPTZ DEFAULT now(),
          UNIQUE (email, key)
        )
        """
    )
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_entities_email ON memory_entities (email)"
    )
    await _execute(
        """
        CREATE TABLE IF NOT EXISTS memory_entity_links (
          memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
          entity_id UUID NOT NULL REFERENCES memory_entities(id) ON DELETE CASCADE,
          PRIMARY KEY (memory_id, entity_id)
        )
        """
    )
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_entity_links_entity "
        "ON memory_entity_links (entity_id)"
    )

    await _execute(
        """
        CREATE TABLE IF NOT EXISTS memory_reminders (
          id         UUID PRIMARY KEY,
          email      TEXT NOT NULL REFERENCES profiles(email),
          content    TEXT NOT NULL,
          due_at     TIMESTAMPTZ,
          done_at    TIMESTAMPTZ,
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_reminders_email "
        "ON memory_reminders (email, created_at DESC)"
    )


def _memory_row(r: asyncpg.Record, *, include_similarity: bool = False) -> dict:
    out = {
        "id": str(r["id"]),
        "content": r["content"],
        "source": r["source"],
        "piiTags": r["pii_tags"] or [],
        "sensitivity": r["sensitivity"] or "normal",
        "sourceUri": r["source_uri"] or "",
        "ingestedAt": r["ingested_at"],
        "pipelineVersion": r["pipeline_version"] or "",
        "createdAt": r["created_at"],
        "entities": [],
    }
    if include_similarity:
        out["similarity"] = float(r["similarity"])
    return out


def _entity_row(r: asyncpg.Record) -> dict:
    out = {
        "id": str(r["id"]),
        "name": r["name"],
        "key": r["key"],
        "type": r["type"],
        "createdAt": r["created_at"],
    }
    if "memory_count" in r:
        out["memoryCount"] = int(r["memory_count"])
    return out


_MEMORY_COLS = (
    "id, content, source, pii_tags, sensitivity, "
    "source_uri, ingested_at, pipeline_version, created_at"
)


# ── Memories ──────────────────────────────────────────────


async def insert_memory(
    id: str,
    email: str,
    content: str,
    embedding: list[float],
    source: str = "chat",
    *,
    pii_tags: list[str] | None = None,
    sensitivity: str = "normal",
    source_uri: str = "",
    pipeline_version: str = "",
) -> dict:
    tags = pii_tags or []
    uri = source_uri or ""
    version = pipeline_version or ""
    await _execute(
        """
        INSERT INTO memories
          (id, email, content, embedding, source, pii_tags, sensitivity,
           source_uri, ingested_at, pipeline_version)
        VALUES ($1, $2, $3, $4::vector, $5, $6::jsonb, $7, $8,
                CASE WHEN $8 <> '' OR $9 <> '' THEN now() ELSE NULL END, $9)
        """,
        id,
        email,
        content,
        _vec_literal(embedding),
        source,
        tags,
        sensitivity,
        uri,
        version,
    )
    return {
        "id": id,
        "content": content,
        "source": source,
        "piiTags": tags,
        "sensitivity": sensitivity,
        "sourceUri": uri,
        "pipelineVersion": version,
        "entities": [],
    }


async def list_memories(email: str, *, entity_key: str = "") -> list[dict]:
    if entity_key:
        rows = await _fetch(
            """
            SELECT m.id, m.content, m.source, m.pii_tags, m.sensitivity,
                   m.source_uri, m.ingested_at, m.pipeline_version, m.created_at
            FROM memories m
            JOIN memory_entity_links l ON l.memory_id = m.id
            JOIN memory_entities e ON e.id = l.entity_id
            WHERE m.email = $1 AND m.deleted_at IS NULL
              AND e.email = $1 AND e.key = $2
            ORDER BY m.created_at DESC
            """,
            email,
            entity_key,
        )
    else:
        rows = await _fetch(
            f"""
            SELECT {_MEMORY_COLS}
            FROM memories
            WHERE email = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            """,
            email,
        )
    memories = [_memory_row(r) for r in rows]
    await _attach_entities(email, memories)
    return memories


async def upsert_entity(
    id: str,
    email: str,
    *,
    name: str,
    key: str,
    entity_type: str = "other",
) -> dict:
    row = await _fetchrow(
        """
        INSERT INTO memory_entities (id, email, name, key, type)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (email, key) DO UPDATE
          SET name = EXCLUDED.name,
              type = EXCLUDED.type
        RETURNING id, name, key, type, created_at
        """,
        id,
        email,
        name,
        key,
        entity_type,
    )
    assert row is not None
    return _entity_row(row)


async def link_memory_entity(memory_id: str, entity_id: str) -> None:
    await _execute(
        """
        INSERT INTO memory_entity_links (memory_id, entity_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
        """,
        memory_id,
        entity_id,
    )


async def memory_owned(email: str, memory_id: str) -> bool:
    row = await _fetchrow(
        """
        SELECT 1 FROM memories
        WHERE email = $1 AND id = $2 AND deleted_at IS NULL
        """,
        email,
        memory_id,
    )
    return row is not None


async def unlink_memory_entity(email: str, memory_id: str, entity_id: str) -> bool:
    """Remove a link; delete the entity if it has no remaining live memories."""
    result = await _execute(
        """
        DELETE FROM memory_entity_links l
        USING memories m, memory_entities e
        WHERE l.memory_id = m.id AND l.entity_id = e.id
          AND m.email = $1 AND m.id = $2 AND e.email = $1 AND e.id = $3
        """,
        email,
        memory_id,
        entity_id,
    )
    # asyncpg returns e.g. "DELETE 1"
    if not result.endswith("1"):
        return False
    await _execute(
        """
        DELETE FROM memory_entities e
        WHERE e.email = $1 AND e.id = $2
          AND NOT EXISTS (
            SELECT 1 FROM memory_entity_links l
            JOIN memories m ON m.id = l.memory_id
            WHERE l.entity_id = e.id AND m.deleted_at IS NULL
          )
        """,
        email,
        entity_id,
    )
    return True


async def entities_for_memory(email: str, memory_id: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT e.id, e.name, e.key, e.type, e.created_at
        FROM memory_entity_links l
        JOIN memory_entities e ON e.id = l.entity_id
        JOIN memories m ON m.id = l.memory_id
        WHERE m.email = $1 AND m.id = $2 AND m.deleted_at IS NULL AND e.email = $1
        ORDER BY e.name ASC
        """,
        email,
        memory_id,
    )
    return [_entity_row(r) for r in rows]


async def rename_entity(
    email: str, entity_id: str, *, name: str, key: str, entity_type: str | None = None
) -> dict | None:
    """Rename an entity. If key collides with another, merge links into that one."""
    existing = await _fetchrow(
        """
        SELECT id, name, key, type, created_at FROM memory_entities
        WHERE email = $1 AND id = $2
        """,
        email,
        entity_id,
    )
    if not existing:
        return None

    conflict = await _fetchrow(
        """
        SELECT id FROM memory_entities
        WHERE email = $1 AND key = $2 AND id <> $3
        """,
        email,
        key,
        entity_id,
    )
    if conflict:
        # Move all links to the conflict target, drop the old entity.
        await _execute(
            """
            INSERT INTO memory_entity_links (memory_id, entity_id)
            SELECT memory_id, $1 FROM memory_entity_links WHERE entity_id = $2
            ON CONFLICT DO NOTHING
            """,
            str(conflict["id"]),
            entity_id,
        )
        await _execute(
            "DELETE FROM memory_entity_links WHERE entity_id = $1", entity_id
        )
        await _execute(
            "DELETE FROM memory_entities WHERE email = $1 AND id = $2", email, entity_id
        )
        row = await _fetchrow(
            """
            UPDATE memory_entities
               SET name = $3, type = COALESCE($4, type)
             WHERE email = $1 AND id = $2
         RETURNING id, name, key, type, created_at
            """,
            email,
            str(conflict["id"]),
            name,
            entity_type,
        )
        return _entity_row(row) if row else None

    row = await _fetchrow(
        """
        UPDATE memory_entities
           SET name = $3, key = $4, type = COALESCE($5, type)
         WHERE email = $1 AND id = $2
     RETURNING id, name, key, type, created_at
        """,
        email,
        entity_id,
        name,
        key,
        entity_type,
    )
    return _entity_row(row) if row else None


async def list_entities(email: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT e.id, e.name, e.key, e.type, e.created_at,
               COUNT(m.id)::int AS memory_count
        FROM memory_entities e
        LEFT JOIN memory_entity_links l ON l.entity_id = e.id
        LEFT JOIN memories m
          ON m.id = l.memory_id AND m.email = e.email AND m.deleted_at IS NULL
        WHERE e.email = $1
        GROUP BY e.id, e.name, e.key, e.type, e.created_at
        HAVING COUNT(m.id) > 0
        ORDER BY COUNT(m.id) DESC, e.name ASC
        """,
        email,
    )
    return [_entity_row(r) for r in rows]


async def list_memory_ids_without_entities(
    email: str, *, limit: int = 25
) -> list[tuple[str, str]]:
    rows = await _fetch(
        """
        SELECT m.id, m.content
        FROM memories m
        LEFT JOIN memory_entity_links l ON l.memory_id = m.id
        WHERE m.email = $1 AND m.deleted_at IS NULL AND l.memory_id IS NULL
        ORDER BY m.created_at DESC
        LIMIT $2
        """,
        email,
        limit,
    )
    return [(str(r["id"]), r["content"]) for r in rows]


async def _attach_entities(email: str, memories: list[dict]) -> None:
    if not memories:
        return
    ids = [m["id"] for m in memories]
    rows = await _fetch(
        """
        SELECT l.memory_id, e.id, e.name, e.key, e.type, e.created_at
        FROM memory_entity_links l
        JOIN memory_entities e ON e.id = l.entity_id
        WHERE e.email = $1 AND l.memory_id = ANY($2::uuid[])
        ORDER BY e.name ASC
        """,
        email,
        ids,
    )
    by_mem: dict[str, list[dict]] = {mid: [] for mid in ids}
    for r in rows:
        by_mem[str(r["memory_id"])].append(_entity_row(r))
    for m in memories:
        m["entities"] = by_mem.get(m["id"], [])


async def list_memories_for_report(
    email: str,
    *,
    loan: str = "",
    tag: str = "",
    source_uri_prefix: str = "",
) -> list[dict]:
    """Warehouse-style filter for pipeline reporting (loan id / tag / lineage)."""
    rows = await _fetch(
        f"""
        SELECT {_MEMORY_COLS}
        FROM memories
        WHERE email = $1 AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        email,
    )
    out = [_memory_row(r) for r in rows]
    if loan:
        needle = loan.lower()
        out = [m for m in out if needle in (m["content"] or "").lower()]
    if tag:
        out = [m for m in out if tag in (m.get("piiTags") or [])]
    if source_uri_prefix:
        out = [
            m
            for m in out
            if (m.get("sourceUri") or "").startswith(source_uri_prefix)
        ]
    return out


async def delete_memory(email: str, id: str) -> bool:
    """Soft-delete: set deleted_at so audit/history can still reference the row."""
    result = await _execute(
        """
        UPDATE memories
           SET deleted_at = now()
         WHERE email = $1 AND id = $2 AND deleted_at IS NULL
        """,
        email,
        id,
    )
    return result.endswith(" 1")


async def latest_memory(email: str) -> dict | None:
    """Most recently created non-deleted memory for this user, or None."""
    row = await _fetchrow(
        f"""
        SELECT {_MEMORY_COLS}
        FROM memories
        WHERE email = $1 AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        email,
    )
    return _memory_row(row) if row else None


async def update_memory_content(
    email: str,
    memory_id: str,
    content: str,
    embedding: list[float],
) -> dict | None:
    """Replace content + embedding for a live memory; return the updated row."""
    row = await _fetchrow(
        f"""
        UPDATE memories
           SET content = $3,
               embedding = $4::vector
         WHERE email = $1 AND id = $2 AND deleted_at IS NULL
     RETURNING {_MEMORY_COLS}
        """,
        email,
        memory_id,
        content,
        _vec_literal(embedding),
    )
    return _memory_row(row) if row else None


async def soft_delete_all_memories(email: str) -> int:
    """Soft-delete every live memory for this user. Returns rows affected."""
    result = await _execute(
        """
        UPDATE memories
           SET deleted_at = now()
         WHERE email = $1 AND deleted_at IS NULL
        """,
        email,
    )
    # asyncpg: "UPDATE <n>"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


def _reminder_row(r: asyncpg.Record) -> dict:
    return {
        "id": str(r["id"]),
        "content": r["content"],
        "dueAt": r["due_at"],
        "doneAt": r["done_at"],
        "createdAt": r["created_at"],
    }


async def insert_reminder(
    id: str,
    email: str,
    content: str,
    *,
    due_at=None,
) -> dict:
    row = await _fetchrow(
        """
        INSERT INTO memory_reminders (id, email, content, due_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, content, due_at, done_at, created_at
        """,
        id,
        email,
        content,
        due_at,
    )
    return _reminder_row(row)


async def list_reminders(email: str, *, include_done: bool = False) -> list[dict]:
    if include_done:
        rows = await _fetch(
            """
            SELECT id, content, due_at, done_at, created_at
            FROM memory_reminders
            WHERE email = $1
            ORDER BY created_at DESC
            LIMIT 100
            """,
            email,
        )
    else:
        rows = await _fetch(
            """
            SELECT id, content, due_at, done_at, created_at
            FROM memory_reminders
            WHERE email = $1 AND done_at IS NULL
            ORDER BY created_at DESC
            LIMIT 100
            """,
            email,
        )
    return [_reminder_row(r) for r in rows]


async def complete_reminder(email: str, reminder_id: str) -> bool:
    result = await _execute(
        """
        UPDATE memory_reminders
           SET done_at = now()
         WHERE email = $1 AND id = $2 AND done_at IS NULL
        """,
        email,
        reminder_id,
    )
    return result.endswith(" 1")


async def delete_reminder(email: str, reminder_id: str) -> bool:
    result = await _execute(
        """
        DELETE FROM memory_reminders
         WHERE email = $1 AND id = $2
        """,
        email,
        reminder_id,
    )
    return result.endswith(" 1")


async def search_memories(email: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Cosine-nearest memories for this user. similarity = 1 - cosine distance."""
    rows = await _fetch(
        f"""
        SELECT {_MEMORY_COLS},
               1 - (embedding <=> $2::vector) AS similarity
        FROM memories
        WHERE email = $1 AND deleted_at IS NULL
        ORDER BY embedding <=> $2::vector
        LIMIT $3
        """,
        email, _vec_literal(query_embedding), top_k,
    )
    return [_memory_row(r, include_similarity=True) for r in rows]


# ── Audit log ─────────────────────────────────────────────


async def write_audit(
    email: str,
    action: str,
    *,
    memory_id: str | None = None,
    request_id: str = "",
    detail: dict | None = None,
) -> None:
    await _execute(
        """
        INSERT INTO memory_audit_log (id, email, action, memory_id, request_id, detail)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        """,
        str(uuid.uuid4()),
        email,
        action,
        uuid.UUID(memory_id) if memory_id else None,
        request_id or "",
        detail or {},
    )


async def list_audit(email: str, limit: int = 50) -> list[dict]:
    rows = await _fetch(
        """
        SELECT id, email, action, memory_id, request_id, detail, created_at
        FROM memory_audit_log
        WHERE email = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        email,
        limit,
    )
    return [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "action": r["action"],
            "memoryId": str(r["memory_id"]) if r["memory_id"] else None,
            "requestId": r["request_id"] or "",
            "detail": r["detail"] or {},
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


# ── Chat history ──────────────────────────────────────────


async def save_chat_message(
    id: str,
    email: str,
    session_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    meta: dict | None = None,
) -> None:
    await _execute(
        """
        INSERT INTO memory_chat_history
          (id, email, session_id, role, content, sources, meta)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
        """,
        id, email, session_id, role, content, sources or [], meta or {},
    )


async def get_chat_history(email: str, session_id: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT role, content, sources, meta, created_at
        FROM memory_chat_history
        WHERE email = $1 AND session_id = $2
        ORDER BY created_at ASC
        """,
        email, session_id,
    )
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "sources": r["sources"] or [],
            "meta": r["meta"] or {},
            "createdAt": r["created_at"],
        }
        for r in rows
    ]
