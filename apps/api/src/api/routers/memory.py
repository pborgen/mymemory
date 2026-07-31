"""Memory endpoints — the store-or-recall chat plus memory management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from ..auth import require_admin, require_user
from .. import config
from .. import observability as obs
from .. import rate_limit
from ..memory import db as mem_db
from ..memory import engine
from ..memory import guardrails as gr
from ..memory.entities import (
    attach_named_entity,
    backfill_unlinked_memories,
    detach_entity,
    rename_entity,
)

router = APIRouter()


async def require_user_chat_budget(email: str = Depends(require_user)) -> str:
    """Auth + per-user rate limit for the costly chat path."""
    await rate_limit.enforce(f"chat:{email}", config.RATE_LIMIT_CHAT_PER_MIN)
    return email


async def require_user_store_budget(email: str = Depends(require_user)) -> str:
    """Auth + per-user rate limit for direct memory store (embed + entity LLM)."""
    await rate_limit.enforce(f"store:{email}", config.RATE_LIMIT_STORE_PER_MIN)
    return email


async def _maybe_backfill_entities(email: str) -> None:
    try:
        await backfill_unlinked_memories(email, limit=25)
    except Exception:
        pass


def _valid_session_id(value: object) -> str:
    """Accept only a well-formed UUID from the client; otherwise mint a fresh one."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())


@router.post("/api/memory/chat")
async def memory_chat(
    body: dict = Body(default={}),
    email: str = Depends(require_user_chat_budget),
):
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "Message required"}, status_code=400)

    session_id = _valid_session_id(body.get("sessionId"))
    source = body.get("source") or "chat"
    return await engine.handle_message(email, message, session_id, source)


@router.get("/api/memory/chat/{session_id}")
async def memory_chat_history(session_id: str, email: str = Depends(require_user)):
    return await mem_db.get_chat_history(email, session_id)


@router.post("/api/memory/chat/feedback")
async def chat_feedback(body: dict = Body(default={}), email: str = Depends(require_user)):
    """Thumbs up/down tied to a chat requestId for online quality signals."""
    request_id = (body.get("requestId") or "").strip()
    if not request_id:
        return JSONResponse({"error": "requestId required"}, status_code=400)
    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "rating must be 1 or -1"}, status_code=400)
    comment = (body.get("comment") or "").strip()
    try:
        return await obs.save_feedback(request_id, email, rating, comment)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/memory/debug/{request_id}")
async def debug_request(request_id: str, _: str = Depends(require_admin)):
    """Look up the metric / debug envelope for a request_id (admin debug drill)."""
    row = await obs.get_metric_by_request_id(request_id)
    if not row:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return row


@router.get("/api/metrics/summary")
async def metrics_summary(hours: int = 24, _: str = Depends(require_admin)):
    """Aggregate chat SLIs for the last N hours."""
    hours = max(1, min(hours, 168))
    return await obs.metrics_summary(hours)


@router.get("/api/memory/audit")
async def memory_audit(email: str = Depends(require_user), limit: int = 50):
    """Append-only access/store trail for the current user (governance demo)."""
    limit = max(1, min(limit, 200))
    return await mem_db.list_audit(email, limit)


@router.get("/api/memory")
async def list_memories(
    email: str = Depends(require_user),
    entity: str = "",
):
    # Lazily cluster a batch of older memories that predate entity linking.
    await _maybe_backfill_entities(email)
    return await mem_db.list_memories(email, entity_key=entity.strip().lower())


@router.get("/api/memory/entities")
async def list_entities(email: str = Depends(require_user)):
    """Entity clusters for the signed-in user (auto-extracted on store)."""
    await _maybe_backfill_entities(email)
    return await mem_db.list_entities(email)


@router.patch("/api/memory/entities/{entity_id}")
async def patch_entity(
    entity_id: str,
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    """Rename (and optionally retype) an entity across all its memories."""
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    entity_type = body.get("type")
    updated = await rename_entity(
        email,
        entity_id,
        name=name,
        entity_type=entity_type if isinstance(entity_type, str) else None,
    )
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    await mem_db.write_audit(
        email,
        "entity_rename",
        detail={"entityId": entity_id, "name": updated["name"], "key": updated["key"]},
    )
    return {"ok": True, "entity": updated}


@router.post("/api/memory/{memory_id}/entities")
async def add_memory_entity(
    memory_id: str,
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    """Attach an entity relationship to a memory (creates the entity if needed)."""
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    entity_type = (body.get("type") or "other").strip()
    linked = await attach_named_entity(
        email, memory_id, name=name, entity_type=entity_type
    )
    if not linked:
        return JSONResponse({"error": "Not found"}, status_code=404)
    entities = await mem_db.entities_for_memory(email, memory_id)
    await mem_db.write_audit(
        email,
        "entity_link",
        memory_id=memory_id,
        detail={"entityId": linked["id"], "name": linked["name"]},
    )
    return {"ok": True, "entity": linked, "entities": entities}


@router.delete("/api/memory/{memory_id}/entities/{entity_id}")
async def remove_memory_entity(
    memory_id: str,
    entity_id: str,
    email: str = Depends(require_user),
):
    """Detach an entity relationship from a memory."""
    ok = await detach_entity(email, memory_id, entity_id)
    if not ok:
        return JSONResponse({"error": "Not found"}, status_code=404)
    entities = await mem_db.entities_for_memory(email, memory_id)
    await mem_db.write_audit(
        email,
        "entity_unlink",
        memory_id=memory_id,
        detail={"entityId": entity_id},
    )
    return {"ok": True, "entities": entities}


@router.get("/api/memory/report")
async def memory_report(
    email: str = Depends(require_user),
    loan: str = "",
    tag: str = "",
    sourceUriPrefix: str = "",
):
    """Filter memories for warehouse-style reporting (loan / tag / lineage)."""
    return await mem_db.list_memories_for_report(
        email,
        loan=loan.strip(),
        tag=tag.strip(),
        source_uri_prefix=sourceUriPrefix.strip(),
    )


@router.post("/api/memory")
async def create_memory(
    body: dict = Body(default={}),
    email: str = Depends(require_user_store_budget),
):
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    pii = gr.check_store_pii(content, content)
    if pii.blocked and not (body.get("confirmSensitive") is True):
        return JSONResponse(
            {"error": pii.message, "guardrail": pii.reason},
            status_code=400,
        )
    source = body.get("source") or "manual"
    source_uri = (body.get("sourceUri") or "").strip()
    pipeline_version = (body.get("pipelineVersion") or "").strip()
    stored = await engine.store_fact(
        email,
        content,
        source,
        source_uri=source_uri,
        pipeline_version=pipeline_version,
    )
    await mem_db.write_audit(
        email,
        "store",
        memory_id=stored["id"],
        detail={
            "piiTags": stored.get("piiTags") or [],
            "sensitivity": stored.get("sensitivity"),
            "source": source,
            "sourceUri": source_uri or None,
            "pipelineVersion": pipeline_version or None,
        },
    )
    return {"ok": True, "memory": stored}


@router.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str, email: str = Depends(require_user)):
    deleted = await mem_db.delete_memory(email, memory_id)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    await mem_db.write_audit(
        email, "delete", memory_id=memory_id, detail={"soft": True}
    )
    return {"ok": True}
