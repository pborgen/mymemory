"""Per-user feature settings + data tools gated by those settings."""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from ..auth import require_user
from .. import db
from ..memory import db as mem_db
from ..memory import engine
from ..user_settings import FEATURE_CATALOG, GROUP_ORDER, ordered_groups

router = APIRouter()


def _settings_payload(settings: dict) -> dict:
    return {
        "settings": settings,
        "catalog": FEATURE_CATALOG,
        "groupOrder": GROUP_ORDER,
        "groups": ordered_groups(),
    }


@router.get("/api/settings")
async def get_settings(email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    return _settings_payload(settings)


@router.patch("/api/settings")
async def patch_settings_route(
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    updates = body.get("settings") if isinstance(body.get("settings"), dict) else body
    if not isinstance(updates, dict):
        return JSONResponse({"error": "settings object required"}, status_code=400)
    settings = await db.update_user_settings(email, updates)
    return {"ok": True, **_settings_payload(settings)}


@router.post("/api/settings/paste-inbox")
async def paste_inbox(
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    settings = await db.get_user_settings(email)
    if not settings.get("pasteInbox"):
        return JSONResponse(
            {"error": "Enable Paste inbox in Settings first"},
            status_code=403,
        )
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return JSONResponse({"error": "No lines to save"}, status_code=400)
    if len(lines) > 40:
        return JSONResponse({"error": "Max 40 lines per paste"}, status_code=400)
    stored = []
    for line in lines:
        mem = await engine.store_fact(email, line, source="paste")
        stored.append(mem)
    return {"ok": True, "count": len(stored), "memories": stored}


@router.get("/api/settings/export")
async def export_memories(email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("importExport"):
        return JSONResponse(
            {"error": "Enable Import / export in Settings first"},
            status_code=403,
        )
    memories = await mem_db.list_memories(email)
    return {
        "email": email,
        "count": len(memories),
        "memories": [
            {
                "id": m["id"],
                "content": m["content"],
                "source": m["source"],
                "createdAt": m["createdAt"].isoformat()
                if hasattr(m["createdAt"], "isoformat")
                else m["createdAt"],
                "sensitivity": m.get("sensitivity"),
            }
            for m in memories
        ],
    }


@router.get("/api/settings/export.csv")
async def export_memories_csv(email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("importExport"):
        return JSONResponse(
            {"error": "Enable Import / export in Settings first"},
            status_code=403,
        )
    memories = await mem_db.list_memories(email)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "content", "source", "createdAt", "sensitivity"])
    for m in memories:
        created = m["createdAt"]
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        writer.writerow(
            [m["id"], m["content"], m["source"], created, m.get("sensitivity") or ""]
        )
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="mymemory-export.csv"'},
    )


@router.post("/api/settings/import")
async def import_memories(
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    settings = await db.get_user_settings(email)
    if not settings.get("importExport"):
        return JSONResponse(
            {"error": "Enable Import / export in Settings first"},
            status_code=403,
        )
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("id,content"):
            continue
        # CSV: take content column if present, else whole line.
        if "," in line and line.count(",") >= 1:
            try:
                row = next(csv.reader([line]))
                # id,content,... or bare content
                content = row[1].strip() if len(row) >= 2 else row[0].strip()
            except Exception:
                content = line
        else:
            content = line
        if content:
            lines.append(content)
    if not lines:
        return JSONResponse({"error": "No rows to import"}, status_code=400)
    if len(lines) > 100:
        return JSONResponse({"error": "Max 100 rows per import"}, status_code=400)
    stored = []
    for content in lines:
        mem = await engine.store_fact(email, content, source="import")
        stored.append({"id": mem["id"], "content": mem["content"]})
    return {"ok": True, "count": len(stored), "memories": stored}


@router.delete("/api/settings/memories")
async def delete_all_memories(email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("importExport"):
        return JSONResponse(
            {"error": "Enable Import / export in Settings first"},
            status_code=403,
        )
    count = await mem_db.soft_delete_all_memories(email)
    return {"ok": True, "deleted": count}


@router.get("/api/reminders")
async def list_reminders(email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("reminders"):
        return JSONResponse(
            {"error": "Enable Reminders in Settings first"},
            status_code=403,
        )
    return await mem_db.list_reminders(email)


@router.post("/api/reminders")
async def create_reminder(
    body: dict = Body(default={}),
    email: str = Depends(require_user),
):
    settings = await db.get_user_settings(email)
    if not settings.get("reminders"):
        return JSONResponse(
            {"error": "Enable Reminders in Settings first"},
            status_code=403,
        )
    content = (body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "content required"}, status_code=400)
    return await mem_db.insert_reminder(
        str(uuid.uuid4()),
        email,
        content,
        due_at=body.get("dueAt"),
    )


@router.post("/api/reminders/{reminder_id}/done")
async def complete_reminder(reminder_id: str, email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("reminders"):
        return JSONResponse(
            {"error": "Enable Reminders in Settings first"},
            status_code=403,
        )
    ok = await mem_db.complete_reminder(email, reminder_id)
    if not ok:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"ok": True}


@router.delete("/api/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, email: str = Depends(require_user)):
    settings = await db.get_user_settings(email)
    if not settings.get("reminders"):
        return JSONResponse(
            {"error": "Enable Reminders in Settings first"},
            status_code=403,
        )
    ok = await mem_db.delete_reminder(email, reminder_id)
    if not ok:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"ok": True}
