"""Memory endpoints — the store-or-recall chat plus memory management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from ..auth import require_user
from ..memory import db as mem_db
from ..memory import engine

router = APIRouter()


@router.post("/api/memory/chat")
async def memory_chat(body: dict = Body(default={}), email: str = Depends(require_user)):
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "Message required"}, status_code=400)

    session_id = body.get("sessionId") or str(uuid.uuid4())
    source = body.get("source") or "chat"
    return await engine.handle_message(email, message, session_id, source)


@router.get("/api/memory/chat/{session_id}")
async def memory_chat_history(session_id: str, email: str = Depends(require_user)):
    return await mem_db.get_chat_history(email, session_id)


@router.get("/api/memory")
async def list_memories(email: str = Depends(require_user)):
    return await mem_db.list_memories(email)


@router.post("/api/memory")
async def create_memory(body: dict = Body(default={}), email: str = Depends(require_user)):
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    source = body.get("source") or "manual"
    stored = await engine.store_fact(email, content, source)
    return {"ok": True, "memory": stored}


@router.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str, email: str = Depends(require_user)):
    deleted = await mem_db.delete_memory(email, memory_id)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"ok": True}
