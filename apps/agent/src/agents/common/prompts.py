"""Fetch managed system prompts from the MyMemory API.

Prompts are stored and versioned server-side (see apps/api/src/api/prompts).
Agents call `fetch_prompt(key, default)` at construction time to pick up the
active version. Any failure — API down, timeout, unknown key — falls back to the
hardcoded `default`, so the agent keeps working offline.

Uses the same MEMORY_API_URL / x-user-email dev-auth convention as
agents.memory.tools.
"""
from __future__ import annotations

import os

import httpx

API_URL = os.getenv("MEMORY_API_URL", "http://localhost:8080")
USER_EMAIL = os.getenv("MEMORY_USER_EMAIL", "paul@dev.local")


def fetch_prompt(key: str, default: str) -> str:
    """Return the active content for `key`, or `default` on any error."""
    try:
        response = httpx.get(
            f"{API_URL}/api/prompts/{key}",
            headers={"x-user-email": USER_EMAIL},
            timeout=10,
        )
        if response.status_code >= 400:
            return default
        content = response.json().get("content")
        return content if isinstance(content, str) and content.strip() else default
    except Exception:
        return default
