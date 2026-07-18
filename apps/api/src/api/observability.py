"""Request IDs, structured JSON logs, and lightweight chat metrics.

Phase 2 observability: every chat turn is correlatable via `request_id`, logged
as JSON, timed by stage, and summarized in `chat_metrics` for simple SLIs
without requiring Prometheus.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from . import db as _db
from . import langfuse_tracing as lf

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_log = logging.getLogger("api.observability")


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(value: str) -> None:
    request_id_var.set(value)


def new_request_id() -> str:
    return str(uuid.uuid4())


class JsonLogFormatter(logging.Formatter):
    """One JSON object per log line — easy to grep / ship to a log stack later."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": get_request_id(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["excInfo"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Configure root logging once for JSON lines (idempotent)."""
    root = logging.getLogger()
    if getattr(root, "_mymemory_json_logging", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._mymemory_json_logging = True  # type: ignore[attr-defined]


def log_event(event: str, **fields: Any) -> None:
    """Structured info log with arbitrary fields under a stable `event` name."""
    _log.info(event, extra={"extra_fields": {"event": event, **fields}})


class Timer:
    """Simple stage timer; call `.ms` after the measured block."""

    __slots__ = ("_start", "ms")

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.ms = 0

    def stop(self) -> int:
        self.ms = int((time.perf_counter() - self._start) * 1000)
        return self.ms


async def ensure_observability_tables() -> None:
    await _db.pool().execute(
        """
        CREATE TABLE IF NOT EXISTS chat_metrics (
          id                   UUID PRIMARY KEY,
          request_id           TEXT NOT NULL,
          email                TEXT NOT NULL,
          session_id           TEXT,
          action               TEXT NOT NULL,
          empty_retrieval      BOOLEAN DEFAULT FALSE,
          latency_total_ms     INT,
          latency_classify_ms  INT,
          latency_embed_ms     INT,
          latency_retrieve_ms  INT,
          latency_generate_ms  INT,
          memory_count         INT DEFAULT 0,
          prompt_versions      JSONB DEFAULT '{}',
          error                TEXT DEFAULT '',
          created_at           TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _db.pool().execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_metrics_created ON chat_metrics (created_at DESC)"
    )
    await _db.pool().execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_metrics_request ON chat_metrics (request_id)"
    )
    await _db.pool().execute(
        """
        CREATE TABLE IF NOT EXISTS chat_feedback (
          id          UUID PRIMARY KEY,
          request_id  TEXT NOT NULL,
          email       TEXT NOT NULL,
          rating      INT  NOT NULL,
          comment     TEXT DEFAULT '',
          created_at  TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    await _db.pool().execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_feedback_request ON chat_feedback (request_id)"
    )


async def record_chat_metric(
    *,
    request_id: str,
    email: str,
    session_id: str,
    action: str,
    empty_retrieval: bool,
    timings: dict[str, int],
    memory_count: int,
    prompt_versions: dict,
    error: str = "",
) -> None:
    await _db.pool().execute(
        """
        INSERT INTO chat_metrics (
          id, request_id, email, session_id, action, empty_retrieval,
          latency_total_ms, latency_classify_ms, latency_embed_ms,
          latency_retrieve_ms, latency_generate_ms, memory_count,
          prompt_versions, error
        ) VALUES (
          $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14
        )
        """,
        str(uuid.uuid4()),
        request_id,
        email,
        session_id,
        action,
        empty_retrieval,
        timings.get("total", 0),
        timings.get("classify", 0),
        timings.get("embed", 0),
        timings.get("retrieve", 0),
        timings.get("generate", 0),
        memory_count,
        prompt_versions,
        error,
    )


async def metrics_summary(hours: int = 24) -> dict:
    """Aggregate SLIs for the last N hours (admin dashboard / interview demo)."""
    row = await _db.pool().fetchrow(
        """
        SELECT
          COUNT(*)::int AS requests,
          COUNT(*) FILTER (WHERE error <> '')::int AS errors,
          COUNT(*) FILTER (WHERE action = 'stored')::int AS stored,
          COUNT(*) FILTER (WHERE action = 'recalled')::int AS recalled,
          COUNT(*) FILTER (WHERE empty_retrieval)::int AS empty_retrieval,
          COALESCE(AVG(latency_total_ms), 0)::int AS avg_total_ms,
          COALESCE(
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_total_ms),
            0
          )::int AS p95_total_ms,
          COALESCE(AVG(latency_classify_ms), 0)::int AS avg_classify_ms,
          COALESCE(AVG(latency_retrieve_ms), 0)::int AS avg_retrieve_ms,
          COALESCE(AVG(latency_generate_ms), 0)::int AS avg_generate_ms
        FROM chat_metrics
        WHERE created_at > now() - ($1 || ' hours')::interval
        """,
        str(hours),
    )
    feedback = await _db.pool().fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE rating > 0)::int AS thumbs_up,
          COUNT(*) FILTER (WHERE rating < 0)::int AS thumbs_down
        FROM chat_feedback
        WHERE created_at > now() - ($1 || ' hours')::interval
        """,
        str(hours),
    )
    return {
        "windowHours": hours,
        "requests": row["requests"] if row else 0,
        "errors": row["errors"] if row else 0,
        "actions": {
            "stored": row["stored"] if row else 0,
            "recalled": row["recalled"] if row else 0,
        },
        "emptyRetrieval": row["empty_retrieval"] if row else 0,
        "latencyMs": {
            "avgTotal": row["avg_total_ms"] if row else 0,
            "p95Total": row["p95_total_ms"] if row else 0,
            "avgClassify": row["avg_classify_ms"] if row else 0,
            "avgRetrieve": row["avg_retrieve_ms"] if row else 0,
            "avgGenerate": row["avg_generate_ms"] if row else 0,
        },
        "feedback": {
            "thumbsUp": feedback["thumbs_up"] if feedback else 0,
            "thumbsDown": feedback["thumbs_down"] if feedback else 0,
        },
    }


