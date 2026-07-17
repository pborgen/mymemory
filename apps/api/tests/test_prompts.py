"""Prompt management endpoints (routers/prompts.py).

Prompts are global and seeded on startup. Editing appends versions to the shared
tables, so the mutating tests capture the active version up front and restore it
on teardown (via `restore_active`) to leave prompt *content* unchanged.
"""
from __future__ import annotations

import uuid

import pytest_asyncio

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


async def test_save_prompt_creates_new_active_version(client, admin_auth, restore_active):
    await restore_active(KEY)
    before = (await client.get(f"/api/prompts/{KEY}", headers=admin_auth)).json()

    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={
            "content": "Edited answer prompt.",
            "changeNote": "Phase 1 audit: test save with rationale",
        },
        headers=admin_auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "Edited answer prompt."
    assert body["activated"] is True
    # A new version is appended and made active (version = max+1, so it advances).
    assert body["activeVersion"] > before["activeVersion"]

    versions = (await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)).json()
    active = next(v for v in versions if v["isActive"])
    assert active["changeNote"] == "Phase 1 audit: test save with rationale"
    assert active["createdBy"]


async def test_save_draft_does_not_activate(client, admin_auth, restore_active):
    await restore_active(KEY)
    before = (await client.get(f"/api/prompts/{KEY}", headers=admin_auth)).json()

    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={
            "content": "Draft only content",
            "changeNote": "draft save",
            "activate": False,
        },
        headers=admin_auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["activated"] is False
    assert body["activeVersion"] == before["activeVersion"]
    assert body["content"] == before["content"]  # active content unchanged

    versions = (await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)).json()
    assert any(v["content"] == "Draft only content" and not v["isActive"] for v in versions)


async def test_activate_blocked_when_eval_fails(client, admin_auth, restore_active, monkeypatch):
    from api.prompts import eval as prompt_eval

    await restore_active(KEY)

    async def always_fail(key: str, content: str) -> dict:
        return {
            "key": key,
            "passed": False,
            "skipped": False,
            "threshold": 1.0,
            "passedCount": 0,
            "total": 1,
            "results": [{"id": "x", "passed": False, "detail": "forced fail"}],
            "summary": "0/1 cases passed",
        }

    monkeypatch.setattr(prompt_eval, "evaluate_prompt", always_fail)

    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={
            "content": "Would be active but eval fails",
            "changeNote": "should block",
            "activate": True,
        },
        headers=admin_auth,
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "Eval failed" in body["error"]
    assert body["eval"]["passed"] is False


async def test_activate_force_override(client, admin_auth, restore_active, monkeypatch):
    from api.prompts import eval as prompt_eval

    await restore_active(KEY)

    async def always_fail(key: str, content: str) -> dict:
        return {
            "key": key,
            "passed": False,
            "skipped": False,
            "threshold": 1.0,
            "passedCount": 0,
            "total": 1,
            "results": [{"id": "x", "passed": False, "detail": "forced fail"}],
            "summary": "0/1 cases passed",
        }

    monkeypatch.setattr(prompt_eval, "evaluate_prompt", always_fail)

    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={
            "content": "Forced live despite eval",
            "changeNote": "emergency",
            "activate": True,
            "forceReason": "incident hotfix",
        },
        headers=admin_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["activated"] is True
    assert "force: incident hotfix" in (
        await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)
    ).json()[0]["changeNote"]


async def test_save_prompt_requires_content(client, admin_auth):
    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={"content": "", "changeNote": "n/a"},
        headers=admin_auth,
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "Content required"}


async def test_save_prompt_requires_change_note(client, admin_auth):
    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={"content": "Missing rationale"},
        headers=admin_auth,
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "changeNote required"}


async def test_save_unknown_prompt_404(client, admin_auth):
    resp = await client.put(
        "/api/prompts/does.not.exist",
        json={"content": "hi", "changeNote": "test"},
        headers=admin_auth,
    )
    assert resp.status_code == 404


async def test_save_prompt_forbidden_for_non_admin(client, auth):
    resp = await client.put(
        f"/api/prompts/{KEY}",
        json={"content": "nope", "changeNote": "should be forbidden"},
        headers=auth,
    )
    assert resp.status_code == 403
    assert resp.json() == {"error": "Admin access required"}


# ── POST /api/prompts/{key}/rollback ──────────────────────────────────────


async def test_rollback_requires_version_id(client, admin_auth):
    resp = await client.post(f"/api/prompts/{KEY}/rollback", json={}, headers=admin_auth)
    assert resp.status_code == 400
    assert resp.json() == {"error": "versionId required"}


async def test_rollback_to_previous_version(client, admin_auth, restore_active):
    await restore_active(KEY)
    original = (await client.get(f"/api/prompts/{KEY}", headers=admin_auth)).json()
    original_version_id = next(
        v["id"] for v in (await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)).json()
        if v["isActive"]
    )

    # Edit, then roll back to the original version → content restored.
    await client.put(
        f"/api/prompts/{KEY}",
        json={"content": "temp edit", "changeNote": "temp for rollback test"},
        headers=admin_auth,
    )
    resp = await client.post(
        f"/api/prompts/{KEY}/rollback",
        json={"versionId": original_version_id},
        headers=admin_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == original["content"]


async def test_rollback_unknown_version_404(client, admin_auth):
    resp = await client.post(
        f"/api/prompts/{KEY}/rollback",
        json={"versionId": str(uuid.uuid4())},
        headers=admin_auth,
    )
    assert resp.status_code == 404


# ── POST /api/prompts/{key}/reset ─────────────────────────────────────────


async def test_reset_prompt_restores_default(client, admin_auth, restore_active):
    from api.prompts.defaults import DEFAULTS_BY_KEY

    await restore_active(KEY)
    # Edit away from the default, then reset back to it.
    await client.put(
        f"/api/prompts/{KEY}",
        json={"content": "drifted", "changeNote": "drift before reset"},
        headers=admin_auth,
    )
    resp = await client.post(f"/api/prompts/{KEY}/reset", headers=admin_auth)
    assert resp.status_code == 200
    assert resp.json()["content"] == DEFAULTS_BY_KEY[KEY]["content"]
    versions = (await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)).json()
    active = next(v for v in versions if v["isActive"])
    assert active["changeNote"] == "Reset to registry default"


async def test_reset_unknown_prompt_404(client, admin_auth):
    resp = await client.post("/api/prompts/does.not.exist/reset", headers=admin_auth)
    assert resp.status_code == 404
