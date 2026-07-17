"""Admin role endpoints (routers/admins.py) — DB-backed profiles.role."""
from __future__ import annotations

import pytest

from api import config
from api import db as app_db


async def test_me_reports_user_by_default(client, auth, user_email):
    resp = await client.get("/api/me", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user_email
    assert body["role"] == "user"
    assert body["isAdmin"] is False


async def test_list_admins_requires_admin(client, auth):
    resp = await client.get("/api/admins", headers=auth)
    assert resp.status_code == 403


async def test_admin_can_grant_and_list(client, admin_auth, user_email):
    other = f"other-{user_email}"
    resp = await client.put(
        f"/api/admins/{other}",
        json={"role": "admin"},
        headers=admin_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    assert resp.json()["email"] == other

    listed = await client.get("/api/admins", headers=admin_auth)
    assert listed.status_code == 200
    emails = {a["email"] for a in listed.json()}
    assert user_email in emails
    assert other in emails


async def test_cannot_demote_last_admin(client, admin_auth, user_email):
    others = [a for a in await app_db.list_admins() if a["email"] != user_email]
    if others:
        pytest.skip(
            "shared DB already has other admins; last-admin guard needs a solo-admin DB"
        )

    resp = await client.put(
        f"/api/admins/{user_email}",
        json={"role": "user"},
        headers=admin_auth,
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "Cannot demote the last admin"}


async def test_cannot_demote_super_admin(client, admin_auth, user_email, monkeypatch):
    monkeypatch.setattr(config, "SUPER_ADMIN_EMAIL", user_email)
    # Re-seed so the flag matches this user (startup seed already ran).
    await app_db.set_role(user_email, "admin")

    other = f"peer-{user_email}"
    await client.put(
        f"/api/admins/{other}", json={"role": "admin"}, headers=admin_auth
    )

    resp = await client.put(
        f"/api/admins/{user_email}",
        json={"role": "user"},
        headers=admin_auth,
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "Cannot demote the super admin"}


async def test_admin_can_demote_other_admin(client, admin_auth, user_email):
    other = f"peer-{user_email}"
    await client.put(
        f"/api/admins/{other}", json={"role": "admin"}, headers=admin_auth
    )

    resp = await client.put(
        f"/api/admins/{other}",
        json={"role": "user"},
        headers=admin_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


async def test_super_admin_seeded_on_startup(client, monkeypatch):
    """seed_super_admin runs at lifespan; call it again after setting the env."""
    email = "super-seed@itest.local"
    monkeypatch.setattr(config, "SUPER_ADMIN_EMAIL", email)
    await app_db.seed_super_admin()
    assert await app_db.is_admin(email)
