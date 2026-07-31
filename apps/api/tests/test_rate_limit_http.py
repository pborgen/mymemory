"""Rate-limit behavior on costly memory endpoints (needs Postgres)."""
from __future__ import annotations

from api import config
from api import rate_limit as rl


async def test_chat_rate_limit_returns_429(client, auth, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_CHAT_PER_MIN", 2)
    rl.limiter.reset()

    for _ in range(2):
        resp = await client.post(
            "/api/memory/chat",
            json={"message": "hello there"},
            headers=auth,
        )
        assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/api/memory/chat",
        json={"message": "hello again"},
        headers=auth,
    )
    assert resp.status_code == 429
    assert "Rate limit" in resp.json()["error"]
