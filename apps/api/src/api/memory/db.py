"""Memory database layer — memories + chat history, with pgvector search.

Reuses the shared asyncpg pool from api.db. Embeddings are stored in a
VECTOR(EMBED_DIM) column; asyncpg sends them as a '[...]' string literal cast
to ::vector. Retrieval is cosine distance (<=>) ascending, scoped per email.
"""
from __future__ import annotations

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
          id         UUID PRIMARY KEY,
          email      TEXT NOT NULL REFERENCES profiles(email),
          content    TEXT NOT NULL,
          embedding  VECTOR({config.EMBED_DIM}),
          source     TEXT DEFAULT 'chat',
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _execute("CREATE INDEX IF NOT EXISTS idx_memories_email ON memories (email)")
    # HNSW cosine index for fast approximate nearest-neighbour search.
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
    # Existing DBs created before meta: add without wiping chat history.
    await _execute(
        "ALTER TABLE memory_chat_history ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'"
    )


# ── Memories ──────────────────────────────────────────────


async def insert_memory(
    id: str, email: str, content: str, embedding: list[float], source: str = "chat"
) -> dict:
    await _execute(
        """
        INSERT INTO memories (id, email, content, embedding, source)
        VALUES ($1, $2, $3, $4::vector, $5)
        """,
        id, email, content, _vec_literal(embedding), source,
    )
    return {"id": id, "content": content, "source": source}


async def list_memories(email: str) -> list[dict]:
    rows = await _fetch(
        """
        SELECT id, content, source, created_at
        FROM memories WHERE email = $1
        ORDER BY created_at DESC
        """,
        email,
    )
    return [
        {
            "id": str(r["id"]), "content": r["content"],
            "source": r["source"], "createdAt": r["created_at"],
        }
        for r in rows
    ]


async def delete_memory(email: str, id: str) -> bool:
    result = await _execute("DELETE FROM memories WHERE email = $1 AND id = $2", email, id)
    return result.endswith(" 1")


async def search_memories(email: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Cosine-nearest memories for this user. similarity = 1 - cosine distance."""
    rows = await _fetch(
        """
        SELECT id, content, source, created_at,
               1 - (embedding <=> $2::vector) AS similarity
        FROM memories
        WHERE email = $1
        ORDER BY embedding <=> $2::vector
        LIMIT $3
        """,
        email, _vec_literal(query_embedding), top_k,
    )
    return [
        {
            "id": str(r["id"]), "content": r["content"], "source": r["source"],
            "createdAt": r["created_at"], "similarity": float(r["similarity"]),
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
