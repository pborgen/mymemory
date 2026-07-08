"""Embeddings — pluggable provider, selected by config.EMBED_PROVIDER.

  openai  — OpenAI-compatible /v1/embeddings (e.g. a vLLM / TEI embed server)
  ollama  — Ollama /api/embeddings
  bedrock — Amazon Titan Text Embeddings v2

Every path must return config.EMBED_DIM-length vectors to match the VECTOR(n)
column in memory/db.py. Bedrock's boto3 client is created lazily so a non-Bedrock
deployment needs no AWS.
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache

import httpx

from .. import config


@lru_cache(maxsize=1)
def _bedrock_client():
    import boto3

    return boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def _embed_openai(text: str) -> list[float]:
    response = httpx.post(
        f"{config.EMBED_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {config.EMBED_API_KEY}"},
        json={"model": config.EMBED_MODEL_ID, "input": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def _embed_ollama(text: str) -> list[float]:
    response = httpx.post(
        f"{config.EMBED_BASE_URL}/api/embeddings",
        json={"model": config.EMBED_MODEL_ID, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    embedding = response.json().get("embedding")
    if not embedding:
        raise RuntimeError(f"Embed server returned no embedding for {config.EMBED_MODEL_ID}")
    return embedding


def _embed_bedrock(text: str) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": config.EMBED_DIM, "normalize": True})
    response = _bedrock_client().invoke_model(
        modelId=config.EMBED_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(response["body"].read())
    return payload["embedding"]


def _embed_sync(text: str) -> list[float]:
    if config.EMBED_PROVIDER == "openai":
        return _embed_openai(text)
    if config.EMBED_PROVIDER == "ollama":
        return _embed_ollama(text)
    return _embed_bedrock(text)


async def embed(text: str) -> list[float]:
    """Embed a single string. The provider clients are sync; run off the loop."""
    return await asyncio.to_thread(_embed_sync, text.strip())
