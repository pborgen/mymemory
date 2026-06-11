"""Generation — Claude on AWS Bedrock for routing and answering.

Two LLM calls live here:
  - classify_and_normalize(message): decide whether the message is a fact to
    STORE or a question to RECALL, and (for STORE) rewrite it as a clean,
    self-contained statement worth embedding.
  - generate_answer(query, memories, history): answer a question grounded ONLY
    in the user's retrieved memories.

Uses the anthropic SDK's AnthropicBedrock client; credentials resolve via the
standard AWS chain.
"""
from __future__ import annotations

import asyncio
import json

from anthropic import AnthropicBedrock

from .. import config

_client = AnthropicBedrock(aws_region=config.AWS_REGION)
MODEL_ID = config.RAG_MODEL_ID

_ROUTER_SYSTEM = """You route messages for a personal memory assistant. The user \
either tells you a fact to remember about their life, or asks a question to \
recall something they told you earlier.

Respond with ONLY a JSON object, no prose, in this exact shape:
{"action": "store" | "recall", "fact": "<string>"}

Rules:
- "store" — the message states information to remember (e.g. "my car plate is \
8XYZ123", "Jenna's birthday is March 3"). Set "fact" to a clean, self-contained \
third-person-or-first-person statement capturing the information, expanding \
pronouns and context so it stands alone. Keep the user's own values verbatim.
- "recall" — the message asks for information or is a question (e.g. "what's my \
license plate?", "when is Jenna's birthday?"). Set "fact" to "".
- If ambiguous, prefer "recall" only when it is clearly a question; otherwise "store"."""

_ANSWER_SYSTEM = """You are a personal memory assistant. You answer the user's \
question using ONLY the memories provided as context — things the user told you \
earlier.

RULES:
- Base your answer ONLY on the provided memories. Never invent or guess facts.
- If the memories don't contain the answer, say you don't have that saved yet, \
and briefly suggest they tell you so you can remember it.
- Be concise and direct — usually one sentence. Give the value they asked for.
- Do not mention "memories", "context", or "documents" in your wording; just answer naturally."""


def _classify_sync(message: str) -> dict:
    response = _client.messages.create(
        model=MODEL_ID,
        max_tokens=400,
        system=_ROUTER_SYSTEM,
        messages=[{"role": "user", "content": message}],
    )
    first = response.content[0]
    text = first.text if getattr(first, "type", None) == "text" else ""
    try:
        data = json.loads(text.strip())
        action = data.get("action")
        if action not in ("store", "recall"):
            raise ValueError("bad action")
        return {"action": action, "fact": (data.get("fact") or "").strip()}
    except Exception:
        # Fall back to recall so we never silently swallow a real question.
        return {"action": "recall", "fact": ""}


async def classify_and_normalize(message: str) -> dict:
    return await asyncio.to_thread(_classify_sync, message)


def _answer_sync(query: str, memories: list[dict], history: list[dict]) -> dict:
    context_block = "\n".join(
        f"- {m['content']} (saved {m['createdAt']:%Y-%m-%d})"
        if hasattr(m.get("createdAt"), "strftime")
        else f"- {m['content']}"
        for m in memories
    ) or "(no saved memories matched this question)"

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append(
        {
            "role": "user",
            "content": (
                "Here are the user's saved memories that may be relevant:\n\n"
                f"{context_block}\n\n"
                "---\n\n"
                f"Answer this question using only the memories above:\n{query}"
            ),
        }
    )

    response = _client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=_ANSWER_SYSTEM,
        messages=messages,
    )
    first = response.content[0]
    answer = first.text if getattr(first, "type", None) == "text" else ""

    sources = [
        {"id": m["id"], "content": m["content"], "similarity": m["similarity"]}
        for m in memories
    ]
    return {"answer": answer, "sources": sources}


async def generate_answer(
    query: str, memories: list[dict], history: list[dict] | None = None
) -> dict:
    return await asyncio.to_thread(_answer_sync, query, memories, history or [])
