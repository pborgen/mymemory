"""Embeddings — Amazon Titan Text Embeddings v2 on AWS Bedrock.

Uses boto3's bedrock-runtime client. Credentials resolve via the standard AWS
chain (env vars, shared config/credentials, SSO, or an instance/role profile) —
the same chain the Bedrock Claude client in generation.py relies on. The output
dimension must match the VECTOR(n) column in db.py (config.EMBED_DIM).
"""
from __future__ import annotations

import asyncio
import json

import boto3

from .. import config

_client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def _embed_sync(text: str) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": config.EMBED_DIM, "normalize": True})
    response = _client.invoke_model(
        modelId=config.EMBED_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    payload = json.loads(response["body"].read())
    return payload["embedding"]


async def embed(text: str) -> list[float]:
    """Embed a single string. Bedrock's boto3 client is sync; run off the loop."""
    return await asyncio.to_thread(_embed_sync, text.strip())
