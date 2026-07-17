"""The store-or-recall engine — the core loop behind POST /api/memory/chat.

Per message: classify intent, then either embed+store a new fact or retrieve+
answer a question. Both paths persist to the chat history.

Every turn:
  - runs hard guardrails (input / PII / retrieval floor / output groundedness)
  - pins prompt versions
  - records a request_id + stage timings (observability)
  - stores a debug envelope on the assistant message meta
"""
from __future__ import annotations

import re
import uuid

from . import db
from . import guardrails as gr
from .embeddings import embed
from .generation import classify_and_normalize, generate_answer
from .retrieval import retrieve_relevant_memories
from .. import config
from .. import observability as obs
from ..prompts import store as prompt_store


def _pin(resolved: dict) -> dict:
    """Slim version pointer safe to return/store (no full prompt text)."""
    return {
        "version": resolved["version"],
        "versionId": resolved["versionId"],
        "source": resolved["source"],
    }


async def store_fact(email: str, fact: str, source: str = "chat") -> dict:
    """Embed and persist a single memory. Returns the stored row."""
    embedding = await embed(fact)
    return await db.insert_memory(str(uuid.uuid4()), email, fact, embedding, source)


async def _finish(
    *,
    email: str,
    session_id: str,
    message: str,
    answer: str,
    action: str,
    sources: list,
    request_id: str,
    prompt_versions: dict,
    timings: dict[str, int],
    empty_retrieval: bool,
    memory_ids: list[str],
    guardrail: str = "",
) -> dict:
    debug = {
        "requestId": request_id,
        "promptVersions": prompt_versions,
        "timingsMs": timings,
        "memoryIds": memory_ids,
        "emptyRetrieval": empty_retrieval,
        "guardrail": guardrail or None,
        "providers": {
            "gen": config.GEN_PROVIDER,
            "embed": config.EMBED_PROVIDER,
        },
    }
    obs.log_event(
        "memory.chat",
        action=action,
        sessionId=session_id,
        email=email,
        emptyRetrieval=empty_retrieval,
        memoryIds=memory_ids,
        timingsMs=timings,
        promptVersions=prompt_versions,
        guardrail=guardrail or None,
    )
    await db.save_chat_message(str(uuid.uuid4()), email, session_id, "user", message)
    await db.save_chat_message(
        str(uuid.uuid4()),
        email,
        session_id,
        "assistant",
        answer,
        sources,
        meta=debug,
    )
    await obs.record_chat_metric(
        request_id=request_id,
        email=email,
        session_id=session_id,
        action=action,
        empty_retrieval=empty_retrieval,
        timings=timings,
        memory_count=len(memory_ids),
        prompt_versions=prompt_versions,
        error=guardrail,
    )
    return {
        "answer": answer,
        "action": action,
        "sources": sources,
        "sessionId": session_id,
        "promptVersions": prompt_versions,
        "requestId": request_id,
        "timingsMs": timings,
        "emptyRetrieval": empty_retrieval,
        "guardrail": guardrail or None,
    }


