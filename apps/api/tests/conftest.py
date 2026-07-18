"""Shared fixtures for the API integration tests.

These are *integration* tests: they drive the real FastAPI app (real routers,
dependencies, exception handlers) against a real pgvector Postgres, exercising
the actual SQL in api.db / memory.db / prompts.db. Only the external model
providers are faked — embeddings and the generation/classification LLM calls —
so the suite never touches the remote GPU box or AWS Bedrock.

The app is driven in-process via httpx's ASGI transport; the app lifespan
(pool init, schema creation, prompt seeding) runs once per test so each test
starts from a migrated schema.

Requires POSTGRES_URL (or DATABASE_URL) to point at a pgvector-enabled Postgres.
If neither is set, the whole suite is skipped rather than failing.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from api import config
from api.main import app

# All test users share this suffix so teardown can wipe them with one DELETE.
TEST_EMAIL_DOMAIN = "itest.local"


def pytest_collection_modifyitems(config, items):  # noqa: ANN001 - pytest hook
    """Skip the entire suite when no Postgres is configured."""
    if os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"):
        return
    skip = pytest.mark.skip(
        reason="POSTGRES_URL/DATABASE_URL not set; integration tests need a pgvector Postgres"
    )
    for item in items:
        item.add_marker(skip)


# ── Fakes for the external model providers ────────────────────────────────


async def fake_embed(text: str) -> list[float]:
    """Deterministic, non-zero EMBED_DIM vector — no network, stable per string.

    Real semantics don't matter here (generation is faked too); it only has to
    match the VECTOR(EMBED_DIM) column so INSERT/search round-trip through
    pgvector for real.
    """
    v = [0.0] * config.EMBED_DIM
    data = text.encode("utf-8") or b"\x00"
    for i, byte in enumerate(data):
        v[(i * 7 + byte) % config.EMBED_DIM] += 1.0
    return v


_QUESTION_STARTS = (
    "what", "when", "where", "who", "how", "which", "why",
    "is", "are", "do", "does", "did", "can", "could", "list",
)


async def fake_classify_and_normalize(message: str, system: str | None = None) -> dict:
    """Cheap store-vs-recall heuristic standing in for the classifier LLM."""
    text = message.strip()
    lowered = text.lower()
    is_question = text.endswith("?") or lowered.split(" ", 1)[0] in _QUESTION_STARTS
    if is_question:
        return {"action": "recall", "fact": ""}
    return {"action": "store", "fact": text}


async def fake_generate_answer(
    query: str,
    memories: list[dict],
    history: list[dict] | None = None,
    system: str | None = None,
) -> dict:
    """Echo-style answer grounded in the retrieved memories, plus their sources."""
    sources = [
        {"id": m["id"], "content": m["content"], "similarity": m.get("similarity", 0)}
        for m in memories
    ]
    blob = " ".join(m.get("content", "") for m in memories).lower()
    q = query.lower()
    # Soft refusal when the question asks for something clearly not in memories.
    sensitive = ("ssn", "social security", "password")
    if any(k in q for k in sensitive) and not any(k in blob for k in sensitive):
        return {
            "answer": "I don't have that saved yet — tell me and I'll remember it.",
            "sources": sources,
        }
    if memories:
        answer = f"Based on your memories: {memories[0]['content']}"
    else:
        answer = "I don't have that saved yet."
    return {"answer": answer, "sources": sources}


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(monkeypatch):
    """An httpx client bound to the live app, with providers faked and dev auth on.

    Runs the app lifespan (schema + prompt seed) around the test and wipes all
    test-domain rows before and after so tests don't leak into each other or the
    dev database.
    """
    # Dev auth on, prod Google auth off.
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH_HEADERS", True)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "SUPER_ADMIN_EMAIL", "")
    # Fake embeddings are not semantic — disable similarity floor in tests.
    monkeypatch.setattr(config, "RETRIEVAL_MIN_SIMILARITY", 0.0)

    # Fake the model providers at the seams the engine/retrieval import them from.
    from api.memory import engine, retrieval
    from api.prompts import eval as prompt_eval

    monkeypatch.setattr(engine, "embed", fake_embed)
    monkeypatch.setattr(engine, "classify_and_normalize", fake_classify_and_normalize)
    monkeypatch.setattr(engine, "generate_answer", fake_generate_answer)
    monkeypatch.setattr(retrieval, "embed", fake_embed)
    # Prompt eval imports the same LLM helpers — keep those offline too.
    monkeypatch.setattr(prompt_eval, "classify_and_normalize", fake_classify_and_normalize)
    monkeypatch.setattr(prompt_eval, "generate_answer", fake_generate_answer)

    async with app.router.lifespan_context(app):
        from api import db as _db

        await _wipe_test_rows(_db)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            try:
                yield c
            finally:
                await _wipe_test_rows(_db)


async def _wipe_test_rows(db_module) -> None:
    """Delete every row owned by a test-domain user (children before parent FK)."""
    like = f"%@{TEST_EMAIL_DOMAIN}"
    pool = db_module.pool()
    await pool.execute("DELETE FROM chat_feedback WHERE email LIKE $1", like)
    await pool.execute("DELETE FROM chat_metrics WHERE email LIKE $1", like)
    await pool.execute("DELETE FROM memory_audit_log WHERE email LIKE $1", like)
    await pool.execute("DELETE FROM memory_chat_history WHERE email LIKE $1", like)
    await pool.execute("DELETE FROM memories WHERE email LIKE $1", like)
    await pool.execute("DELETE FROM profiles WHERE email LIKE $1", like)


@pytest.fixture
def user_email() -> str:
    """A unique test user each test, in the wipe-able test domain."""
    return f"user-{uuid.uuid4().hex[:12]}@{TEST_EMAIL_DOMAIN}"


@pytest.fixture
def auth(user_email):
    """Dev auth headers for `user_email`."""
    return {"x-user-email": user_email}


@pytest_asyncio.fixture
async def admin_auth(client, auth, user_email):
    """Dev auth headers for a user that has been granted admin in the DB."""
    from api import db as app_db

    # Touch the profile via a request, then grant admin (super-admin is env-only).
    await client.get("/api/session", headers=auth)
    await app_db.set_role(user_email, "admin")
    return auth
