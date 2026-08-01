"""Per-user feature settings + gated data tools."""
from __future__ import annotations


async def test_settings_defaults(client, auth):
    resp = await client.get("/api/settings", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["settings"]["quickChips"] is False
    assert body["settings"]["forgetByTopic"] is True
    assert any(i["key"] == "reminders" for i in body["catalog"])


async def test_settings_patch(client, auth):
    resp = await client.patch(
        "/api/settings",
        json={"settings": {"quickChips": True, "showSources": True}},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["settings"]["quickChips"] is True
    assert resp.json()["settings"]["showSources"] is True

    again = await client.get("/api/settings", headers=auth)
    assert again.json()["settings"]["quickChips"] is True


async def test_paste_inbox_requires_flag(client, auth):
    resp = await client.post(
        "/api/settings/paste-inbox",
        json={"text": "My dog is Rex"},
        headers=auth,
    )
    assert resp.status_code == 403

    await client.patch(
        "/api/settings", json={"settings": {"pasteInbox": True}}, headers=auth
    )
    resp = await client.post(
        "/api/settings/paste-inbox",
        json={"text": "My dog is Rex\nMy plate is 8XYZ123"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


async def test_chat_forget_by_topic(client, auth):
    await client.post(
        "/api/memory/chat",
        json={"message": "My wifi password is hunter2"},
        headers=auth,
    )
    resp = await client.post(
        "/api/memory/chat",
        json={"message": "Forget my wifi password"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "forgotten"
    listed = await client.get("/api/memory", headers=auth)
    assert listed.json() == []


async def test_chat_reminder_gated(client, auth):
    # Default reminders off → treated as non-reminder path (chat/store/etc).
    await client.patch(
        "/api/settings", json={"settings": {"reminders": True}}, headers=auth
    )
    resp = await client.post(
        "/api/memory/chat",
        json={"message": "remind me to call the lender"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "reminded"
    listed = await client.get("/api/reminders", headers=auth)
    assert listed.status_code == 200
    assert any("lender" in r["content"] for r in listed.json())
