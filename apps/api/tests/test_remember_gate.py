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


def test_forget_last_phrases():
    assert rg.is_forget_last("Forget the last memory you stored")
    assert rg.is_forget_last("please delete the last thing you saved")
    assert rg.is_forget_last("undo what you just remembered")
    assert rg.is_forget_last("Forget the last memories you stored?")
    # Content-specific delete is not this path.
    assert not rg.is_forget_last("forget my wifi password")
    assert not rg.is_forget_last("What's my license plate?")


def test_resolve_route_forget_beats_question():
    assert rg.resolve_route(
        "Forget the last memory?",
        {"action": "recall", "fact": ""},
    )["action"] == "forget"
    # Hallucinated forget on a greeting must not delete memories.
    assert rg.resolve_route(
        "hi",
        {"action": "forget", "fact": ""},
    )["action"] == "chat"


def test_forget_topic_and_edit_and_remind():
    assert rg.forget_topic_query("Forget my wifi password") == "wifi password"
    assert rg.is_edit_correct("Actually my plate is 8XYZ456")
    assert rg.is_edit_correct("Change my wifi password to hunter3")
    assert not rg.is_edit_correct("hi")
    assert rg.reminder_content("remind me to call Jenna") == "call Jenna"
    assert rg.reminder_content("remind me: pick up dry cleaning") == (
        "pick up dry cleaning"
    )
    assert rg.resolve_route(
        "Forget my wifi password",
        {"action": "chat", "fact": ""},
    )["action"] == "forget_topic"
    assert rg.resolve_route(
        "Actually my plate is 8XYZ456",
        {"action": "store", "fact": "My plate is 8XYZ456"},
    )["action"] == "update"
    assert rg.resolve_route(
        "remind me to call Jenna",
        {"action": "chat", "fact": ""},
    )["action"] == "remind"
