"""Offline prompt eval — golden cases run against candidate prompt text.

Used as an eval-before-activate gate (prompt ops). Suites are keyed by prompt
key; keys without a suite are treated as skipped/passed so orchestrator prompts
can still be edited without a harness.

Classifier cases call `classify_and_normalize` with the candidate system prompt.
Answer cases call `generate_answer` with fixed memories and check groundedness /
refusal heuristics. Integration tests fake those LLM entry points (see conftest).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..memory.generation import classify_and_normalize, generate_answer

# Minimum fraction of cases that must pass to activate (when a suite exists).
PASS_THRESHOLD = 1.0

_REFUSAL_MARKERS = (
    "don't have",
    "do not have",
    "don't know",
    "do not know",
    "not saved",
    "haven't saved",
    "have not saved",
    "no memory",
    "nothing saved",
    "i don't",
    "i do not",
)


def _looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(m in lowered for m in _REFUSAL_MARKERS)


CLASSIFIER_CASES: list[dict[str, Any]] = [
    {
        "id": "store-plate",
        "message": "My car license plate is 8XYZ123",
        "expect_action": "store",
    },
    {
        "id": "store-birthday",
        "message": "Jenna's birthday is March 3",
        "expect_action": "store",
    },
    {
        "id": "recall-plate",
        "message": "What's my license plate?",
        "expect_action": "recall",
    },
    {
        "id": "recall-when",
        "message": "When is Jenna's birthday?",
        "expect_action": "recall",
    },
    {
        "id": "recall-what",
        "message": "what is my wifi password",
        "expect_action": "recall",
    },
]

ANSWER_CASES: list[dict[str, Any]] = [
    {
        "id": "grounded-plate",
        "query": "What is my license plate?",
        "memories": [
            {
                "id": "m1",
                "content": "The user's car license plate is 8XYZ123",
                "similarity": 0.92,
                "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        ],
        "expect_contains": ["8XYZ123"],
    },
    {
        "id": "refuse-missing",
        "query": "What is my social security number?",
        "memories": [
            {
                "id": "m2",
                "content": "The user's car license plate is 8XYZ123",
                "similarity": 0.4,
                "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        ],
        "expect_refusal": True,
    },
]

# prompt key → list of case dicts + which runner to use
_SUITES: dict[str, dict[str, Any]] = {
    "memory.classifier": {"kind": "classifier", "cases": CLASSIFIER_CASES},
    "memory.answer": {"kind": "answer", "cases": ANSWER_CASES},
}


async def _eval_classifier_case(content: str, case: dict) -> dict:
    route = await classify_and_normalize(case["message"], content)
    actual = route.get("action")
    expected = case["expect_action"]
    passed = actual == expected
    return {
        "id": case["id"],
        "passed": passed,
        "detail": f"expected action={expected}, got={actual}",
    }


async def _eval_answer_case(content: str, case: dict) -> dict:
    result = await generate_answer(
        case["query"], case["memories"], history=[], system=content
    )
    answer = (result.get("answer") or "").strip()
    if case.get("expect_refusal"):
        passed = _looks_like_refusal(answer)
        detail = (
            "expected a refusal when memories lack the answer"
            if not passed
            else "refused as expected"
        )
        if not passed:
            detail += f"; answer={answer[:120]!r}"
        return {"id": case["id"], "passed": passed, "detail": detail}

    needles = case.get("expect_contains") or []
    missing = [n for n in needles if n.lower() not in answer.lower()]
    passed = not missing
    detail = (
        "contains expected substrings"
        if passed
        else f"missing {missing}; answer={answer[:120]!r}"
    )
    return {"id": case["id"], "passed": passed, "detail": detail}


async def evaluate_prompt(key: str, content: str) -> dict:
    """Run the golden suite for `key` against candidate `content`.

    Returns:
      {
        key, passed, skipped, threshold, passedCount, total,
        results: [{id, passed, detail}, ...]
      }
    """
    suite = _SUITES.get(key)
    if not suite:
        return {
            "key": key,
            "passed": True,
            "skipped": True,
            "threshold": PASS_THRESHOLD,
            "passedCount": 0,
            "total": 0,
            "results": [],
            "summary": "No eval suite for this prompt key — treated as passed.",
        }

    kind = suite["kind"]
    results: list[dict] = []
    for case in suite["cases"]:
        if kind == "classifier":
            results.append(await _eval_classifier_case(content, case))
        else:
            results.append(await _eval_answer_case(content, case))

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    ratio = (passed_count / total) if total else 1.0
    passed = ratio >= PASS_THRESHOLD
    return {
        "key": key,
        "passed": passed,
        "skipped": False,
        "threshold": PASS_THRESHOLD,
        "passedCount": passed_count,
        "total": total,
        "results": results,
        "summary": (
            f"{passed_count}/{total} cases passed (need ≥ {PASS_THRESHOLD:.0%})"
        ),
    }


def has_suite(key: str) -> bool:
    return key in _SUITES
