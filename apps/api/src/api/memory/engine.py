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
from .entities import link_entities_for_memory
from .generation import classify_and_normalize, generate_answer
from .retrieval import retrieve_relevant_memories
from .. import config
from .. import db as api_db
from .. import langfuse_tracing as lf
from .. import observability as obs
from ..prompts import store as prompt_store

_CONFLICT_SIMILARITY = 0.88
_TOPIC_DELETE_SIMILARITY = 0.35


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
    memory_id = str(uuid.uuid4())
    stored = await db.insert_memory(
        memory_id,
        email,
        fact,
        embedding,
        source,
        pii_tags=tags,
        sensitivity=sensitivity,
        source_uri=source_uri,
        pipeline_version=pipeline_version,
    )
    try:
        entities = await link_entities_for_memory(email, memory_id, fact)
        stored["entities"] = entities
    except Exception:
        # Clustering is best-effort — never fail a successful store.
        stored["entities"] = []
    return stored


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
    out = {
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
        "chips": [],
    }
    return out


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
    settings = await api_db.get_user_settings(email)

    # Cheap pre-filters: feature intents / chitchat skip the classifier.
    if rg.is_forget_last(message):
        timings["classify"] = t.stop()
        return await _forget_last_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            settings=settings,
        )

    if settings.get("reminders") and rg.is_reminder(message):
        timings["classify"] = t.stop()
        return await _create_reminder_from_chat(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
        )

    if settings.get("forgetByTopic") and rg.is_forget_topic(message):
        timings["classify"] = t.stop()
        return await _forget_topic_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
        )

    if settings.get("editCorrect") and rg.is_edit_correct(message):
        timings["classify"] = t.stop()
        return await _update_matching_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            settings=settings,
        )

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

    if route["action"] == "forget":
        return await _forget_last_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            settings=settings,
        )

    if route["action"] == "forget_topic" and settings.get("forgetByTopic"):
        return await _forget_topic_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            topic=route.get("fact") or None,
        )

    if route["action"] == "remind" and settings.get("reminders"):
        return await _create_reminder_from_chat(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            content=route.get("fact") or None,
        )

    if route["action"] == "update" and settings.get("editCorrect"):
        return await _update_matching_memory(
            email=email,
            session_id=session_id,
            message=message,
            request_id=request_id,
            total=total,
            timings=timings,
            prompt_versions=prompt_versions,
            root=root,
            settings=settings,
            fact=route.get("fact") or message.strip(),
        )

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

        # Conflict detection: overlapping fact → update the older memory in place.
        if settings.get("conflictDetection"):
            overlaps = await retrieve_relevant_memories(
                email, fact, top_k=3, min_similarity=_CONFLICT_SIMILARITY
            )
            if overlaps:
                old = overlaps[0]
                embedding = await embed(fact)
                updated = await db.update_memory_content(
                    email, str(old["id"]), fact, embedding
                )
                timings["embed"] = t.stop()
                if updated:
                    memory_ids = [updated["id"]]
                    answer = (
                        f"Updated your earlier note — I'll remember: {updated['content']}"
                    )
                    timings["total"] = total.stop()
                    result = await _finish(
                        email=email,
                        session_id=session_id,
                        message=message,
                        answer=answer,
                        action="updated",
                        sources=[],
                        request_id=request_id,
                        prompt_versions=prompt_versions,
                        timings=timings,
                        empty_retrieval=False,
                        memory_ids=memory_ids,
                    )
                    return _with_chips(result, settings, action="updated")

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
        result = await _finish(
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
        return _with_chips(result, settings, action="stored")

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
        if settings.get("timeAwareAnswers") and memories:
            # Prefer newer rows when similarity is close (stable sort: -created, -sim).
            memories = sorted(
                memories,
                key=lambda m: (
                    m.get("createdAt") or 0,
                    float(m.get("similarity") or 0),
                ),
                reverse=True,
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


def _with_chips(result: dict, settings: dict, *, action: str) -> dict:
    if not settings.get("quickChips"):
        return result
    if action in ("stored", "updated"):
        result["chips"] = [
            {"id": "undo", "label": "Undo save"},
            {"id": "ask", "label": "Ask me later"},
        ]
    return result


async def _create_reminder_from_chat(
    *,
    email: str,
    session_id: str,
    message: str,
    request_id: str,
    total: obs.Timer,
    timings: dict[str, int],
    prompt_versions: dict,
    root: object | None,
    content: str | None = None,
) -> dict:
    text = (content or rg.reminder_content(message) or "").strip()
    if not text:
        text = message.strip()
    reminder = await db.insert_reminder(str(uuid.uuid4()), email, text)
    answer = f"Reminder saved: {reminder['content']}. Manage these under Settings."
    timings["total"] = total.stop()
    lf.update_observation(
        root,
        output=[{"role": "assistant", "content": answer}],
        metadata={"action": "reminded", "reminderId": reminder["id"]},
    )
    return await _finish(
        email=email,
        session_id=session_id,
        message=message,
        answer=answer,
        action="reminded",
        sources=[],
        request_id=request_id,
        prompt_versions=prompt_versions,
        timings=timings,
        empty_retrieval=False,
        memory_ids=[],
    )


_STOP_TOPIC = frozenset(
    {
        "a", "an", "the", "my", "me", "please", "forget", "delete", "remove",
        "erase", "about", "that", "this", "from", "your", "you", "saved",
        "memory", "memories",
    }
)


async def _match_topic_memory(email: str, query: str) -> dict | None:
    """Best memory for a topic delete — vector hit, else keyword overlap."""
    hits = await retrieve_relevant_memories(
        email, query, top_k=3, min_similarity=_TOPIC_DELETE_SIMILARITY
    )
    if hits:
        return hits[0]
    tokens = [
        t
        for t in re.findall(r"[a-z0-9]+", query.lower())
        if t not in _STOP_TOPIC and len(t) > 1
    ]
    if not tokens:
        return None
    best: tuple[int, dict] | None = None
    for mem in await db.list_memories(email):
        content = (mem.get("content") or "").lower()
        score = sum(1 for t in tokens if t in content)
        if score and (best is None or score > best[0]):
            best = (score, mem)
    return best[1] if best else None


async def _forget_topic_memory(
    *,
    email: str,
    session_id: str,
    message: str,
    request_id: str,
    total: obs.Timer,
    timings: dict[str, int],
    prompt_versions: dict,
    root: object | None,
    topic: str | None = None,
) -> dict:
    query = (topic or rg.forget_topic_query(message) or message).strip()
    target = await _match_topic_memory(email, query)
    if not target:
        answer = f"I couldn't find a saved memory matching “{query}”."
        timings["total"] = total.stop()
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action="forgotten",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=True,
            memory_ids=[],
        )
    memory_id = str(target["id"])
    await db.delete_memory(email, memory_id)
    answer = f"Forgotten — removed: {target.get('content') or ''}"
    timings["total"] = total.stop()
    lf.update_observation(
        root,
        output=[{"role": "assistant", "content": answer}],
        metadata={"action": "forgotten", "memoryIds": [memory_id]},
    )
    return await _finish(
        email=email,
        session_id=session_id,
        message=message,
        answer=answer,
        action="forgotten",
        sources=[],
        request_id=request_id,
        prompt_versions=prompt_versions,
        timings=timings,
        empty_retrieval=False,
        memory_ids=[memory_id],
    )


async def _update_matching_memory(
    *,
    email: str,
    session_id: str,
    message: str,
    request_id: str,
    total: obs.Timer,
    timings: dict[str, int],
    prompt_versions: dict,
    root: object | None,
    settings: dict,
    fact: str | None = None,
) -> dict:
    new_fact = (fact or message).strip()
    # Strip leading correction cues for a cleaner stored statement.
    new_fact = re.sub(
        r"^\s*(actually|correction:|correct that[,:]?|no,? it'?s|it'?s actually)\s*",
        "",
        new_fact,
        flags=re.I,
    ).strip() or message.strip()
    hits = await retrieve_relevant_memories(
        email, new_fact, top_k=3, min_similarity=0.2
    )
    if not hits:
        # Nothing to update — fall through to a normal store.
        stored = await store_fact(email, new_fact, "chat")
        answer = f"Got it — I'll remember that: {stored['content']}"
        timings["total"] = total.stop()
        result = await _finish(
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
            memory_ids=[stored["id"]],
        )
        return _with_chips(result, settings, action="stored")

    old = hits[0]
    embedding = await embed(new_fact)
    updated = await db.update_memory_content(
        email, str(old["id"]), new_fact, embedding
    )
    timings["total"] = total.stop()
    if not updated:
        answer = "I couldn't update that memory — try again."
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action="blocked",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=[],
            guardrail="update_failed",
        )
    answer = f"Updated — I'll remember: {updated['content']}"
    result = await _finish(
        email=email,
        session_id=session_id,
        message=message,
        answer=answer,
        action="updated",
        sources=[],
        request_id=request_id,
        prompt_versions=prompt_versions,
        timings=timings,
        empty_retrieval=False,
        memory_ids=[updated["id"]],
    )
    return _with_chips(result, settings, action="updated")