async def handle_message(
    email: str, message: str, session_id: str, source: str = "chat"
) -> dict:
    """Route one chat message with hard guardrails around store/recall."""
    request_id = obs.get_request_id() or obs.new_request_id()
    obs.set_request_id(request_id)
    total = obs.Timer()
    timings: dict[str, int] = {
        "classify": 0,
        "embed": 0,
        "retrieve": 0,
        "generate": 0,
        "total": 0,
    }
    prompt_versions: dict = {}
    empty_retrieval = False
    memory_ids: list[str] = []

    try:
        # ── 1. Input guardrails ───────────────────────────────────────────
        inbound = gr.check_input(message)
        if inbound.blocked:
            timings["total"] = total.stop()
            obs.log_event(
                "guardrail.blocked",
                reason=inbound.reason,
                email=email,
                sessionId=session_id,
            )
            return await _finish(
                email=email,
                session_id=session_id,
                message=message,
                answer=inbound.message,
                action="blocked",
                sources=[],
                request_id=request_id,
                prompt_versions=prompt_versions,
                timings=timings,
                empty_retrieval=False,
                memory_ids=[],
                guardrail=inbound.reason,
            )

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in await db.get_chat_history(email, session_id)
        ]

        t = obs.Timer()
        classifier = await prompt_store.resolve_active("memory.classifier")
        prompt_versions = {"memory.classifier": _pin(classifier)}
        route = await classify_and_normalize(message, classifier["content"])
        timings["classify"] = t.stop()

        if route["action"] == "store" and route["fact"]:
            # ── Store PII policy ──────────────────────────────────────────
            pii = gr.check_store_pii(route["fact"], message)
            if pii.blocked:
                timings["total"] = total.stop()
                obs.log_event(
                    "guardrail.blocked",
                    reason=pii.reason,
                    email=email,
                    sessionId=session_id,
                )
                return await _finish(
                    email=email,
                    session_id=session_id,
                    message=message,
                    answer=pii.message,
                    action="blocked",
                    sources=[],
                    request_id=request_id,
                    prompt_versions=prompt_versions,
                    timings=timings,
                    empty_retrieval=False,
                    memory_ids=[],
                    guardrail=pii.reason,
                )

            t = obs.Timer()
            fact = route["fact"]
            if message.lstrip().upper().startswith("CONFIRM_SENSITIVE"):
                # Strip the confirmation prefix from what we persist if present in fact.
                fact = re_sub_confirm(fact)
            stored = await store_fact(email, fact, source)
            timings["embed"] = t.stop()
            answer = f"Got it — I'll remember that: {stored['content']}"
            action, sources = "stored", []
        else:
            # ── Retrieval floor (authz already via email scope) ───────────
            t = obs.Timer()
            memories = await retrieve_relevant_memories(
                email,
                message,
                top_k=6,
                min_similarity=config.RETRIEVAL_MIN_SIMILARITY,
            )
            timings["retrieve"] = t.stop()
            empty_retrieval = len(memories) == 0
            memory_ids = [str(m["id"]) for m in memories]

            if empty_retrieval:
                timings["total"] = total.stop()
                obs.log_event(
                    "guardrail.blocked",
                    reason="empty_retrieval",
                    email=email,
                    sessionId=session_id,
                )
                return await _finish(
                    email=email,
                    session_id=session_id,
                    message=message,
                    answer=gr.REFUSAL_NO_MEMORY,
                    action="blocked",
                    sources=[],
                    request_id=request_id,
                    prompt_versions=prompt_versions,
                    timings=timings,
                    empty_retrieval=True,
                    memory_ids=[],
                    guardrail="empty_retrieval",
                )

            t = obs.Timer()
            answer_prompt = await prompt_store.resolve_active("memory.answer")
            prompt_versions["memory.answer"] = _pin(answer_prompt)
            result = await generate_answer(
                message, memories, history, answer_prompt["content"]
            )
            timings["generate"] = t.stop()
            answer, sources = result["answer"], result["sources"]

            # ── Output groundedness gate ──────────────────────────────────
            grounded = gr.check_output_groundedness(answer, memories)
            if grounded.blocked:
                obs.log_event(
                    "guardrail.blocked",
                    reason=grounded.reason,
                    email=email,
                    sessionId=session_id,
                )
                answer = grounded.message
                sources = []
                action = "blocked"
                guardrail = grounded.reason
            else:
                action = "recalled"
                guardrail = ""

            timings["total"] = total.stop()
            return await _finish(
                email=email,
                session_id=session_id,
                message=message,
                answer=answer,
                action=action,
                sources=sources,
                request_id=request_id,
                prompt_versions=prompt_versions,
                timings=timings,
                empty_retrieval=False,
                memory_ids=memory_ids,
                guardrail=guardrail,
            )

        timings["total"] = total.stop()
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action=action,
            sources=sources,
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=memory_ids,
        )
    except Exception as exc:
        timings["total"] = total.stop()
        error = str(exc)
        obs.log_event(
            "memory.chat.error",
            sessionId=session_id,
            email=email,
            error=error,
            timingsMs=timings,
        )
        try:
            await obs.record_chat_metric(
                request_id=request_id,
                email=email,
                session_id=session_id,
                action="error",
                empty_retrieval=False,
                timings=timings,
                memory_count=0,
                prompt_versions={},
                error=error,
            )
        except Exception:
            pass
        raise


def re_sub_confirm(fact: str) -> str:
    """Remove a leading CONFIRM_SENSITIVE token from a normalized fact if present."""
    return re.sub(
        r"^\s*CONFIRM_SENSITIVE[:\s-]*", "", fact, flags=re.IGNORECASE
    ).strip() or fact
