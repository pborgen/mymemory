"""The store-or-recall engine — the core loop behind POST /api/memory/chat.

Per message: classify intent, then either embed+store a new fact or retrieve+
answer a question. Both paths persist to the chat history.

Every turn:
  - runs hard guardrails (input / PII / retrieval floor / output groundedness)
  - pins prompt versions
  - records a request_id + stage timings (observability)
  - optionally emits a Langfuse trace (classify / retrieve / generate spans)
  - stores a debug envelope on the assistant message meta
"""
from __future__ import annotations

import re
import uuid

from . import db
from . import guardrails as gr
from . import remember_gate as rg
from .embeddings import embed
from .generation import classify_and_normalize, generate_answer
from .retrieval import retrieve_relevant_memories
from .. import config
from .. import langfuse_tracing as lf
from .. import observability as obs
from ..prompts import store as prompt_store


def _pin(resolved: dict) -> dict:
    """Slim version pointer safe to return/store (no full prompt text)."""
    return {
        "version": resolved["version"],
        "versionId": resolved["versionId"],
        "source": resolved["source"],
    }


async def store_fact(
    email: str,
    fact: str,
    source: str = "chat",
    *,
    source_uri: str = "",
    pipeline_version: str = "",
) -> dict:
    """Embed and persist a single memory with governance tags (+ optional lineage)."""
    embedding = await embed(fact)
    tags, sensitivity = gr.classify_content_tags(fact)
    return await db.insert_memory(
        str(uuid.uuid4()),
        email,
        fact,
        embedding,
        source,
        pii_tags=tags,
        sensitivity=sensitivity,
        source_uri=source_uri,
        pipeline_version=pipeline_version,
    )


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
    langfuse_trace_id = (
        lf.trace_id_for_request(request_id) if lf.enabled() else None
    )
    debug = {
        "requestId": request_id,
        "langfuseTraceId": langfuse_trace_id,
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
    # Append-only governance trail (who stored/recalled/blocked what).
    try:
        await db.write_audit(
            email,
            action,
            memory_id=memory_ids[0] if len(memory_ids) == 1 else None,
            request_id=request_id,
            detail={
                "guardrail": guardrail or None,
                "memoryIds": memory_ids,
                "emptyRetrieval": empty_retrieval,
                "sessionId": session_id,
                "sensitivity": None,
            },
        )
    except Exception:
        pass
    if lf.enabled():
        lf.flush()
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
        "langfuseTraceId": langfuse_trace_id,
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

    with lf.chat_trace(
        request_id=request_id,
        email=email,
        session_id=session_id,
        message=message,
        source=source,
    ) as root:
        try:
            return await _handle_message_traced(
                email=email,
                message=message,
                session_id=session_id,
                source=source,
                request_id=request_id,
                total=total,
                timings=timings,
                prompt_versions=prompt_versions,
                root=root,
            )
        except Exception as exc:
            timings["total"] = total.stop()
            error = str(exc)
            lf.update_observation(
                root,
                output={"error": error},
                level="ERROR",
                status_message=error,
            )
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


async def _handle_message_traced(
    *,
    email: str,
    message: str,
    session_id: str,
    source: str,
    request_id: str,
    total: obs.Timer,
    timings: dict[str, int],
    prompt_versions: dict,
    root: object | None,
) -> dict:
    # ── 1. Input guardrails ───────────────────────────────────────────
    inbound = gr.check_input(message)
    if inbound.blocked:
        timings["total"] = total.stop()
        with lf.observation(
            root,
            name="block-input",
            as_type="guardrail",
            input=[{"role": "user", "content": message}],
            metadata={"reason": inbound.reason},
        ) as g:
            lf.update_observation(
                g, output={"blocked": True, "reason": inbound.reason}
            )
        lf.update_observation(
            root,
            output=[
                {"role": "assistant", "content": inbound.message},
            ],
            metadata={"action": "blocked", "guardrail": inbound.reason},
        )
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
    # Cheap pre-filter: never call the classifier for obvious chitchat.
    if rg.is_obvious_chat(message):
        timings["classify"] = t.stop()
        timings["total"] = total.stop()
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": rg.CHAT_REPLY}],
            metadata={"action": "chat", "reason": "obvious_chat"},
        )
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=rg.CHAT_REPLY,
            action="chat",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=[],
        )

    classifier = await prompt_store.resolve_active("memory.classifier")
    prompt_versions = {"memory.classifier": _pin(classifier)}
    # OpenAI drop-in auto-creates a generation; avoid a duplicate manual span.
    if lf.uses_openai_generation_integration():
        route = await classify_and_normalize(
            message, classifier["content"], observation_name="classify-intent"
        )
    else:
        with lf.observation(
            root,
            name="classify-intent",
            as_type="generation",
            model=lf.gen_model_name(),
            input=[{"role": "user", "content": message}],
            metadata={"promptVersion": prompt_versions["memory.classifier"]},
        ) as gen:
            route = await classify_and_normalize(
                message, classifier["content"], observation_name="classify-intent"
            )
            lf.update_observation(gen, output=route)
    timings["classify"] = t.stop()

    route = rg.resolve_route(message, route)

    if route["action"] == "chat":
        timings["total"] = total.stop()
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": rg.CHAT_REPLY}],
            metadata={"action": "chat"},
        )
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=rg.CHAT_REPLY,
            action="chat",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=[],
        )

    if route["action"] == "store" and route["fact"]:
        # ── Store PII policy ──────────────────────────────────────────
        pii = gr.check_store_pii(route["fact"], message)
        if pii.blocked:
            timings["total"] = total.stop()
            with lf.observation(
                root,
                name="block-pii-store",
                as_type="guardrail",
                metadata={"reason": pii.reason},
            ) as g:
                lf.update_observation(g, output={"blocked": True})
            lf.update_observation(
                root,
                output=[{"role": "assistant", "content": pii.message}],
                metadata={"action": "blocked", "guardrail": pii.reason},
            )
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
            fact = re_sub_confirm(fact)
        with lf.observation(
            root,
            name="embed-memory",
            as_type="embedding",
            model=lf.embed_model_name(),
            input={"text": fact},
            metadata={"source": source},
        ) as emb:
            stored = await store_fact(email, fact, source)
            lf.update_observation(
                emb,
                output={
                    "memoryId": stored["id"],
                    "piiTags": stored.get("piiTags"),
                    "sensitivity": stored.get("sensitivity"),
                },
            )
        timings["embed"] = t.stop()
        memory_ids = [stored["id"]]
        answer = f"Got it — I'll remember that: {stored['content']}"
        timings["total"] = total.stop()
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": answer}],
            metadata={"action": "stored", "memoryIds": memory_ids},
        )
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action="stored",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=memory_ids,
        )

    # ── Retrieval floor (authz already via email scope) ───────────
    t = obs.Timer()
    with lf.observation(
        root,
        name="retrieve-context",
        as_type="retriever",
        input={"query": message, "topK": 6},
        metadata={"minSimilarity": config.RETRIEVAL_MIN_SIMILARITY},
    ) as ret:
        memories = await retrieve_relevant_memories(
            email,
            message,
            top_k=6,
            min_similarity=config.RETRIEVAL_MIN_SIMILARITY,
        )
        lf.update_observation(
            ret,
            output={
                "count": len(memories),
                "memoryIds": [str(m["id"]) for m in memories],
                "similarities": [m.get("similarity") for m in memories],
            },
        )
    timings["retrieve"] = t.stop()
    empty_retrieval = len(memories) == 0
    memory_ids = [str(m["id"]) for m in memories]

    if empty_retrieval:
        timings["total"] = total.stop()
        with lf.observation(
            root,
            name="block-empty-retrieval",
            as_type="guardrail",
        ) as g:
            lf.update_observation(g, output={"blocked": True})
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": gr.REFUSAL_NO_MEMORY}],
            metadata={"action": "blocked", "guardrail": "empty_retrieval"},
        )
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
    if lf.uses_openai_generation_integration():
        result = await generate_answer(
            message,
            memories,
            history,
            answer_prompt["content"],
            observation_name="generate-response",
        )
    else:
        with lf.observation(
            root,
            name="generate-response",
            as_type="generation",
            model=lf.gen_model_name(),
            input=[{"role": "user", "content": message}],
            metadata={
                "promptVersion": prompt_versions["memory.answer"],
                "memoryCount": len(memories),
            },
        ) as gen:
            result = await generate_answer(
                message,
                memories,
                history,
                answer_prompt["content"],
                observation_name="generate-response",
            )
            lf.update_observation(
                gen,
                output=[{"role": "assistant", "content": result["answer"]}],
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
        with lf.observation(
            root,
            name="block-ungrounded-output",
            as_type="guardrail",
            metadata={"reason": grounded.reason},
        ) as g:
            lf.update_observation(g, output={"blocked": True})
        answer = grounded.message
        sources = []
        action = "blocked"
        guardrail = grounded.reason
    else:
        action = "recalled"
        guardrail = ""

    timings["total"] = total.stop()
    lf.update_observation(
        root,
        output=[{"role": "assistant", "content": answer}],
        metadata={
            "action": action,
            "memoryIds": memory_ids,
            "guardrail": guardrail or None,
        },
    )
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


def re_sub_confirm(fact: str) -> str:
    """Remove a leading CONFIRM_SENSITIVE token from a normalized fact if present."""
    return re.sub(
        r"^\s*CONFIRM_SENSITIVE[:\s-]*", "", fact, flags=re.IGNORECASE
    ).strip() or fact
