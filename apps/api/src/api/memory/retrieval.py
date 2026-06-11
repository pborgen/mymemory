"""Retrieval step — embed the query, then pgvector cosine search per user."""
from __future__ import annotations

from . import db
from .embeddings import embed


async def retrieve_relevant_memories(
    email: str, query: str, top_k: int = 6, min_similarity: float = 0.0
) -> list[dict]:
    query_embedding = await embed(query)
    results = await db.search_memories(email, query_embedding, top_k)
    return [m for m in results if m["similarity"] >= min_similarity]
