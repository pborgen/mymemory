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

# Bedrock model id (cross-region inference profile) for answer generation, used
# via the model-agnostic Converse API. Defaults to Amazon Nova Lite — one of the
# cheapest Bedrock models and not behind the Anthropic access gate. Swap to a
# Claude profile (e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0) via env.
RAG_MODEL_ID: str = os.getenv("RAG_MODEL_ID", "us.amazon.nova-2-lite-v1:0")

# Bedrock embedding model. Titan Text Embeddings v2 outputs 1024-dim vectors;
# EMBED_DIM must match the VECTOR(n) column declared in memory/db.py.
EMBED_MODEL_ID: str = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1024"))
