"""The store-or-recall engine — the core loop behind POST /api/memory/chat.

Per message: classify intent, then either embed+store a new fact or retrieve+
answer a question. Both paths persist to the chat history.
"""
from __future__ import annotations

import uuid

from . import db
from .embeddings import embed
from .generation import classify_and_normalize, generate_answer
from .retrieval import retrieve_relevant_memories
from ..prompts import store as prompt_store


async def store_fact(email: str, fact: str, source: str = "chat") -> dict:
    """Embed and persist a single memory. Returns the stored row."""
    embedding = await embed(fact)
    return await db.insert_memory(str(uuid.uuid4()), email, fact, embedding, source)


async def handle_message(
    email: str, message: str, session_id: str, source: str = "chat"
) -> dict:
    """Route one chat message. Returns { answer, action, sources, sessionId }."""
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in await db.get_chat_history(email, session_id)
    ]

    classifier_prompt = await prompt_store.get_active("memory.classifier")
    route = await classify_and_normalize(message, classifier_prompt)

    if route["action"] == "store" and route["fact"]:
        stored = await store_fact(email, route["fact"], source)
        answer = f"Got it — I'll remember that: {stored['content']}"
        action, sources = "stored", []
    else:
        memories = await retrieve_relevant_memories(email, message, top_k=6)
        answer_prompt = await prompt_store.get_active("memory.answer")
        result = await generate_answer(message, memories, history, answer_prompt)
        answer, sources = result["answer"], result["sources"]
        action = "recalled"

    await db.save_chat_message(str(uuid.uuid4()), email, session_id, "user", message)
    await db.save_chat_message(
        str(uuid.uuid4()), email, session_id, "assistant", answer, sources
    )

    return {"answer": answer, "action": action, "sources": sources, "sessionId": session_id}
