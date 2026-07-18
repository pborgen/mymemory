"""Langfuse helpers stay local-friendly (no-op without keys)."""
from __future__ import annotations

from api import langfuse_tracing as lf


def test_langfuse_disabled_without_keys(monkeypatch):
    monkeypatch.setattr("api.config.LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr("api.config.LANGFUSE_SECRET_KEY", "")
    monkeypatch.setattr("api.config.LANGFUSE_ENABLED", False)
    # Reset lazy client
    lf._client = None
    lf._client_checked = False
    assert lf.enabled() is False
    assert lf.get_client() is None
    with lf.chat_trace(
        request_id="00000000-0000-0000-0000-000000000001",
        email="a@b.c",
        session_id="s",
        message="hi",
        source="chat",
    ) as root:
        assert root is None
        with lf.observation(root, name="classify", as_type="generation") as child:
            assert child is None
    lf.score_feedback(request_id="00000000-0000-0000-0000-000000000001", rating=1)


def test_trace_id_deterministic_from_request_id():
    a = lf.trace_id_for_request("550e8400-e29b-41d4-a716-446655440000")
    b = lf.trace_id_for_request("550e8400-e29b-41d4-a716-446655440000")
    c = lf.trace_id_for_request("550e8400-e29b-41d4-a716-446655440001")
    assert a == b
    assert len(a) == 32
    assert a != c
