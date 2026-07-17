"""Memory endpoints (routers/memory.py) — chat store/recall + memory CRUD.

The classifier, embedder, and answer generator are faked in conftest, so these
tests assert the routing/persistence behaviour of the engine and DB layer, not
model quality.
"""
from __future__ import annotations

import uuid


# ── Auth gate ─────────────────────────────────────────────────────────────


async def test_endpoints_require_auth(client):
    for method, path in [
        ("get", "/api/memory"),
        ("post", "/api/memory"),
        ("post", "/api/memory/chat"),
        ("get", f"/api/memory/chat/{uuid.uuid4()}"),
        ("delete", f"/api/memory/{uuid.uuid4()}"),
    ]:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(client, method)(path, **kwargs)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
        assert resp.json() == {"error": "Unauthorized"}


# ── POST /api/memory (manual create) ──────────────────────────────────────


async def test_create_memory(client, auth):
    resp = await client.post("/api/memory", json={"content": "My license plate is 8XYZ123"}, headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["memory"]["content"] == "My license plate is 8XYZ123"
    assert body["memory"]["source"] == "manual"
    assert body["memory"]["id"]


async def test_create_memory_requires_content(client, auth):
    resp = await client.post("/api/memory", json={"content": "   "}, headers=auth)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Content required"}


async def test_create_then_list_memories(client, auth):
    await client.post("/api/memory", json={"content": "fact one"}, headers=auth)
    await client.post("/api/memory", json={"content": "fact two"}, headers=auth)

    resp = await client.get("/api/memory", headers=auth)
    assert resp.status_code == 200
    contents = [m["content"] for m in resp.json()]
    assert set(contents) == {"fact one", "fact two"}


async def test_list_memories_scoped_per_user(client, auth):
    # Another user's memory must not appear in this user's list.
    await client.post("/api/memory", json={"content": "mine"}, headers=auth)
    other = {"x-user-email": "other-user@itest.local"}
    await client.post("/api/memory", json={"content": "theirs"}, headers=other)

    resp = await client.get("/api/memory", headers=auth)
    contents = [m["content"] for m in resp.json()]
    assert contents == ["mine"]


# ── DELETE /api/memory/{id} ───────────────────────────────────────────────


async def test_delete_memory(client, auth):
    created = await client.post("/api/memory", json={"content": "delete me"}, headers=auth)
    memory_id = created.json()["memory"]["id"]

    resp = await client.delete(f"/api/memory/{memory_id}", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    remaining = await client.get("/api/memory", headers=auth)
    assert remaining.json() == []


async def test_delete_missing_memory_404(client, auth):
    resp = await client.delete(f"/api/memory/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404
    assert resp.json() == {"error": "Not found"}


async def test_delete_is_scoped_per_user(client, auth):
    created = await client.post("/api/memory", json={"content": "owner only"}, headers=auth)
    memory_id = created.json()["memory"]["id"]

    other = {"x-user-email": "other-user@itest.local"}
    resp = await client.delete(f"/api/memory/{memory_id}", headers=other)
    assert resp.status_code == 404  # another user can't delete it

    # Still there for the owner.
    remaining = await client.get("/api/memory", headers=auth)
    assert [m["id"] for m in remaining.json()] == [memory_id]


# ── POST /api/memory/chat ─────────────────────────────────────────────────


async def test_chat_requires_message(client, auth):
    resp = await client.post("/api/memory/chat", json={"message": "  "}, headers=auth)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Message required"}


async def test_chat_store_path(client, auth):
    resp = await client.post(
        "/api/memory/chat", json={"message": "My dog's name is Rex"}, headers=auth
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "stored"
    assert body["sources"] == []
    assert "Rex" in body["answer"]
    assert body["sessionId"]
    assert body["requestId"]
    assert "total" in body["timingsMs"]
    # Store path pins the classifier prompt version (not the answer prompt).
    assert "memory.classifier" in body["promptVersions"]
    assert "memory.answer" not in body["promptVersions"]
    pin = body["promptVersions"]["memory.classifier"]
    assert pin["source"] in ("db", "default")
    if pin["source"] == "db":
        assert pin["version"] >= 1
        assert pin["versionId"]

    # The fact was persisted and is now listable.
    listed = await client.get("/api/memory", headers=auth)
    assert any("Rex" in m["content"] for m in listed.json())


async def test_chat_recall_path(client, auth):
    await client.post("/api/memory/chat", json={"message": "My favorite color is teal"}, headers=auth)
    resp = await client.post(
        "/api/memory/chat", json={"message": "What is my favorite color?"}, headers=auth
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "recalled"
    assert isinstance(body["sources"], list)
    assert body["answer"]
    # Recall path pins both classifier and answer prompts.
    assert set(body["promptVersions"]) == {"memory.classifier", "memory.answer"}
    for pin in body["promptVersions"].values():
        assert pin["source"] in ("db", "default")


async def test_chat_invalid_session_id_is_replaced(client, auth):
    resp = await client.post(
        "/api/memory/chat",
        json={"message": "Remember I like tea", "sessionId": "not-a-uuid"},
        headers=auth,
    )
    assert resp.status_code == 200
    # Server mints a valid UUID when the client sends a bad one.
    uuid.UUID(resp.json()["sessionId"])


async def test_chat_preserves_valid_session_id(client, auth):
    session_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/memory/chat",
        json={"message": "Remember I like coffee", "sessionId": session_id},
        headers=auth,
    )
    assert resp.json()["sessionId"] == session_id


# ── GET /api/memory/chat/{session_id} ─────────────────────────────────────


async def test_chat_history_records_turns(client, auth):
    session_id = str(uuid.uuid4())
    await client.post(
        "/api/memory/chat",
        json={"message": "My car is blue", "sessionId": session_id},
        headers=auth,
    )

    resp = await client.get(f"/api/memory/chat/{session_id}", headers=auth)
    assert resp.status_code == 200
    history = resp.json()
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant"]
    assert history[0]["content"] == "My car is blue"
    assert history[1]["content"]  # assistant answer
    # Assistant turn persists the prompt version pins used for that reply.
    assert "promptVersions" in history[1]["meta"]
    assert "memory.classifier" in history[1]["meta"]["promptVersions"]
    assert history[1]["meta"]["requestId"]


async def test_chat_feedback_and_debug_lookup(client, admin_auth):
    chat = await client.post(
        "/api/memory/chat",
        json={"message": "My city is Austin"},
        headers=admin_auth,
    )
    assert chat.status_code == 200
    request_id = chat.json()["requestId"]

    fb = await client.post(
        "/api/memory/chat/feedback",
        json={"requestId": request_id, "rating": 1, "comment": "correct"},
        headers=admin_auth,
    )
    assert fb.status_code == 200
    assert fb.json()["ok"] is True

    debug = await client.get(f"/api/memory/debug/{request_id}", headers=admin_auth)
    assert debug.status_code == 200
    assert debug.json()["requestId"] == request_id
    assert debug.json()["action"] == "stored"

    summary = await client.get("/api/metrics/summary?hours=24", headers=admin_auth)
    assert summary.status_code == 200
    assert summary.json()["requests"] >= 1


async def test_health_reports_postgres(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["checks"]["postgres"]["ok"] is True


async def test_chat_history_empty_for_unknown_session(client, auth):
    resp = await client.get(f"/api/memory/chat/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []
