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
    }
    if include_similarity:
        out["similarity"] = float(r["similarity"])
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
    }


async def list_memories(email: str) -> list[dict]:
    rows = await _fetch(
        f"""
        SELECT {_MEMORY_COLS}
        FROM memories
        WHERE email = $1 AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        email,
    )
    return [_memory_row(r) for r in rows]


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
