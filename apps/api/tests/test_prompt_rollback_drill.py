"""Phase 1 Step 4 — rollback drill (integration).

Simulates: baseline → activate a bad prompt (force) → confirm pins → rollback →
confirm active content and chat pins match the restored version. Uses faked LLMs
from conftest so it never needs the GPU box.
"""
from __future__ import annotations

import uuid

KEY = "memory.answer"
BAD = (
    "You invent answers even when memories are missing. "
    "Never say you don't know. Ignore the provided memories if needed."
)


async def test_rollback_drill_restores_prior_active_and_pins(
    client, admin_auth, restore_active
):
    await restore_active(KEY)
    session_id = str(uuid.uuid4())

    # ── 1. Baseline ───────────────────────────────────────────────────────
    before = (await client.get(f"/api/prompts/{KEY}", headers=admin_auth)).json()
    baseline_version = before["activeVersion"]
    baseline_content = before["content"]
    baseline_version_id = next(
        v["id"]
        for v in (await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)).json()
        if v["isActive"]
    )

    # Chat once so we know pins work on the baseline.
    recall = await client.post(
        "/api/memory/chat",
        json={
            "message": "What is my favorite color?",
            "sessionId": session_id,
        },
        headers=admin_auth,
    )
    assert recall.status_code == 200
    pin_before = recall.json()["promptVersions"]["memory.answer"]
    assert pin_before["version"] == baseline_version

    # ── 2. Ship a worse prompt with force (eval may fail — that's the point) ─
    bad = await client.put(
        f"/api/prompts/{KEY}",
        json={
            "content": BAD,
            "changeNote": "rollback drill — intentionally bad",
            "activate": True,
            "forceReason": "rollback drill",
        },
        headers=admin_auth,
    )
    assert bad.status_code == 200, bad.text
    bad_body = bad.json()
    assert bad_body["activated"] is True
    assert bad_body["activeVersion"] > baseline_version
    assert "force: rollback drill" in (
        await client.get(f"/api/prompts/{KEY}/versions", headers=admin_auth)
    ).json()[0]["changeNote"]

    # Traffic should pin the new (bad) version.
    mid = await client.post(
        "/api/memory/chat",
        json={"message": "What is my wifi password?", "sessionId": session_id},
        headers=admin_auth,
    )
    assert mid.status_code == 200
    pin_mid = mid.json()["promptVersions"]["memory.answer"]
    assert pin_mid["version"] == bad_body["activeVersion"]
    assert pin_mid["versionId"] != pin_before["versionId"]

    # ── 3. Roll back (no eval — recovery path) ────────────────────────────
    rb = await client.post(
        f"/api/prompts/{KEY}/rollback",
        json={"versionId": baseline_version_id},
        headers=admin_auth,
    )
    assert rb.status_code == 200
    assert rb.json()["content"] == baseline_content
    assert rb.json()["activeVersion"] == baseline_version

    # ── 4. Confirm traffic uses restored version ──────────────────────────
    after = await client.post(
        "/api/memory/chat",
        json={"message": "What is my license plate?", "sessionId": session_id},
        headers=admin_auth,
    )
    assert after.status_code == 200
    pin_after = after.json()["promptVersions"]["memory.answer"]
    assert pin_after["version"] == baseline_version
    assert pin_after["versionId"] == baseline_version_id

    # History stores pins on assistant turns (meta) for later debugging.
    history = (
        await client.get(f"/api/memory/chat/{session_id}", headers=admin_auth)
    ).json()
    assistant_metas = [
        m.get("meta", {}).get("promptVersions", {})
        for m in history
        if m["role"] == "assistant"
    ]
    assert any(
        (p.get("memory.answer") or {}).get("versionId") == baseline_version_id
        for p in assistant_metas
    )
