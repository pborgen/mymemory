"""Prompt resolver — cached access to the active content of a managed prompt.

The memory engine resolves prompts on every chat message, so we keep a small
in-process TTL cache to avoid a DB round-trip per LLM call. Falls back to the
registry default if the key is missing or the DB is unavailable, so the engine
never breaks because a prompt row is absent.
"""
from __future__ import annotations

import time

from . import db
from .defaults import DEFAULTS_BY_KEY

_TTL_SECONDS = 30.0
_cache: dict[str, tuple[float, str]] = {}


def _default(key: str) -> str:
    d = DEFAULTS_BY_KEY.get(key)
    return d["content"] if d else ""


async def get_active(key: str) -> str:
    """Active content for `key`, cached for a few seconds; default on any miss."""
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]
    try:
        content = await db.get_active_content(key)
    except Exception:
        content = None
    if content is None:
        content = _default(key)
    _cache[key] = (now, content)
    return content


def invalidate(key: str | None = None) -> None:
    """Drop the cache for one key (after an edit) or all keys."""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)
