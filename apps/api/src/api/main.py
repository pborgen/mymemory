"""FastAPI application for the MyMemory backend.

Serves the /api routes the Expo client calls. On startup it ensures the schema
exists (profiles, pgvector extension, memory + chat tables).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from . import config, db, observability as obs
from .memory.db import ensure_memory_tables
from .prompts import store as prompt_store
from .prompts.db import ensure_prompt_tables, seed_prompts
from .routers import admins, auth, memory, prompts


@asynccontextmanager
async def lifespan(app: FastAPI):
    obs.setup_logging()
    await db.init_pool()
    await db.ensure_tables()
    await ensure_memory_tables()
    await ensure_prompt_tables()
    await seed_prompts()
    await db.seed_super_admin()
    await obs.ensure_observability_tables()
    print(f"MyMemory API ready (port {config.PORT})")
    yield
    await prompt_store.close()
    await db.close_pool()


app = FastAPI(title="MyMemory API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach/propagate X-Request-Id on every request for log correlation."""
    rid = request.headers.get("x-request-id") or obs.new_request_id()
    obs.set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


# Errors are returned as { "error": "..." }.
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse({"error": "Invalid request"}, status_code=400)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    obs.log_event("unhandled_exception", error=str(exc))
    return JSONResponse({"error": str(exc)}, status_code=500)


# ── API routers ───────────────────────────────────────────

for module in (auth, admins, memory, prompts):
    app.include_router(module.router)


@app.get("/", response_class=PlainTextResponse)
async def root():
    return "MyMemory API"


@app.get("/api/health")
async def health():
    """Liveness + dependency checks (Postgres required; Redis/LLM best-effort)."""
    checks: dict[str, dict] = {}
    ok = True

    try:
        await db.pool().fetchval("SELECT 1")
        checks["postgres"] = {"ok": True}
    except Exception as exc:
        ok = False
        checks["postgres"] = {"ok": False, "error": str(exc)}

    try:
        client = prompt_store._redis()
        if client is None:
            checks["redis"] = {"ok": True, "skipped": True}
        else:
            await client.ping()
            checks["redis"] = {"ok": True}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": str(exc)}

    checks["providers"] = {
        "ok": True,
        "gen": config.GEN_PROVIDER,
        "embed": config.EMBED_PROVIDER,
    }

    status = 200 if ok else 503
    return JSONResponse(
        {"ok": ok, "checks": checks},
        status_code=status,
    )


def run() -> None:
    """Entry point for `uv run api` / the `api` script."""
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=config.PORT, reload=False)


if __name__ == "__main__":
    run()
