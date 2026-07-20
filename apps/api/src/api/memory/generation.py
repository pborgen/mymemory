"""Generation — routing and answering across pluggable chat providers.

Two LLM calls live here:
  - classify_and_normalize(message): decide whether the message is a fact to
    STORE or a question to RECALL, and (for STORE) rewrite it as a clean,
    self-contained statement worth embedding.
  - generate_answer(query, memories, history): answer a question grounded ONLY
    in the user's retrieved memories.

The provider is config.GEN_PROVIDER — "openai" (any OpenAI-compatible server
such as vLLM), "ollama", or "bedrock". Messages are built in the Bedrock
Converse shape ({"role", "content": [{"text": …}]}) and flattened per provider.
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache

import httpx

from .. import config


@lru_cache(maxsize=1)
def _bedrock_client():
    # Imported/created lazily so a non-Bedrock deployment needs no boto3/AWS.
    import boto3

    return boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def _flatten(system: str, messages: list[dict]) -> list[dict]:
    """Convert Converse-shaped messages to plain {role, content} chat turns."""
    chat = [{"role": "system", "content": system}]
    for m in messages:
        text = "".join(part.get("text", "") for part in m.get("content", []))
        chat.append({"role": m["role"], "content": text})
    return chat

_ROUTER_SYSTEM = """You route messages for a personal memory assistant.

Decide ONE action. Respond with ONLY a JSON object (no prose, no markdown):
{"action": "store" | "recall" | "chat", "fact": "<string>"}

## store — ONLY durable personal facts worth saving long-term
Examples: license plate, birthday, preferred name, address, loan number, rate lock,
allergy, wifi password, "my dog is named Rex".
Set "fact" to a clean, self-contained statement (resolve pronouns). Keep values verbatim.

Do NOT store:
- greetings / small talk ("hi", "how are you", "thanks")
- assistant-style phrases ("Hello, how can I assist you today?")
- questions, commands about the app, or meta chat
- fleeting feelings with no lasting detail ("I'm tired")

If unsure whether it is a lasting fact → use "chat", not "store".

## recall — the user is asking for something they may have saved
Examples: "what's my license plate?", "when is Jenna's birthday?"
Set "fact" to "".

## chat — everything else
Greetings, thanks, how-you-work questions, empty chatter. Set "fact" to "".

Default when ambiguous between store and chat: "chat"."""

_ANSWER_SYSTEM = """You are a personal memory assistant. You answer the user's \
question using ONLY the memories provided as context — things the user told you \
earlier.