async def _forget_last_memory(
    *,
    email: str,
    session_id: str,
    message: str,
    request_id: str,
    total: obs.Timer,
    timings: dict[str, int],
    prompt_versions: dict,
    root: object | None,
    settings: dict | None = None,
) -> dict:
    """Soft-delete the user's newest memory and confirm what was removed."""
    latest = await db.latest_memory(email)
    if not latest:
        answer = "There's nothing saved yet for me to forget."
        timings["total"] = total.stop()
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": answer}],
            metadata={"action": "forgotten", "memoryIds": []},
        )
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action="forgotten",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=[],
        )

    memory_id = str(latest["id"])
    deleted = await db.delete_memory(email, memory_id)
    if not deleted:
        answer = "I couldn't remove that memory — try again in a moment."
        timings["total"] = total.stop()
        lf.update_observation(
            root,
            output=[{"role": "assistant", "content": answer}],
            metadata={"action": "forgotten", "memoryIds": []},
            level="WARNING",
        )
        return await _finish(
            email=email,
            session_id=session_id,
            message=message,
            answer=answer,
            action="forgotten",
            sources=[],
            request_id=request_id,
            prompt_versions=prompt_versions,
            timings=timings,
            empty_retrieval=False,
            memory_ids=[],
        )

    content = latest.get("content") or ""
    answer = f"Forgotten — I removed the last thing I saved: {content}"
    memory_ids = [memory_id]
    timings["total"] = total.stop()
    lf.update_observation(
        root,
        output=[{"role": "assistant", "content": answer}],
        metadata={"action": "forgotten", "memoryIds": memory_ids},
    )
    return await _finish(
        email=email,
        session_id=session_id,
        message=message,
        answer=answer,
        action="forgotten",
        sources=[],
        request_id=request_id,
        prompt_versions=prompt_versions,
        timings=timings,
        empty_retrieval=False,
        memory_ids=memory_ids,
    )


def re_sub_confirm(fact: str) -> str:
    """Remove a leading CONFIRM_SENSITIVE token from a normalized fact if present."""
    return re.sub(
        r"^\s*CONFIRM_SENSITIVE[:\s-]*", "", fact, flags=re.IGNORECASE
    ).strip() or fact
