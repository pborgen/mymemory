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
          role       TEXT NOT NULL DEFAULT 'user',
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    # Existing DBs created before roles: add column without wiping profiles.
    await _execute(
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'"
    )


# ── Profile helpers ───────────────────────────────────────


async def ensure_profile(email: str) -> None:
    """Create a bare profile row for this email if one doesn't exist."""
    await _execute(
        "INSERT INTO profiles (email) VALUES ($1) ON CONFLICT (email) DO NOTHING",
        email.lower(),
    )


async def ensure_google_user(email: str, full_name: str | None = None) -> None:
    await _execute(
        """
        INSERT INTO profiles (email, full_name)
        VALUES ($1, $2)
        ON CONFLICT (email) DO UPDATE
          SET full_name = COALESCE(NULLIF(EXCLUDED.full_name, ''), profiles.full_name)
        """,
        email.lower(),
        full_name or "",
    )


async def get_profile(email: str) -> dict | None:
    row = await _fetchrow(
        "SELECT email, full_name, role, created_at FROM profiles WHERE email = $1",
        email.lower(),
    )
    if not row:
        return None
    return {
        "email": row["email"],
        "fullName": row["full_name"],
        "role": row["role"] or "user",
        "createdAt": row["created_at"],
    }


async def is_admin(email: str) -> bool:
    row = await _fetchrow(
        "SELECT role FROM profiles WHERE email = $1", email.lower()
    )
    return bool(row and row["role"] == "admin")


async def count_admins() -> int:
    return int(
        await pool().fetchval("SELECT COUNT(*) FROM profiles WHERE role = 'admin'") or 0
    )


async def set_role(email: str, role: str) -> dict | None:
    """Set profile role to 'user' or 'admin'. Ensures the profile exists."""
    if role not in ("user", "admin"):
        raise ValueError("role must be 'user' or 'admin'")
    email = email.lower().strip()
    if not email or "@" not in email:
        raise ValueError("invalid email")
    await ensure_profile(email)
    await _execute(
        "UPDATE profiles SET role = $2 WHERE email = $1",
        email,
        role,
    )
    return await get_profile(email)


async def list_admins() -> list[dict]:
    rows = await _fetch(
        """
        SELECT email, full_name, role, created_at
        FROM profiles
        WHERE role = 'admin'
        ORDER BY email ASC
        """
    )
    return [
        {
            "email": r["email"],
            "fullName": r["full_name"],
            "role": r["role"],
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


async def seed_super_admin() -> None:
    """Ensure SUPER_ADMIN_EMAIL exists and has role=admin (env-defined root admin)."""
    email = config.SUPER_ADMIN_EMAIL
    if not email:
        return
    await set_role(email, "admin")
