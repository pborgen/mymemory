"""Authentication — Google OAuth (Bearer) + dev `x-user-email` header.

Exposed as FastAPI dependencies. Email is the user identifier; there are no
roles — every authenticated user is a regular user who owns their memories.
"""
from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from . import config, db

_google_request = google_requests.Request()


def _verify_google_token(token: str) -> dict | None:
    """Verify a Google ID token; return its payload or None. Synchronous (network)."""
    info = google_id_token.verify_oauth2_token(
        token, _google_request, audience=config.GOOGLE_CLIENT_ID
    )
    return info


async def identify_user(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):]
        if not config.GOOGLE_CLIENT_ID:
            return None
        payload = await asyncio.to_thread(_verify_google_token, token)
        return payload.get("email") if payload else None
    if config.ALLOW_DEV_AUTH_HEADERS:
        dev_email = request.headers.get("x-user-email")
        if dev_email:
            return dev_email
    return None


async def require_user(request: Request) -> str:
    try:
        email = await identify_user(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")
    await db.ensure_profile(email)
    return email