RULES:
- Base your answer ONLY on the provided memories. Never invent or guess facts.
- If the memories don't contain the answer, say you don't have that saved yet, \
and briefly suggest they tell you so you can remember it.
- Be concise and direct — usually one sentence. Give the value they asked for.
- Do not mention "memories", "context", or "documents" in your wording; just answer naturally."""


# JSON schema the classifier must emit. Passed to the provider as a
# constrained-decoding (guided JSON) hint so small models can't drift off-format.
_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["store", "recall", "chat"]},
        "fact": {"type": "string"},
    },
    "required": ["action", "fact"],
    "additionalProperties": False,
}


def _converse(
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    json_schema: dict | None = None,
    *,
    observation_name: str | None = None,
) -> str:
    """One chat round-trip; returns the assistant's text. Dispatches on
    config.GEN_PROVIDER. `messages` use the Bedrock Converse shape. When
    `json_schema` is given, the output is constrained to that schema on providers
    that support it (openai/vLLM, ollama); bedrock falls back to prompt-only.
    """
    if config.GEN_PROVIDER == "openai":
        return _openai_converse(
            system,
            messages,
            max_tokens,
            temperature,
            json_schema,
            observation_name=observation_name,
        )
    if config.GEN_PROVIDER == "ollama":
        return _ollama_converse(system, messages, max_tokens, temperature, json_schema)
    return _bedrock_converse(system, messages, max_tokens, temperature)


def _openai_client():
    """OpenAI-compatible client; Langfuse drop-in when tracing is enabled."""
    from .. import langfuse_tracing as lf

    if lf.enabled():
        from langfuse.openai import OpenAI
    else:
        from openai import OpenAI

    return OpenAI(
        base_url=config.OPENAI_BASE_URL,
        api_key=config.OPENAI_API_KEY,
        timeout=120.0,
    )


def _openai_converse(
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    json_schema: dict | None = None,
    *,
    observation_name: str | None = None,
) -> str:
    """Chat via OpenAI SDK (Langfuse-wrapped when enabled → tokens/cost auto)."""
    kwargs: dict = {
        "model": config.OPENAI_CHAT_MODEL,
        "messages": _flatten(system, messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_schema is not None:
        # vLLM guided decoding — not part of the OpenAI schema, so use extra_body.
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["extra_body"] = {"guided_json": json_schema}
    if observation_name:
        # Langfuse OpenAI wrapper uses `name` for the generation observation.
        kwargs["name"] = observation_name
    client = _openai_client()
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content if response.choices else ""
    return (content or "").strip()


def _ollama_converse(
    system: str, messages: list[dict], max_tokens: int, temperature: float,
    json_schema: dict | None = None,
) -> str:
    body: dict = {
        "model": config.OLLAMA_CHAT_MODEL,
        "messages": _flatten(system, messages),
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_schema is not None:
        # Ollama accepts a JSON schema (or the literal "json") in `format`.
        body["format"] = json_schema
    response = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/chat",
        json=body,
        timeout=120,
    )
    response.raise_for_status()
    return (response.json().get("message", {}).get("content") or "").strip()


def _bedrock_converse(system: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    response = _bedrock_client().converse(
        modelId=config.RAG_MODEL_ID,
        system=[{"text": system}],
        messages=messages,
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    parts = response["output"]["message"]["content"]
    return "".join(p.get("text", "") for p in parts).strip()


def _classify_sync(
    message: str, system: str, *, observation_name: str = "classify-intent"
) -> dict:
    text = _converse(
        system,
        [{"role": "user", "content": [{"text": message}]}],
        max_tokens=400,
        temperature=0.0,
        json_schema=_CLASSIFY_SCHEMA,
        observation_name=observation_name,
    )
    # Models occasionally wrap JSON in ```json fences; strip them.
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
        action = data.get("action")
        if action not in ("store", "recall", "chat"):
            raise ValueError("bad action")
        return {"action": action, "fact": (data.get("fact") or "").strip()}
    except Exception:
        # Prefer recall for questions; otherwise chat — never invent a store.
        q = message.strip()
        if q.endswith("?") or q.lower().split(" ", 1)[0] in {
            "what", "when", "where", "who", "how", "which", "why",
        }:
            return {"action": "recall", "fact": ""}
        return {"action": "chat", "fact": ""}


async def classify_and_normalize(
    message: str,
    system: str | None = None,
    *,
    observation_name: str = "classify-intent",
) -> dict:
    return await asyncio.to_thread(
        _classify_sync,
        message,
        system or _ROUTER_SYSTEM,
        observation_name=observation_name,
    )


def _answer_sync(
    query: str,
    memories: list[dict],
    history: list[dict],
    system: str,
    *,
    observation_name: str = "generate-response",
) -> dict:
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

    answer = _converse(
        system,
        messages,
        max_tokens=1024,
        temperature=0.2,
        observation_name=observation_name,
    )
    sources = [
        {"id": m["id"], "content": m["content"], "similarity": m["similarity"]}
        for m in memories
    ]
    return {"answer": answer, "sources": sources}


async def generate_answer(
    query: str,
    memories: list[dict],
    history: list[dict] | None = None,
    system: str | None = None,
    *,
    observation_name: str = "generate-response",
) -> dict:
    return await asyncio.to_thread(
        _answer_sync,
        query,
        memories,
        history or [],
        system or _ANSWER_SYSTEM,
        observation_name=observation_name,
    )
