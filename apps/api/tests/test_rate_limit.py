"""Prod config guard + in-process rate limiter (no Postgres required)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api import config
from api.rate_limit import SlidingWindowLimiter


def test_validate_public_config_ok(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH_HEADERS", False)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
    monkeypatch.setattr(config, "CORS_ORIGINS", "https://app.example.com")
    config.validate_public_config()  # does not raise


def test_validate_public_config_rejects_dev_headers(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH_HEADERS", True)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
    monkeypatch.setattr(config, "CORS_ORIGINS", "https://app.example.com")
    with pytest.raises(RuntimeError, match="ALLOW_DEV_AUTH_HEADERS"):
        config.validate_public_config()


def test_validate_public_config_rejects_open_cors(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH_HEADERS", False)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
    monkeypatch.setattr(config, "CORS_ORIGINS", "")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        config.validate_public_config()


def test_cors_origin_list_parses(monkeypatch):
    monkeypatch.setattr(
        config, "CORS_ORIGINS", "https://a.example.com, https://b.example.com"
    )
    assert config.cors_origin_list() == [
        "https://a.example.com",
        "https://b.example.com",
    ]


@pytest.mark.asyncio
async def test_sliding_window_enforces_limit():
    lim = SlidingWindowLimiter()
    await lim.hit("u", limit=2, window_sec=60)
    await lim.hit("u", limit=2, window_sec=60)
    with pytest.raises(HTTPException) as exc:
        await lim.hit("u", limit=2, window_sec=60)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_sliding_window_zero_disables():
    lim = SlidingWindowLimiter()
    for _ in range(5):
        await lim.hit("u", limit=0, window_sec=60)
