"""Environment-driven configuration, loaded once at import time."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL: str | None = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
PORT: int = int(os.getenv("PORT", "8080"))
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
ALLOW_DEV_AUTH_HEADERS: bool = os.getenv("ALLOW_DEV_AUTH_HEADERS") == "true"

# Super admin email — upserted as profiles.role=admin on API startup. Day-to-day
# grants for other admins happen in the DB (see /api/admins). Leave blank only
# if you will set roles via SQL yourself.
SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "").strip().lower()
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# ── Guardrails ────────────────────────────────────────────
# Max characters accepted on chat / store input (hard length limit).
GUARDRAIL_MAX_MESSAGE_CHARS: int = int(os.getenv("GUARDRAIL_MAX_MESSAGE_CHARS", "4000"))
# Drop retrieval hits below this cosine similarity; empty → hard refuse (no generate).
# Integration tests with fake embeddings set this to 0 via monkeypatch.
RETRIEVAL_MIN_SIMILARITY: float = float(os.getenv("RETRIEVAL_MIN_SIMILARITY", "0.25"))

# Redis connection string for the shared prompt cache (api.prompts.store). Unset
# in local dev is fine — the resolver reads straight through to Postgres.
REDIS_URL: str | None = os.getenv("REDIS_URL")

# Generation and embeddings are configured independently, because a single
# server often provides only one of them (e.g. a vLLM chat server has no
# embeddings endpoint). Each provider is one of: "openai", "ollama", "bedrock".

# ── Generation (answer + classification LLM) ──────────────
#   openai  — any OpenAI-compatible server (vLLM, LM Studio, LiteLLM, …)
#   ollama  — an Ollama server (/api/chat)
#   bedrock — AWS Bedrock Converse (Claude/Nova)
GEN_PROVIDER: str = os.getenv("GEN_PROVIDER", "openai").lower()

# OpenAI-compatible chat server (GEN_PROVIDER=openai). For a Tailscale vLLM host:
# OPENAI_BASE_URL=http://100.99.15.47:8001/v1 . vLLM ignores the key, but the
# OpenAI wire format wants a non-empty one.
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "http://localhost:8001/v1").rstrip("/")
OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "not-needed")

# Ollama chat (GEN_PROVIDER=ollama).
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")

# Bedrock chat (GEN_PROVIDER=bedrock). Cross-region inference profile; default is
# cheap Amazon Nova Lite. Swap to a Claude profile via env if desired.
RAG_MODEL_ID: str = os.getenv("RAG_MODEL_ID", "us.amazon.nova-2-lite-v1:0")

# ── Embeddings ────────────────────────────────────────────
#   openai  — OpenAI-compatible /v1/embeddings (e.g. a vLLM/TEI embed server)
#   ollama  — Ollama /api/embeddings
#   bedrock — Amazon Titan
# EMBED_DIM MUST match the VECTOR(n) column in memory/db.py; changing it requires
# recreating that column (existing memories are re-embedded).
EMBED_PROVIDER: str = os.getenv("EMBED_PROVIDER", "openai").lower()
EMBED_BASE_URL: str = os.getenv("EMBED_BASE_URL", "http://localhost:8002/v1").rstrip("/")
EMBED_API_KEY: str = os.getenv("EMBED_API_KEY", "not-needed")
# Model name for the active embed provider (an OpenAI/Ollama model id, or the
# Titan Bedrock model id when EMBED_PROVIDER=bedrock).
EMBED_MODEL_ID: str = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1024"))

# ── Langfuse (optional LLM observability) ─────────────────
# Local-friendly: leave keys unset and tracing is a no-op. Set keys from
# Langfuse Cloud (free) or a self-hosted instance (see docs/observability.md).
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_BASE_URL: str = os.getenv(
    "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
).rstrip("/")
_langfuse_flag = os.getenv("LANGFUSE_ENABLED", "").strip().lower()
if _langfuse_flag in ("0", "false", "no", "off"):
    LANGFUSE_ENABLED: bool = False
elif _langfuse_flag in ("1", "true", "yes", "on"):
    LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
else:
    # Auto-enable when both keys are present.
    LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
