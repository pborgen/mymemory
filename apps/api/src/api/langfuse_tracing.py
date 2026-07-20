"""Optional Langfuse tracing for memory chat (local-friendly).

Follows Langfuse skill / best-practice guidance:
  - one trace per chat turn; session_id groups conversation
  - verb-first stable observation names
  - correct as_type (chain / generation / retriever / embedding / guardrail)
  - PII masking before export
  - environment separation (development vs production)
  - user-thumbs scores seeded from request_id

Disabled until keys are set — request_id / chat_metrics still work alone.
"""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from . import config

_log = logging.getLogger("api.langfuse")
_client = None
_client_checked = False

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PAN_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def enabled() -> bool:
    return config.LANGFUSE_ENABLED


def mask_data(data: Any, **_: Any) -> Any:
    """Redact SSN / payment-card shaped strings before they leave the process."""
    if isinstance(data, str):
        out = _SSN_RE.sub("[REDACTED_SSN]", data)
        return _PAN_RE.sub("[REDACTED_CARD]", out)
    if isinstance(data, dict):
        return {k: mask_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [mask_data(v) for v in data]
    if isinstance(data, tuple):
        return tuple(mask_data(v) for v in data)
    return data


def trace_id_for_request(request_id: str) -> str:
    """Deterministic Langfuse/OTEL trace id from our UUID request_id."""
    from langfuse import Langfuse

    return Langfuse.create_trace_id(seed=request_id)


def get_client():
    """Lazy Langfuse client, or None when tracing is off."""
    global _client, _client_checked
    if not enabled():
        return None
    if _client_checked:
        return _client
    _client_checked = True
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            base_url=config.LANGFUSE_BASE_URL,
            tracing_enabled=True,
            environment=config.LANGFUSE_TRACING_ENVIRONMENT,
            mask=mask_data,
        )
        _log.info(
            "Langfuse tracing enabled (base_url=%s env=%s)",
            config.LANGFUSE_BASE_URL,
            config.LANGFUSE_TRACING_ENVIRONMENT,
        )
    except Exception as exc:
        _log.warning("Langfuse init failed; continuing without traces: %s", exc)
        _client = None
    return _client


def flush() -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        _log.warning("Langfuse flush failed: %s", exc)


def shutdown() -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.flush()
        client.shutdown()
    except Exception as exc:
        _log.warning("Langfuse shutdown failed: %s", exc)


def gen_model_name() -> str:
    if config.GEN_PROVIDER == "openai":
        return config.OPENAI_CHAT_MODEL
    if config.GEN_PROVIDER == "ollama":
        return config.OLLAMA_CHAT_MODEL
    return config.RAG_MODEL_ID


def embed_model_name() -> str:
    return config.EMBED_MODEL_ID


def uses_openai_generation_integration() -> bool:
    """True when OpenAI drop-in will auto-create generation observations."""
    return enabled() and config.GEN_PROVIDER == "openai"


@contextmanager
def chat_trace(
    *,
    request_id: str,
    email: str,
    session_id: str,
    message: str,
    source: str,
) -> Iterator[Any]:
    """Root observation for one chat turn. Yields span or None."""
    client = get_client()
    if client is None:
        yield None
        return

    from langfuse import propagate_attributes

    tid = trace_id_for_request(request_id)
    # Trace-level I/O: user message only (not full function args / secrets).
    root_input = [{"role": "user", "content": message}]
    try:
        with client.start_as_current_observation(
            name="memory-chat",
            as_type="chain",
            trace_context={"trace_id": tid},
            input=root_input,
            metadata={
                "requestId": request_id,
                "source": source,
                "genProvider": config.GEN_PROVIDER,
                "embedProvider": config.EMBED_PROVIDER,
            },
        ) as root:
            with propagate_attributes(
                user_id=email,
                session_id=session_id,
                metadata={"requestId": request_id, "source": source},
                tags=["memory-chat", "rag", f"source:{source}"],
                trace_name="memory-chat",
            ):
                yield root
    except Exception as exc:
        _log.warning("Langfuse chat_trace failed open: %s", exc)
        yield None


@contextmanager
def observation(
    parent: Any,
    *,
    name: str,
    as_type: str = "span",
    input: Any = None,
    model: str | None = None,
    metadata: dict | None = None,
) -> Iterator[Any]:
    """Child observation; no-op when parent is None / tracing off."""
    if parent is None:
        yield None
        return
    try:
        kwargs: dict[str, Any] = {
            "name": name,
            "as_type": as_type,
            "input": input,
            "metadata": metadata or {},
        }
        if model:
            kwargs["model"] = model
        with parent.start_as_current_observation(**kwargs) as child:
            yield child
    except Exception as exc:
        _log.warning("Langfuse observation %s failed open: %s", name, exc)
        yield None


def update_observation(obs: Any, **kwargs: Any) -> None:
    if obs is None:
        return
    try:
        obs.update(**kwargs)
    except Exception as exc:
        _log.warning("Langfuse update failed: %s", exc)


def score_feedback(
    *,
    request_id: str,
    rating: int,
    comment: str = "",
) -> None:
    """Map thumbs (±1) onto the chat trace seeded from request_id."""
    client = get_client()
    if client is None:
        return
    try:
        client.create_score(
            name="user-thumbs",
            value=1 if rating > 0 else 0,
            data_type="BOOLEAN",
            trace_id=trace_id_for_request(request_id),
            comment=comment or None,
            metadata={"requestId": request_id, "rating": rating},
        )
        client.flush()
    except Exception as exc:
        _log.warning("Langfuse score_feedback failed: %s", exc)


disabled_span = nullcontext
