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

from . import config, db
from .memory.db import ensure_memory_tables
from .prompts.db import ensure_prompt_tables, seed_prompts
from .routers import auth, memory, prompts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    await db.ensure_tables()
    await ensure_memory_tables()
    await ensure_prompt_tables()
    await seed_prompts()
    print(f"MyMemory API ready (port {config.PORT})")
    yield
    await db.close_pool()


app = FastAPI(title="MyMemory API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Errors are returned as { "error": "..." }.
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse({"error": "Invalid request"}, status_code=400)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse({"error": str(exc)}, status_code=500)


# ── API routers ───────────────────────────────────────────

for module in (auth, memory, prompts):
    app.include_router(module.router)


@app.get("/", response_class=PlainTextResponse)
async def root():
    return "MyMemory API"


@app.get("/api/health")
async def health():
    return {"ok": True}


def run() -> None:
    """Entry point for `uv run api` / the `api` script."""
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=config.PORT, reload=False)


if __name__ == "__main__":
    run()
