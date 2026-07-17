"""Prompt management endpoints — list/read for any user, edits gated to admins.

Prompts are global (app-wide), versioned, and resolved at runtime by the memory
engine and the agent. Saves can be drafts or activated; activation for keys with
an eval suite is gated on a golden-set offline eval (override with forceReason).
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from ..auth import require_admin, require_user
from ..prompts import db as prompts_db
from ..prompts import eval as prompt_eval
from ..prompts import store

router = APIRouter()


def _note_with_force(change_note: str, force_reason: str | None) -> str:
    if force_reason:
        return f"{change_note} [force: {force_reason}]"
    return change_note


async def _gate_or_error(key: str, content: str, force_reason: str | None):
    """Run eval; return (eval_report, error_response_or_None)."""
    report = await prompt_eval.evaluate_prompt(key, content)
    if report["passed"] or report.get("skipped"):
        return report, None
    if force_reason and force_reason.strip():
        return report, None
    return report, JSONResponse(
        {
            "error": "Eval failed — fix the prompt or pass forceReason to override",
            "eval": report,
        },
        status_code=400,
    )


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


@router.post("/api/prompts/{key}/eval")
async def eval_prompt(
    key: str, body: dict = Body(default={}), _: str = Depends(require_admin)
):
    """Run the golden eval suite against candidate content (does not activate)."""
    if not await prompts_db.get_prompt(key):
        return JSONResponse({"error": "Not found"}, status_code=404)
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    return await prompt_eval.evaluate_prompt(key, content)


@router.put("/api/prompts/{key}")
async def save_prompt(key: str, body: dict = Body(default={}), email: str = Depends(require_admin)):
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "Content required"}, status_code=400)
    change_note = (body.get("changeNote") or "").strip()
    if not change_note:
        return JSONResponse({"error": "changeNote required"}, status_code=400)

    # Default: activate (eval-gated). Pass activate=false to save a draft only.
    activate = body.get("activate", True)
    if isinstance(activate, str):
        activate = activate.lower() not in ("0", "false", "no")
    force_reason = (body.get("forceReason") or "").strip() or None

    eval_report = None
    if activate:
        eval_report, err = await _gate_or_error(key, content, force_reason)
        if err is not None:
            return err

    note = _note_with_force(change_note, force_reason if activate else None)
    updated = await prompts_db.save_version(
        key, content, email, note, activate=bool(activate)
    )
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if activate:
        await store.invalidate(key)
    return {**updated, "eval": eval_report, "activated": bool(activate)}


@router.post("/api/prompts/{key}/activate")
async def activate_prompt(
    key: str, body: dict = Body(default={}), email: str = Depends(require_admin)
):
    """Activate an existing version after running the eval gate."""
    version_id = body.get("versionId")
    if not version_id:
        return JSONResponse({"error": "versionId required"}, status_code=400)
    version = await prompts_db.get_version(key, version_id)
    if not version:
        return JSONResponse({"error": "Not found"}, status_code=404)

    force_reason = (body.get("forceReason") or "").strip() or None
    eval_report, err = await _gate_or_error(key, version["content"], force_reason)
    if err is not None:
        return err

    updated = await prompts_db.set_active(key, version_id)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    await store.invalidate(key)
    return {**updated, "eval": eval_report, "activated": True}


@router.post("/api/prompts/{key}/rollback")
async def rollback_prompt(key: str, body: dict = Body(default={}), _: str = Depends(require_admin)):
    """Point active at an existing version (no eval — intentional recovery path)."""
    version_id = body.get("versionId")
    if not version_id:
        return JSONResponse({"error": "versionId required"}, status_code=400)
    updated = await prompts_db.set_active(key, version_id)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    await store.invalidate(key)
    return updated


@router.post("/api/prompts/{key}/reset")
async def reset_prompt(key: str, email: str = Depends(require_admin)):
    updated = await prompts_db.reset_prompt(key, email)
    if not updated:
        return JSONResponse({"error": "Not found"}, status_code=404)
    await store.invalidate(key)
    return updated
