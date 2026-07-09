"""Auth + session endpoints (routers/auth.py)."""
from __future__ import annotations

import pytest

from api import config


# ── GET /api/dev/accounts ─────────────────────────────────────────────────


async def test_dev_accounts_listed_when_dev_auth_enabled(client):
    resp = await client.get("/api/dev/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    emails = {a["email"] for a in accounts}
    assert emails == {"paul@dev.local", "alex@dev.local"}


async def test_dev_accounts_hidden_when_dev_auth_disabled(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH_HEADERS", False)
    resp = await client.get("/api/dev/accounts")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Not found"}


# ── POST /api/auth/google ─────────────────────────────────────────────────


async def test_google_auth_missing_credential(client):
    resp = await client.post("/api/auth/google", json={})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Missing credential"}


async def test_google_auth_not_configured(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    resp = await client.post("/api/auth/google", json={"credential": "abc"})
    assert resp.status_code == 500
    assert resp.json() == {"error": "Google auth not configured"}


async def test_google_auth_invalid_token(client, monkeypatch):
    # A client id is set, but the credential can't be verified → 401.
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    resp = await client.post("/api/auth/google", json={"credential": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid Google token"}


# ── GET /api/auth/config ──────────────────────────────────────────────────


async def test_auth_config_null_when_unset(client):
    resp = await client.get("/api/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"googleClientId": None}


async def test_auth_config_reports_client_id(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "xyz.apps.googleusercontent.com")
    resp = await client.get("/api/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"googleClientId": "xyz.apps.googleusercontent.com"}


# ── GET /api/session ──────────────────────────────────────────────────────


async def test_session_unauthenticated(client):
    resp = await client.get("/api/session")
    assert resp.status_code == 401
    assert resp.json() == {"ok": False, "authenticated": False}


async def test_session_authenticated_with_dev_header(client, auth, user_email):
    resp = await client.get("/api/session", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "authenticated": True, "email": user_email}
