"""Remember-gate: decide whether a message/fact is worth storing.

Two layers (defense in depth):

1. Cheap heuristics — catch greetings / assistant boilerplate before or after
   the LLM classifier so a small local model can't pollute the memory store.
2. Classifier prompt (store | recall | chat) — semantic judgment for the rest.

Only *durable personal facts* should become memories (preferences, IDs,
contacts, dates, loan notes, etc.). Chitchat and meta conversation must not.
"""
from __future__ import annotations

import re

# Exact / near-exact chat openers (normalized).
_CHAT_EXACT = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "thanks",
        "thank you",
        "thank you!",
        "thanks!",
        "ok",
        "okay",
        "sure",
        "cool",
        "great",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "how's it going",
        "how are you?",
        "how's it going?",
    }
)

# Substrings that almost never belong in a personal memory.
_CHAT_PHRASES = (
    "how can i assist",
    "how can i help",
    "how may i help",
    "what can i do for you",
    "nice to meet you",
    "you're welcome",
    "good to see you",
    "let me know if you need",
    "i am an ai",
    "i'm an ai",
    "as an ai",
    "how do you work",
    "what can you do",
    "who are you",
)

# Weak signals that something might be a durable fact (not required alone).
_FACT_CUES = (
    "my ",
    "i am ",
    "i'm ",
    "i live",
    "i work",
    "birthday",
    "anniversary",
    "password",
    "license",
    "plate",
    "email",
    "phone",
    "address",
    "loan",
    "rate lock",
    "underwriter",
    "prefer",
    "allergy",
    "allergic",
    "spouse",
    "wife",
    "husband",
    "kid",
    "son",
    "daughter",
    "dog",
    "cat",
    "named ",
    "number is",
    "is called",
)

_ASSISTANT_BOILERPLATE = re.compile(
    r"\b(how can i (assist|help)|what can i (do|help)|how may i help)\b",
    re.I,
)

CHAT_REPLY = (
    "Hi — I only save lasting facts about you (preferences, contacts, dates, "
    "IDs, notes). Tell me something like that to remember, or ask me to recall "
    "what you've already saved."
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_obvious_chat(message: str) -> bool:
    """True for greetings / thanks / assistant-style small talk (no LLM needed)."""
    n = _normalize(message)
    if not n:
        return True
    # Strip trailing punctuation for exact match.
    bare = n.rstrip("!?.")
    if bare in _CHAT_EXACT or n in _CHAT_EXACT:
        return True
    if any(p in n for p in _CHAT_PHRASES):
        return True
    # Very short non-question with no fact cues → chat.
    if len(n) < 24 and "?" not in n and not any(c in n for c in _FACT_CUES):
        words = bare.split()
        if len(words) <= 4 and not re.search(r"\d", n):
            return True
    return False


def looks_like_durable_fact(fact: str) -> bool:
    """Post-classifier gate: reject store payloads that aren't lasting personal info."""
    n = _normalize(fact)
    if not n or len(n) < 8:
        return False
    if is_obvious_chat(fact):
        return False
    if _ASSISTANT_BOILERPLATE.search(fact):
        return False
    # Must have some substance: a cue, a digit, or a reasonably specific phrase.
    if any(c in n for c in _FACT_CUES):
        return True
    if re.search(r"\d", n):
        return True
    # Proper-noun-ish tokens (capitalized in original) + length
    caps = re.findall(r"\b[A-Z][a-z]{2,}\b", fact or "")
    if len(caps) >= 1 and len(n) >= 16:
        return True
    return False


def gate_store_fact(fact: str) -> str | None:
    """Return None if `fact` may be stored; otherwise a chat-style refusal reason code."""
    if looks_like_durable_fact(fact):
        return None
    return "not_durable_fact"


def is_question(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if text.endswith("?"):
        return True
    first = text.lower().split(" ", 1)[0]
    return first in {
        "what", "when", "where", "who", "how", "which", "why",
        "is", "are", "do", "does", "did", "can", "could", "list",
        "tell", "remind", "recall",
    }


def resolve_route(message: str, route: dict) -> dict:
    """Apply remember-gate heuristics on top of the LLM classifier output.

    - Obvious chat → chat
    - Clear durable statement → store (even if the LLM said recall/chat)
    - Store without a durable fact → chat
    """
    action = (route or {}).get("action") or "chat"
    fact = ((route or {}).get("fact") or "").strip()

    if is_obvious_chat(message):
        return {"action": "chat", "fact": ""}

    if is_question(message):
        return {"action": "recall", "fact": ""}

    # Statements that look like lasting personal info should store.
    if looks_like_durable_fact(message):
        return {"action": "store", "fact": fact or message.strip()}

    if action == "store":
        candidate = fact or message.strip()
        if gate_store_fact(candidate) is not None:
            return {"action": "chat", "fact": ""}
        return {"action": "store", "fact": candidate}

    if action == "recall":
        return {"action": "recall", "fact": ""}

    return {"action": "chat", "fact": ""}
