"""CI smoke test — schema + pgvector round-trip, no AWS/Bedrock required.

Exercises the real DB layer against a pgvector-enabled Postgres (a CI service
container). Embeddings are hand-made vectors passed straight to the DB helpers,
so this validates the schema, the VECTOR column, the HNSW index, the cosine
search, and per-user scoping without calling Titan or Claude.

Run:  POSTGRES_URL=... uv run python scripts/ci_smoke.py
"""
from __future__ import annotations

import asyncio
import sys

from api import config, db
from api.memory import db as mem_db

EMAIL_A = "a@ci.local"
EMAIL_B = "b@ci.local"


def _unit(idx: int) -> list[float]:
    """A deterministic one-hot 1024-d vector — distinct & orthogonal per idx."""
    v = [0.0] * config.EMBED_DIM
    v[idx % config.EMBED_DIM] = 1.0
    return v


async def main() -> int:
    await db.init_pool()
    await db.ensure_tables()
    await mem_db.ensure_memory_tables()

    await db.ensure_profile(EMAIL_A)
    await db.ensure_profile(EMAIL_B)

    # Insert three memories for A on distinct vectors, one for B.
    await mem_db.insert_memory("11111111-1111-1111-1111-111111111111", EMAIL_A, "A: plate 8XYZ123", _unit(0))
    await mem_db.insert_memory("22222222-2222-2222-2222-222222222222", EMAIL_A, "A: wifi hunter2", _unit(1))
    await mem_db.insert_memory("33333333-3333-3333-3333-333333333333", EMAIL_A, "A: dentist July 9", _unit(2))
    await mem_db.insert_memory("44444444-4444-4444-4444-444444444444", EMAIL_B, "B: parking B12", _unit(0))

    # 1. Cosine search returns the nearest vector for A (the one at idx 0).
    hits = await mem_db.search_memories(EMAIL_A, _unit(0), top_k=1)
    assert hits and hits[0]["content"] == "A: plate 8XYZ123", f"unexpected top hit: {hits}"
    assert hits[0]["similarity"] > 0.99, f"similarity too low: {hits[0]['similarity']}"

    # 2. Per-user scoping: B's identical idx-0 vector never leaks into A's results.
    a_contents = {m["content"] for m in await mem_db.list_memories(EMAIL_A)}
    assert a_contents == {"A: plate 8XYZ123", "A: wifi hunter2", "A: dentist July 9"}, a_contents
    b_contents = {m["content"] for m in await mem_db.list_memories(EMAIL_B)}
    assert b_contents == {"B: parking B12"}, b_contents

    # 3. Delete is scoped: B cannot delete A's row; A can.
    assert await mem_db.delete_memory(EMAIL_B, "11111111-1111-1111-1111-111111111111") is False
    assert await mem_db.delete_memory(EMAIL_A, "11111111-1111-1111-1111-111111111111") is True

    await db.close_pool()
    print("CI smoke OK: schema, pgvector search, scoping, delete all pass.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
