"""Prompt resolver — Redis-cached access to the active content of a managed prompt.

The memory engine resolves prompts on every chat message, so we cache the active
content in Redis with a short TTL to avoid a DB round-trip per LLM call. Because
Redis is shared across API workers, an edit handled by one worker invalidates the
cache for all of them — the in-process cache this replaced could only clear its
own process. Resilience is layered: falls back to the registry default if the key
is missing or the DB is unavailable, and reads straight through to the DB if Redis
itself is down, so the engine never breaks because the cache is absent.
"""
from __future__ import annotations

import redis.asyncio as redis

from .. import config
from . import db
from .defaults import DEFAULTS_BY_KEY

_TTL_SECONDS = 30
_KEY_PREFIX = "prompt:active:"

_client: redis.Redis | None = None


def _redis() -> redis.Redis | None:
    """The shared async Redis client, created lazily; None if REDIS_URL is unset."""
    global _client
    if _client is None and config.REDIS_URL:
        _client = redis.from_url(config.REDIS_URL, decode_responses=True)
    return _client


async def close() -> None:
    """Close the shared client (called on app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _default(key: str) -> str:
    d = DEFAULTS_BY_KEY.get(key)
    return d["content"] if d else ""


async def get_active(key: str) -> str:
    """Active content for `key`, cached in Redis for a few seconds; default on any miss."""
    cache_key = _KEY_PREFIX + key
    client = _redis()
    if client is not None:
        try:
            cached = await client.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            client = None  # Redis unavailable — read through and skip the write-back.
    try:
        content = await db.get_active_content(key)
    except Exception:
        content = None
    if content is None:
        content = _default(key)
    if client is not None:
        try:
            await client.set(cache_key, content, ex=_TTL_SECONDS)
        except Exception:
            pass
    return content


async def invalidate(key: str | None = None) -> None:
    """Drop the cache for one key (after an edit) or all managed keys."""
    client = _redis()
    if client is None:
        return
    try:
        if key is None:
            keys = [_KEY_PREFIX + k for k in DEFAULTS_BY_KEY]
            if keys:
                await client.delete(*keys)
        else:
            await client.delete(_KEY_PREFIX + key)
    except Exception:
        pass
