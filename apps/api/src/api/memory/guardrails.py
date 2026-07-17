"""Hard guardrails around the memory chat path (defense in depth).

Soft controls (system prompts, verifier agent) reduce risk but do not enforce
it. These checks are deterministic and fail *closed* on safety:

  1. Input     — length + prompt-injection heuristics
  2. Authz     — already enforced by email-scoped SQL (documented here)
  3. Retrieval — similarity floor; empty → skip generate
  4. Store PII — block SSN / PAN-like values unless explicitly allowed
  5. Output    — cheap groundedness heuristic after generate

Every block should be logged with request_id via the caller (engine).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config

REFUSAL_NO_MEMORY = (
    "I don't have that saved yet — tell me and I'll remember it."
)
REFUSAL_BLOCKED_INPUT = (
    "I can't process that message as written. Please rephrase without "
    "instructions that try to override how I work."
)
REFUSAL_PII_STORE = (
    "I won't store what looks like a Social Security number or payment card "
    "by default. If you still want it saved, send the fact again with "
    "CONFIRM_SENSITIVE at the start of your message."
)
REFUSAL_UNGROUNDED = (
    "I don't have a reliable answer in your saved memories for that."
)

_INJECTION_RE = re.compile(
    r"("
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
    r"|disregard\s+(your|the)\s+(system|rules|instructions)"
    r"|reveal\s+(your\s+)?system\s+prompt"
    r"|dump\s+(all\s+)?(memories|data|secrets)"
    r"|jailbreak"
    r"|you\s+are\s+now\s+dan"
    r")",
    re.IGNORECASE,
)

# US SSN-like and rough payment-card runs (FinServ talking point — not PCI-perfect).
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PAN_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

_REFUSAL_MARKERS = (
    "don't have",
    "do not have",
    "don't know",
    "not saved",
    "haven't saved",
    "have not saved",
    "won't store",
    "can't process",
    "cannot process",
    "no reliable answer",
)


@dataclass(frozen=True)
class GuardDecision:
    """Result of a guardrail check. `blocked` means fail-closed for the caller."""

    blocked: bool
    reason: str = ""  # machine code: input_injection | input_length | pii_store | …
    message: str = ""  # user-facing reply when blocked


def check_input(message: str) -> GuardDecision:
    text = message or ""
    if len(text) > config.GUARDRAIL_MAX_MESSAGE_CHARS:
        return GuardDecision(
            True,
            "input_length",
            f"Message too long (max {config.GUARDRAIL_MAX_MESSAGE_CHARS} characters).",
        )
    if _INJECTION_RE.search(text):
        return GuardDecision(True, "input_injection", REFUSAL_BLOCKED_INPUT)
    return GuardDecision(False)


def detect_sensitive_pii(text: str) -> bool:
    if _SSN_RE.search(text or ""):
        return True
    # Avoid flagging short digit groups; PAN heuristic needs a long digit run.
    digits = re.sub(r"[^\d]", "", text or "")
    if len(digits) >= 13 and _PAN_RE.search(text or ""):
        return True
    return False


def check_store_pii(fact: str, raw_message: str = "") -> GuardDecision:
    """Block store of SSN/PAN-like values unless user prefixed CONFIRM_SENSITIVE."""
    combined = f"{raw_message}\n{fact}"
    if not detect_sensitive_pii(combined):
        return GuardDecision(False)
    if (raw_message or "").lstrip().upper().startswith("CONFIRM_SENSITIVE"):
        return GuardDecision(False)
    return GuardDecision(True, "pii_store", REFUSAL_PII_STORE)


def filter_by_similarity(
    memories: list[dict], min_similarity: float | None = None
) -> list[dict]:
    floor = (
        config.RETRIEVAL_MIN_SIMILARITY
        if min_similarity is None
        else min_similarity
    )
    return [m for m in memories if float(m.get("similarity") or 0) >= floor]


def looks_like_refusal(answer: str) -> bool:
    lowered = (answer or "").lower()
    return any(m in lowered for m in _REFUSAL_MARKERS)


def check_output_groundedness(answer: str, memories: list[dict]) -> GuardDecision:
    """Cheap heuristic: non-refusal answers must share a contentful token with memories.

    Not a full NLI verifier — good interview demo of *hard* post-generation gate.
    """
    if looks_like_refusal(answer):
        return GuardDecision(False)
    if not memories:
        return GuardDecision(True, "ungrounded_output", REFUSAL_UNGROUNDED)

    blob = " ".join(str(m.get("content") or "") for m in memories).lower()
    # Tokens that look like values / words (skip tiny glue words).
    tokens = re.findall(r"[a-z0-9][a-z0-9\-_.]{3,}", (answer or "").lower())
    stop = {
        "that", "this", "with", "from", "your", "have", "been", "were", "what",
        "when", "where", "based", "memories", "memory", "saved", "answer",
    }
    contentful = [t for t in tokens if t not in stop]
    if not contentful:
        return GuardDecision(False)
    if any(t in blob for t in contentful):
        return GuardDecision(False)
    return GuardDecision(True, "ungrounded_output", REFUSAL_UNGROUNDED)
