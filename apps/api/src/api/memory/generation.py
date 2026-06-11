"""Generation — Bedrock Converse API for routing and answering.

Two LLM calls live here:
  - classify_and_normalize(message): decide whether the message is a fact to
    STORE or a question to RECALL, and (for STORE) rewrite it as a clean,
    self-contained statement worth embedding.
  - generate_answer(query, memories, history): answer a question grounded ONLY
    in the user's retrieved memories.

Uses the Bedrock **Converse** API via boto3, which is model-agnostic: the same
code works for Amazon Nova (cheap, the default) and Anthropic Claude — switch by
changing RAG_MODEL_ID. Credentials resolve via the standard AWS chain.
"""
from __future__ import annotations

import asyncio
import json

import boto3

from .. import config

_client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
MODEL_ID = config.RAG_MODEL_ID

_ROUTER_SYSTEM = """You route messages for a personal memory assistant. The user \
either tells you a fact to remember about their life, or asks a question to \
recall something they told you earlier.

Respond with ONLY a JSON object, no prose, no markdown fences, in this exact shape:
{"action": "store" | "recall", "fact": "<string>"}

Rules:
- "store" — the message states information to remember (e.g. "my car plate is \
8XYZ123", "Jenna's birthday is March 3"). Set "fact" to a clean, self-contained \
statement capturing the information, expanding pronouns and context so it stands \
alone. Keep the user's own values verbatim.
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


def _converse(system: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    """One Bedrock Converse round-trip; returns the assistant's text."""
    response = _client.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=messages,
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    parts = response["output"]["message"]["content"]
    return "".join(p.get("text", "") for p in parts).strip()


def _classify_sync(message: str) -> dict:
    text = _converse(
        _ROUTER_SYSTEM,
        [{"role": "user", "content": [{"text": message}]}],
        max_tokens=400,
        temperature=0.0,
    )
    # Models occasionally wrap JSON in ```json fences; strip them.
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
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

    messages = [
        {"role": m["role"], "content": [{"text": m["content"]}]} for m in history
    ]
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Here are the user's saved memories that may be relevant:\n\n"
                        f"{context_block}\n\n"
                        "---\n\n"
                        f"Answer this question using only the memories above:\n{query}"
                    )
                }
            ],
        }
    )

    answer = _converse(_ANSWER_SYSTEM, messages, max_tokens=1024, temperature=0.2)
    sources = [
        {"id": m["id"], "content": m["content"], "similarity": m["similarity"]}
        for m in memories
    ]
    return {"answer": answer, "sources": sources}


async def generate_answer(
    query: str, memories: list[dict], history: list[dict] | None = None
) -> dict:
    return await asyncio.to_thread(_answer_sync, query, memories, history or [])
