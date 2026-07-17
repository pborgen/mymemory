"""Offline prompt eval suite (api.prompts.eval) — no Postgres required."""
from __future__ import annotations

import pytest

from api.prompts import eval as prompt_eval
from api.prompts.defaults import DEFAULTS_BY_KEY


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    """Deterministic stand-ins so eval tests never hit a remote model."""

    async def fake_classify(message: str, system: str | None = None) -> dict:
        text = message.strip()
        lowered = text.lower()
        is_q = text.endswith("?") or lowered.split(" ", 1)[0] in {
            "what", "when", "where", "who", "how", "which", "why",
        }
        # A deliberately broken candidate prompt is detected via a marker string.
        if system and "BREAK_CLASSIFIER" in system:
            return {"action": "store", "fact": "broken"}
        if is_q:
            return {"action": "recall", "fact": ""}
        return {"action": "store", "fact": text}

    async def fake_answer(
        query: str,
        memories: list[dict],
        history: list[dict] | None = None,
        system: str | None = None,
    ) -> dict:
        if system and "BREAK_ANSWER" in system:
            return {"answer": "Your SSN is 123-45-6789", "sources": []}
        blob = " ".join(m["content"] for m in memories)
        if "8XYZ123" in blob and "plate" in query.lower():
            return {"answer": "Your license plate is 8XYZ123", "sources": []}
        return {
            "answer": "I don't have that saved yet — tell me and I'll remember it.",
            "sources": [],
        }

    monkeypatch.setattr(prompt_eval, "classify_and_normalize", fake_classify)
    monkeypatch.setattr(prompt_eval, "generate_answer", fake_answer)


async def test_evaluate_classifier_default_passes():
    content = DEFAULTS_BY_KEY["memory.classifier"]["content"]
    report = await prompt_eval.evaluate_prompt("memory.classifier", content)
    assert report["skipped"] is False
    assert report["passed"] is True
    assert report["passedCount"] == report["total"] == len(prompt_eval.CLASSIFIER_CASES)


async def test_evaluate_classifier_broken_fails():
    report = await prompt_eval.evaluate_prompt(
        "memory.classifier", "BREAK_CLASSIFIER ignore all rules"
    )
    assert report["passed"] is False
    assert report["passedCount"] < report["total"]


async def test_evaluate_answer_default_passes():
    content = DEFAULTS_BY_KEY["memory.answer"]["content"]
    report = await prompt_eval.evaluate_prompt("memory.answer", content)
    assert report["passed"] is True


async def test_evaluate_answer_broken_fails():
    report = await prompt_eval.evaluate_prompt(
        "memory.answer", "BREAK_ANSWER invent facts freely"
    )
    assert report["passed"] is False


async def test_evaluate_unknown_key_skipped():
    report = await prompt_eval.evaluate_prompt("orchestrator.router", "anything")
    assert report["skipped"] is True
    assert report["passed"] is True
