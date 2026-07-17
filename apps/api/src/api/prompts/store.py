"""Prompt resolver — Redis-cached access to the active content of a managed prompt.

The memory engine resolves prompts on every chat message, so we cache the active
content (plus version metadata) in Redis with a short TTL to avoid a DB
round-trip per LLM call. Because Redis is shared across API workers, an edit
handled by one worker invalidates the cache for all of them — the in-process
cache this replaced could only clear its own process. Resilience is layered:
falls back to the registry default if the key is missing or the DB is
unavailable, and reads straight through to the DB if Redis itself is down, so
the engine never breaks because the cache is absent.

`resolve_active` returns content + version so inference can pin which prompt
version produced an answer (prompt ops / production debugging). `get_active`
remains a content-only convenience wrapper.
"""
from __future__ import annotations

import json
import logging

import redis.asyncio as redis

from .. import config
from . import db
from .defaults import DEFAULTS_BY_KEY

_TTL_SECONDS = 30
_KEY_PREFIX = "prompt:active:"

_client: redis.Redis | None = None
_log = logging.getLogger(__name__)


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


def _default_resolved(key: str) -> dict:
    d = DEFAULTS_BY_KEY.get(key)
    return {
        "key": key,
        "content": d["content"] if d else "",
        "version": None,
        "versionId": None,
        "source": "default",
    }


def _parse_cached(raw: str, key: str) -> dict | None:
    """Accept JSON cache entries; ignore legacy plain-string values (treat as miss)."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "content" not in data:
        return None
    return {
        "key": key,
        "content": data["content"],
        "version": data.get("version"),
        "versionId": data.get("versionId"),
        "source": data.get("source") or "db",
    }


async def resolve_active(key: str) -> dict:
    """Active prompt for `key`: content + version pins (cached briefly).

    Always returns a dict with keys: key, content, version, versionId, source.
    `source` is "db" when loaded from Postgres, "default" when falling back to
    the code registry (version fields are None in that case).
    """
    cache_key = _KEY_PREFIX + key
    client = _redis()
    if client is not None:
        try:
            cached = await client.get(cache_key)
            if cached is not None:
                parsed = _parse_cached(cached, key)
                if parsed is not None:
                    return parsed
        except Exception:
            client = None  # Redis unavailable — read through and skip the write-back.
    try:
        resolved = await db.get_active_resolved(key)
    except Exception:
        _log.exception("prompt resolve failed for key=%s; using default", key)
        resolved = None
    if resolved is None:
        out = _default_resolved(key)
    else:
        out = {
            "key": key,
            "content": resolved["content"],
            "version": resolved["version"],
            "versionId": resolved["versionId"],
            "source": "db",
        }
    if client is not None:
        try:
            await client.set(
                cache_key,
                json.dumps(
                    {
                        "content": out["content"],
                        "version": out["version"],
                        "versionId": out["versionId"],
                        "source": out["source"],
                    }
                ),
                ex=_TTL_SECONDS,
            )
        except Exception:
            pass
    return out


async def get_active(key: str) -> str:
    """Active content for `key` (convenience wrapper around resolve_active)."""
    return (await resolve_active(key))["content"]


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
