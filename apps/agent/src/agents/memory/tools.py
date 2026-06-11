"""Tools for the memory agent — thin wrappers over the MyMemory FastAPI backend.

Each tool hits the API on MEMORY_API_URL (default http://localhost:8080) using
dev auth headers (x-user-email), so the API must run with
ALLOW_DEV_AUTH_HEADERS=true.
"""
from __future__ import annotations

import json
import os

import httpx
from langchain_core.tools import tool

API_URL = os.getenv("MEMORY_API_URL", "http://localhost:8080")
USER_EMAIL = os.getenv("MEMORY_USER_EMAIL", "paul@dev.local")


def _request(method: str, path: str, body: dict | None = None) -> str:
    response = httpx.request(
        method,
        f"{API_URL}{path}",
        json=body,
        headers={"x-user-email": USER_EMAIL},
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        return f"API error ({response.status_code}): {response.text[:300]}"
    if response.status_code >= 400:
        return f"API error ({response.status_code}): {json.dumps(data)}"
    return json.dumps(data)


@tool
def remember(fact: str) -> str:
    """Save a fact about the user to their personal memory. Pass a clean,
    self-contained statement (e.g. "The user's car license plate is 8XYZ123")."""
    return _request("POST", "/api/memory", body={"content": fact})


@tool
def recall(question: str) -> str:
    """Look up something the user told you earlier by asking a question
    (e.g. "what is my license plate?"). Returns an answer grounded in their
    saved memories."""
    return _request("POST", "/api/memory/chat", body={"message": question})


@tool
def list_all_memories() -> str:
    """List every memory currently saved for the user."""
    return _request("GET", "/api/memory")


MEMORY_TOOLS = [remember, recall, list_all_memories]
