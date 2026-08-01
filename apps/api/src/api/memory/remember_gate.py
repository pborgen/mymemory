"""Remember-gate: decide whether a message/fact is worth storing.

Two layers (defense in depth):

1. Cheap heuristics — catch greetings / assistant boilerplate / forget-last
   before or after the LLM classifier so a small local model can't pollute
   the memory store (or miss an undo).
2. Classifier prompt (store | recall | chat | forget) — semantic judgment
   for the rest.

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
    "IDs, notes). Tell me something like that to remember, ask me to recall "
    "what you've already saved, or say “forget the last memory” to undo the "
    "most recent save."
)

# "Forget the last thing you stored", "delete my last memory", "undo that save".
_FORGET_LAST_RE = re.compile(
    r"\b(forget|delete|remove|undo|erase)\b"
    r".{0,48}\b(last|previous|most\s+recent)\b",
    re.I | re.DOTALL,
)
_FORGET_JUST_RE = re.compile(
    r"\b(forget|delete|remove|undo|erase)\b"
    r".{0,48}\b(just\s+(stored|saved|remembered)|"
    r"you\s+just\s+(stored|saved|remembered))\b",
    re.I | re.DOTALL,
)
# "Forget my wifi password" / "delete the old address" (not last-memory undo).
_FORGET_TOPIC_RE = re.compile(
    r"^\s*(please\s+)?(forget|delete|remove|erase)\s+(my|the|about\s+my|about\s+the)?\s*(.+?)\s*$",
    re.I,
)
_EDIT_RE = re.compile(
    r"\b(actually|correction:|correct that|change my|change the|"
    r"update my|update the|it'?s actually|no,? it'?s)\b",
    re.I,
)
_REMIND_RE = re.compile(
    r"^\s*remind me(?:\s+to)?[:\s]+(.+)$",
    re.I,
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


def is_forget_last(message: str) -> bool:
    """True when the user asks to undo / delete the most recently stored memory.

    Requires an explicit "last/previous/…" or "just stored" cue so we don't
    treat "forget my wifi password" (delete-by-content) as this path.
    """
    text = (message or "").strip()
    if not text:
        return False
    return bool(_FORGET_LAST_RE.search(text) or _FORGET_JUST_RE.search(text))


def forget_topic_query(message: str) -> str | None:
    """Return the topic phrase for a topic-delete, or None if not that intent."""
    text = (message or "").strip()
    if not text or is_forget_last(text):
        return None
    m = _FORGET_TOPIC_RE.match(text)
    if not m:
        return None
    topic = (m.group(4) or "").strip().rstrip(".!?")
    if not topic or len(topic) < 3:
        return None
    # Avoid swallowing pure undo verbs with no subject.
    if topic.lower() in {"it", "that", "this", "them", "everything"}:
        return None
    return topic


def is_forget_topic(message: str) -> bool:
    return forget_topic_query(message) is not None


def is_edit_correct(message: str) -> bool:
    text = (message or "").strip()
    if not text or len(text) < 8:
        return False
    return bool(_EDIT_RE.search(text))


def reminder_content(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    m = _REMIND_RE.match(text)
    if not m:
        return None
    content = (m.group(1) or "").strip().rstrip(".!")
    return content or None


def is_reminder(message: str) -> bool:
    return reminder_content(message) is not None


def resolve_route(message: str, route: dict) -> dict:
    """Apply remember-gate heuristics on top of the LLM classifier output.

    - Forget-last → forget (before question routing)
    - Obvious chat → chat
    - Clear durable statement → store (even if the LLM said recall/chat)
    - Store without a durable fact → chat
    """
    action = (route or {}).get("action") or "chat"
    fact = ((route or {}).get("fact") or "").strip()

    if is_forget_last(message):
        return {"action": "forget", "fact": ""}
    topic = forget_topic_query(message)
    if topic:
        return {"action": "forget_topic", "fact": topic}
    if is_reminder(message):
        return {"action": "remind", "fact": reminder_content(message) or ""}
    if is_edit_correct(message):
        return {"action": "update", "fact": fact or message.strip()}
    # Trust LLM "forget" only with an undo verb + last/previous cue.
    if action == "forget":
        n = _normalize(message)
        if any(v in n for v in ("forget", "delete", "remove", "undo", "erase")) and (
            "last" in n or "previous" in n or "just" in n
        ):
            return {"action": "forget", "fact": ""}

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