async def save_feedback(
    request_id: str, email: str, rating: int, comment: str = ""
) -> dict:
    if rating not in (-1, 1):
        raise ValueError("rating must be 1 (up) or -1 (down)")
    fid = str(uuid.uuid4())
    await _db.pool().execute(
        """
        INSERT INTO chat_feedback (id, request_id, email, rating, comment)
        VALUES ($1, $2, $3, $4, $5)
        """,
        fid,
        request_id,
        email,
        rating,
        comment,
    )
    # Mirror thumbs into Langfuse when tracing is on (same seeded trace id).
    lf.score_feedback(request_id=request_id, rating=rating, comment=comment)
    return {"ok": True, "id": fid, "requestId": request_id, "rating": rating}


async def get_metric_by_request_id(request_id: str) -> dict | None:
    row = await _db.pool().fetchrow(
        """
        SELECT request_id, email, session_id, action, empty_retrieval,
               latency_total_ms, latency_classify_ms, latency_embed_ms,
               latency_retrieve_ms, latency_generate_ms, memory_count,
               prompt_versions, error, created_at
        FROM chat_metrics
        WHERE request_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        request_id,
    )
    if not row:
        return None
    return {
        "requestId": row["request_id"],
        "email": row["email"],
        "sessionId": row["session_id"],
        "action": row["action"],
        "emptyRetrieval": row["empty_retrieval"],
        "timingsMs": {
            "total": row["latency_total_ms"],
            "classify": row["latency_classify_ms"],
            "embed": row["latency_embed_ms"],
            "retrieve": row["latency_retrieve_ms"],
            "generate": row["latency_generate_ms"],
        },
        "memoryCount": row["memory_count"],
        "promptVersions": row["prompt_versions"] or {},
        "error": row["error"] or "",
        "createdAt": row["created_at"],
    }
