"""Root + health endpoints."""
from __future__ import annotations


async def test_root_returns_plain_text(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.text == "MyMemory API"


async def test_health_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
