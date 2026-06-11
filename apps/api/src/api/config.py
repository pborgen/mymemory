"""Environment-driven configuration, loaded once at import time."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL: str | None = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
PORT: int = int(os.getenv("PORT", "8080"))
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
ALLOW_DEV_AUTH_HEADERS: bool = os.getenv("ALLOW_DEV_AUTH_HEADERS") == "true"
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# Bedrock model id (cross-region inference profile) for answer generation.
# Defaults to Claude Haiku 4.5 — cheap and current; override with RAG_MODEL_ID.
RAG_MODEL_ID: str = os.getenv(
    "RAG_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Bedrock embedding model. Titan Text Embeddings v2 outputs 1024-dim vectors;
# EMBED_DIM must match the VECTOR(n) column declared in memory/db.py.
EMBED_MODEL_ID: str = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1024"))
