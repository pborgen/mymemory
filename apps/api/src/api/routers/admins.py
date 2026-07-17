"""Admin role management — grant/revoke profiles.role = admin.

The env `SUPER_ADMIN_EMAIL` is seeded as admin on startup. Other admins are
managed here in the DB.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from .. import config, db
from ..auth import require_admin, require_user

router = APIRouter()


@router.get("/api/admins")
async def list_admins(_: str = Depends(require_admin)):
    return await db.list_admins()


@router.put("/api/admins/{email}")
async def set_admin_role(
    email: str,
    body: dict = Body(default={}),
    actor: str = Depends(require_admin),
):
    role = (body.get("role") or "").strip().lower()
    if role not in ("admin", "user"):
        return JSONResponse(
            {"error": "role must be 'admin' or 'user'"}, status_code=400
        )
    target = email.lower().strip()
    if role == "user" and config.SUPER_ADMIN_EMAIL and target == config.SUPER_ADMIN_EMAIL:
        return JSONResponse(
            {"error": "Cannot demote the super admin"}, status_code=400
        )
    if role == "user" and target == actor:
        if await db.count_admins() <= 1:
            return JSONResponse(
                {"error": "Cannot demote the last admin"}, status_code=400
            )
    try:
        profile = await db.set_role(target, role)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return profile


@router.get("/api/me")
async def me(email: str = Depends(require_user)):
    """Current user profile including role (for UI gating)."""
    profile = await db.get_profile(email)
    if not profile:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {
        **profile,
        "isAdmin": profile["role"] == "admin",
    }
