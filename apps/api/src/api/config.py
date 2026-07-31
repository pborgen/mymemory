"""Environment-driven configuration, loaded once at import time."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL: str | None = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
PORT: int = int(os.getenv("PORT", "8080"))
# Primary Web OAuth client (GIS on web + webClientId for mobile id tokens).
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
# Optional extra audiences (e.g. iOS OAuth client). Comma-separated.
# Tokens whose `aud` matches any of GOOGLE_CLIENT_ID + these are accepted.
_google_extra = os.getenv("GOOGLE_IOS_CLIENT_ID", "").strip()
GOOGLE_CLIENT_IDS: list[str] = [
    c
    for c in [GOOGLE_CLIENT_ID, *(_google_extra.split(",") if _google_extra else [])]
    if c
]
GOOGLE_IOS_CLIENT_ID: str = (
    _google_extra.split(",")[0].strip() if _google_extra else ""
)
ALLOW_DEV_AUTH_HEADERS: bool = os.getenv("ALLOW_DEV_AUTH_HEADERS") == "true"

# Runtime environment. Set to "production" (or "prod") on public AWS so startup
# refuses unsafe auth/CORS settings. Local/dev leave unset or "development".
ENVIRONMENT: str = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").strip().lower()
IS_PRODUCTION: bool = ENVIRONMENT in ("production", "prod")

# Comma-separated browser origins allowed by CORS. Empty → ["*"] (local only).
# In production this MUST be an explicit list (web App Runner URL, custom domain).
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "").strip()

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

# Per-user rate limits on Bedrock-costly endpoints (requests / rolling 60s).
# Set to 0 to disable (tests). Defaults are generous for humans, hostile to bots.
RATE_LIMIT_CHAT_PER_MIN: int = int(os.getenv("RATE_LIMIT_CHAT_PER_MIN", "30"))
RATE_LIMIT_STORE_PER_MIN: int = int(os.getenv("RATE_LIMIT_STORE_PER_MIN", "20"))


def cors_origin_list() -> list[str]:
    """Parse CORS_ORIGINS into a FastAPI allow_origins list."""
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    return origins or ["*"]


def validate_public_config() -> None:
    """Refuse to boot a public deployment with spoofable or open auth/CORS.

    Called from the FastAPI lifespan when IS_PRODUCTION is true. Local `api:dev`
    leaves ENVIRONMENT unset so this is a no-op.
    """
    problems: list[str] = []
    if ALLOW_DEV_AUTH_HEADERS:
        problems.append(
            "ALLOW_DEV_AUTH_HEADERS=true — anyone can spoof x-user-email and burn LLM spend"
        )
    if not GOOGLE_CLIENT_ID:
        problems.append(
            "GOOGLE_CLIENT_ID is empty — no real login path on a public API"
        )
    if cors_origin_list() == ["*"]:
        problems.append(
            "CORS_ORIGINS is empty/* — set it to your web origin(s), e.g. https://xxx.awsapprunner.com"
        )
    if problems:
        raise RuntimeError(
            "Unsafe production config:\n  - "
            + "\n  - ".join(problems)
        )

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

# Separate test/dev traces from production dashboards (Langfuse environments).
LANGFUSE_TRACING_ENVIRONMENT: str = (
    os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "development").strip() or "development"
)
