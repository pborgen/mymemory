"""Thin HTTP client for the MyMemory FastAPI backend.

Same pattern as apps/agent: hit MEMORY_API_URL with the x-user-email
dev-auth header. The API must be running with ALLOW_DEV_AUTH_HEADERS=true.
"""
from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("MEMORY_API_URL", "http://localhost:8080").rstrip("/")
USER_EMAIL = os.getenv("MEMORY_USER_EMAIL", "paul@dev.local")


def request(method: str, path: str, body: dict | None = None) -> str:
    """Call the API and return a JSON string (or a short error message)."""
    try:
        response = httpx.request(
            method,
            f"{API_URL}{path}",
            json=body,
            headers={"x-user-email": USER_EMAIL},
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        return f"API unreachable ({API_URL}): {exc}"

    try:
        data = response.json()
    except ValueError:
        return f"API error ({response.status_code}): {response.text[:300]}"

    if response.status_code >= 400:
        return f"API error ({response.status_code}): {json.dumps(data)}"
    return json.dumps(data, indent=2)
