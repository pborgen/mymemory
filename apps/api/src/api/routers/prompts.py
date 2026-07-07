"""Prompt management endpoints — list/read for any user, edits gated to admins.

Prompts are global (app-wide), versioned, and resolved at runtime by the memory
engine and the agent. See api.prompts for the storage layer.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .. import config
from ..auth import require_user
from ..prompts import db as prompts_db
from ..prompts import store

router = APIRouter()


async def require_admin(request: Request) -> str:
    """Allow listed admins; in dev (no ADMIN_EMAILS set) allow any authed user."""
    email = await require_user(request)
    if config.ADMIN_EMAILS:
        if email.lower() not in config.ADMIN_EMAILS:
            raise HTTPException(status_code=403, detail="Admin access required")
    elif not config.ALLOW_DEV_AUTH_HEADERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return email


@router.get("/api/prompts")
async def list_prompts(_: str = Depends(require_user)):
    return await prompts_db.list_prompts()


@router.get("/api/prompts/{key}")
async def get_prompt(key: str, _: str = Depends(require_user)):
    prompt = await prompts_db.get_prompt(key)
    if not prompt:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return prompt


@router.get("/api/prompts/{key}/versions")
async def list_versions(key: str, _: str = Depends(require_user)):
    if not await prompts_db.get_prompt(key):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return await prompts_db.list_versions(key)


@router.put("/api/prompts/{key}")
async def save_prompt(key: str, body: dict = Body(default={}), email: str = Depends(require_admin)):
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    updated = await prompts_db.save_version(key, content, email)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    store.invalidate(key)
    return updated


@router.post("/api/prompts/{key}/rollback")
async def rollback_prompt(key: str, body: dict = Body(default={}), email: str = Depends(require_admin)):
    version_id = body.get("versionId")
    if not version_id:
        return JSONResponse({"error": "versionId required"}, status_code=400)
    updated = await prompts_db.set_active(key, version_id)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    store.invalidate(key)
    return updated


@router.post("/api/prompts/{key}/reset")
async def reset_prompt(key: str, email: str = Depends(require_admin)):
    updated = await prompts_db.reset_prompt(key, email)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    store.invalidate(key)
    return updated
