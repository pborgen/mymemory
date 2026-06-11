"""PostgreSQL access layer — async pool + helpers.

Uses asyncpg with positional ($1) parameters and raw SQL (no ORM). Schema is
created on startup in ensure_tables(); the memory/chat tables live in
memory/db.py (ensure_memory_tables). Email is the primary user identifier.
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg

from . import config

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    # Decode/encode JSONB transparently to/from Python objects.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not config.POSTGRES_URL:
            raise RuntimeError("POSTGRES_URL is not set")
        _pool = await asyncpg.create_pool(config.POSTGRES_URL, init=_init_conn)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized; call init_pool() first")
    return _pool


async def _fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    return await pool().fetch(query, *args)


async def _fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    return await pool().fetchrow(query, *args)


async def _execute(query: str, *args: Any) -> str:
    return await pool().execute(query, *args)


# ── Schema ────────────────────────────────────────────────


async def ensure_tables() -> None:
    # pgvector must be enabled before any VECTOR column is created
    # (memory/db.py declares the embedding column).
    await _execute("CREATE EXTENSION IF NOT EXISTS vector")

    await _execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
          email      TEXT PRIMARY KEY,
          full_name  TEXT DEFAULT '',
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


# ── Profile helpers ───────────────────────────────────────


async def ensure_profile(email: str) -> None:
    """Create a bare profile row for this email if one doesn't exist."""
    await _execute(
        "INSERT INTO profiles (email) VALUES ($1) ON CONFLICT (email) DO NOTHING",
        email,
    )


async def ensure_google_user(email: str, full_name: str | None = None) -> None:
    await _execute(
        """
        INSERT INTO profiles (email, full_name)
        VALUES ($1, $2)
        ON CONFLICT (email) DO UPDATE
          SET full_name = COALESCE(NULLIF(EXCLUDED.full_name, ''), profiles.full_name)
        """,
        email,
        full_name or "",
    )


async def get_profile(email: str) -> dict | None:
    row = await _fetchrow(
        "SELECT email, full_name, created_at FROM profiles WHERE email = $1", email
    )
    if not row:
        return None
    return {
        "email": row["email"],
        "fullName": row["full_name"],
        "createdAt": row["created_at"],
    }
