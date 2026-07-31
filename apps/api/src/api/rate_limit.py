"""In-process sliding-window rate limiter for costly LLM endpoints.

Keyed by authenticated email (preferred) so a single user cannot burn Bedrock
spend. Falls back to client IP only when no identity is available (should not
happen on gated routes). Fine for single App Runner instances; swap to Redis
if you scale to multiple replicas that need a shared counter.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window_sec: float = 60.0) -> None:
        """Record a hit; raise 429 if `limit` is exceeded in the window.

        `limit <= 0` disables the limiter (useful in tests).
        """
        if limit <= 0:
            return
        now = time.monotonic()
        cutoff = now - window_sec
        async with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded — try again in a minute",
                )
            q.append(now)

    def reset(self) -> None:
        """Clear all counters (tests only)."""
        self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


async def enforce(key: str, limit: int, window_sec: float = 60.0) -> None:
    await limiter.hit(key, limit, window_sec)
