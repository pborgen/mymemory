"""Per-user feature settings + gated data tools + chat feature paths."""
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


async def test_settings_ignores_unknown_keys(client, auth):
    resp = await client.patch(
        "/api/settings",
        json={"settings": {"quickChips": True, "notARealFlag": True}},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()["settings"]
    assert body["quickChips"] is True
    assert "notARealFlag" not in body


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


async def test_import_export_and_delete_all(client, auth):
    assert (
        await client.get("/api/settings/export", headers=auth)
    ).status_code == 403

    await client.patch(
        "/api/settings", json={"settings": {"importExport": True}}, headers=auth
    )
    imported = await client.post(
        "/api/settings/import",
        json={"text": "My favorite color is teal\nMy dog is named Rex"},
        headers=auth,
    )
    assert imported.status_code == 200
    assert imported.json()["count"] == 2

    exported = await client.get("/api/settings/export", headers=auth)
    assert exported.status_code == 200
    assert exported.json()["count"] == 2

    csv_resp = await client.get("/api/settings/export.csv", headers=auth)
    assert csv_resp.status_code == 200
    assert "teal" in csv_resp.text.lower()

    wiped = await client.delete("/api/settings/memories", headers=auth)
    assert wiped.status_code == 200
    assert wiped.json()["deleted"] == 2
    listed = await client.get("/api/memory", headers=auth)
    assert listed.json() == []


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


async def test_chat_forget_by_topic_can_be_disabled(client, auth):
    await client.patch(
        "/api/settings", json={"settings": {"forgetByTopic": False}}, headers=auth
    )
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
    # With the flag off, this is not a topic-delete turn.
    assert resp.json()["action"] != "forgotten"
    listed = await client.get("/api/memory", headers=auth)
    assert len(listed.json()) == 1


async def test_chat_edit_correct(client, auth):
    await client.post(
        "/api/memory/chat",
        json={"message": "My car license plate is 8XYZ123"},
        headers=auth,
    )
    resp = await client.post(
        "/api/memory/chat",
        json={"message": "Actually my plate is 8XYZ456"},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "updated"
    assert "8XYZ456" in body["answer"]

    listed = await client.get("/api/memory", headers=auth)
    contents = [m["content"] for m in listed.json()]
    assert len(contents) == 1
    assert any("8XYZ456" in c for c in contents)
    assert not any("8XYZ123" in c for c in contents)


async def test_quick_chips_on_store(client, auth):
    off = await client.post(
        "/api/memory/chat",
        json={"message": "My dog's name is Rex"},
        headers=auth,
    )
    assert off.json().get("chips") in ([], None)

    await client.patch(
        "/api/settings", json={"settings": {"quickChips": True}}, headers=auth
    )
    on = await client.post(
        "/api/memory/chat",
        json={"message": "My favorite color is teal"},
        headers=auth,
    )
    chips = on.json().get("chips") or []
    assert {c["id"] for c in chips} >= {"undo", "ask"}


async def test_chat_reminder_gated(client, auth):
    blocked = await client.get("/api/reminders", headers=auth)
    assert blocked.status_code == 403

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
    reminders = listed.json()
    assert any("lender" in r["content"] for r in reminders)

    rid = next(r["id"] for r in reminders if "lender" in r["content"])
    done = await client.post(f"/api/reminders/{rid}/done", headers=auth)
    assert done.status_code == 200
    remaining = await client.get("/api/reminders", headers=auth)
    assert remaining.status_code == 200
    assert remaining.json() == []
