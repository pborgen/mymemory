"""Prompt management endpoints (routers/prompts.py).

Prompts are global and seeded on startup. Editing appends versions to the shared
tables, so the mutating tests capture the active version up front and restore it
on teardown (via `restore_active`) to leave prompt *content* unchanged.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from api import config

# A key that is always seeded (see api.prompts.defaults.DEFAULTS).
KEY = "memory.answer"


@pytest_asyncio.fixture
async def restore_active(client):
    """Restore each marked prompt's active version pointer after the test.

    `client` is depended-on so the app lifespan/pool is live for the DB calls.
    """
    from api.prompts import db as prompts_db

    saved: dict[str, str] = {}

    async def mark(key: str) -> None:
        versions = await prompts_db.list_versions(key)
        active = next(v for v in versions if v["isActive"])
        saved[key] = active["id"]

    yield mark

    for key, version_id in saved.items():
        await prompts_db.set_active(key, version_id)


# ── GET /api/prompts ──────────────────────────────────────────────────────


async def test_list_prompts_requires_auth(client):
    resp = await client.get("/api/prompts")
    assert resp.status_code == 401


async def test_list_prompts_includes_seeded_keys(client, auth):
    resp = await client.get("/api/prompts", headers=auth)
    assert resp.status_code == 200
    keys = {p["key"] for p in resp.json()}
    assert {"memory.answer", "memory.classifier"} <= keys


# ── GET /api/prompts/{key} ────────────────────────────────────────────────


async def test_get_prompt(client, auth):
    resp = await client.get(f"/api/prompts/{KEY}", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == KEY
    assert body["content"]
    assert body["activeVersion"] >= 1


async def test_get_unknown_prompt_404(client, auth):
    resp = await client.get("/api/prompts/does.not.exist", headers=auth)
    assert resp.status_code == 404
    assert resp.json() == {"error": "Not found"}


# ── GET /api/prompts/{key}/versions ───────────────────────────────────────


async def test_list_versions(client, auth):
    resp = await client.get(f"/api/prompts/{KEY}/versions", headers=auth)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 1
    assert sum(1 for v in versions if v["isActive"]) == 1


async def test_list_versions_unknown_key_404(client, auth):
    resp = await client.get("/api/prompts/does.not.exist/versions", headers=auth)
    assert resp.status_code == 404


# ── PUT /api/prompts/{key} (admin) ────────────────────────────────────────


async def test_save_prompt_creates_new_active_version(client, auth, restore_active):
    await restore_active(KEY)
    before = (await client.get(f"/api/prompts/{KEY}", headers=auth)).json()

    resp = await client.put(
        f"/api/prompts/{KEY}", json={"content": "Edited answer prompt."}, headers=auth
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "Edited answer prompt."
    # A new version is appended and made active (version = max+1, so it advances).
    assert body["activeVersion"] > before["activeVersion"]


async def test_save_prompt_requires_content(client, auth):
    resp = await client.put(f"/api/prompts/{KEY}", json={"content": ""}, headers=auth)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Content required"}


async def test_save_unknown_prompt_404(client, auth):
    resp = await client.put(
        "/api/prompts/does.not.exist", json={"content": "hi"}, headers=auth
    )
    assert resp.status_code == 404


async def test_save_prompt_forbidden_for_non_admin(client, auth, monkeypatch):
    # With ADMIN_EMAILS set and the caller not in it, editing is 403.
    monkeypatch.setattr(config, "ADMIN_EMAILS", ["admin@itest.local"])
    resp = await client.put(
        f"/api/prompts/{KEY}", json={"content": "nope"}, headers=auth
    )
    assert resp.status_code == 403
    assert resp.json() == {"error": "Admin access required"}


# ── POST /api/prompts/{key}/rollback ──────────────────────────────────────


async def test_rollback_requires_version_id(client, auth):
    resp = await client.post(f"/api/prompts/{KEY}/rollback", json={}, headers=auth)
    assert resp.status_code == 400
    assert resp.json() == {"error": "versionId required"}


async def test_rollback_to_previous_version(client, auth, restore_active):
    await restore_active(KEY)
    original = (await client.get(f"/api/prompts/{KEY}", headers=auth)).json()
    original_version_id = next(
        v["id"] for v in (await client.get(f"/api/prompts/{KEY}/versions", headers=auth)).json()
        if v["isActive"]
    )

    # Edit, then roll back to the original version → content restored.
    await client.put(f"/api/prompts/{KEY}", json={"content": "temp edit"}, headers=auth)
    resp = await client.post(
        f"/api/prompts/{KEY}/rollback", json={"versionId": original_version_id}, headers=auth
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == original["content"]


async def test_rollback_unknown_version_404(client, auth):
    resp = await client.post(
        f"/api/prompts/{KEY}/rollback", json={"versionId": str(uuid.uuid4())}, headers=auth
    )
    assert resp.status_code == 404


# ── POST /api/prompts/{key}/reset ─────────────────────────────────────────


async def test_reset_prompt_restores_default(client, auth, restore_active):
    from api.prompts.defaults import DEFAULTS_BY_KEY

    await restore_active(KEY)
    # Edit away from the default, then reset back to it.
    await client.put(f"/api/prompts/{KEY}", json={"content": "drifted"}, headers=auth)
    resp = await client.post(f"/api/prompts/{KEY}/reset", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["content"] == DEFAULTS_BY_KEY[KEY]["content"]


async def test_reset_unknown_prompt_404(client, auth):
    resp = await client.post("/api/prompts/does.not.exist/reset", headers=auth)
    assert resp.status_code == 404
