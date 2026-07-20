"""Unit tests for the remember-gate (what is worth storing)."""
from __future__ import annotations

from api.memory import remember_gate as rg


def test_obvious_chat_greetings():
    assert rg.is_obvious_chat("hi")
    assert rg.is_obvious_chat("Hello!")
    assert rg.is_obvious_chat("Hello, how can I assist you today?")
    assert rg.is_obvious_chat("thanks")
    assert rg.is_obvious_chat("how are you?")


def test_not_chat_durable_facts():
    assert not rg.is_obvious_chat("My car license plate is 8XYZ123")
    assert not rg.is_obvious_chat("Jenna's birthday is March 3")
    assert not rg.is_obvious_chat("What's my license plate?")


def test_durable_fact_gate():
    assert rg.looks_like_durable_fact("The user's car license plate is 8XYZ123")
    assert rg.looks_like_durable_fact("My preferred name is OrbitFox")
    assert not rg.looks_like_durable_fact("Hello, how can I assist you today?")
    assert not rg.looks_like_durable_fact("hi")
    assert rg.gate_store_fact("Hello, how can I assist you today?") == "not_durable_fact"
    assert rg.gate_store_fact("My wifi password is hunter2") is None


def test_resolve_route_upgrades_durable_statements():
    # Small models often mis-label preferences as recall/chat.
    assert rg.resolve_route(
        "My preferred coffee order is oat latte.",
        {"action": "recall", "fact": ""},
    )["action"] == "store"
    assert rg.resolve_route(
        "Hello, how can I assist you today?",
        {"action": "store", "fact": "Hello, how can I assist you today?"},
    )["action"] == "chat"
    assert rg.resolve_route(
        "What's my coffee order?",
        {"action": "store", "fact": "coffee"},
    )["action"] == "recall"
