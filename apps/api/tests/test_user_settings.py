"""Unit tests for settings merge / patch helpers (no DB)."""
from __future__ import annotations

from api.user_settings import (
    DEFAULT_SETTINGS,
    FEATURE_CATALOG,
    GROUP_ORDER,
    merge_settings,
    ordered_groups,
    patch_settings,
)


def test_merge_fills_defaults():
    merged = merge_settings({})
    assert merged == DEFAULT_SETTINGS
    assert merge_settings(None) == DEFAULT_SETTINGS


def test_merge_preserves_known_bools():
    merged = merge_settings({"quickChips": True, "reminders": 1, "bogus": True})
    assert merged["quickChips"] is True
    assert merged["reminders"] is True
    assert "bogus" not in merged
    assert merged["showSources"] is False


def test_patch_ignores_unknown_keys():
    out = patch_settings({"quickChips": False}, {"quickChips": True, "nope": True})
    assert out["quickChips"] is True
    assert "nope" not in out


def test_catalog_covers_every_default_key():
    keys = {item["key"] for item in FEATURE_CATALOG}
    assert keys == set(DEFAULT_SETTINGS)


def test_group_order_is_stable():
    assert ordered_groups() == GROUP_ORDER
    assert GROUP_ORDER == ["Looking", "Smart chat", "Library", "Devices"]
    for item in FEATURE_CATALOG:
        assert item["group"] in GROUP_ORDER
        assert item.get("subgroup")
