"""Entity extraction for memory clustering.

Pulls people / places / orgs / things out of a stored fact so memories can be
grouped automatically. Uses the chat LLM when available, with a cheap heuristic
fallback so clustering still works if the model returns junk.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid

from . import db
from . import generation

_ENTITY_TYPES = frozenset({"person", "place", "org", "thing", "other"})

_EXTRACT_SYSTEM = """Extract the lasting entities from a personal memory fact.

Respond with ONLY JSON (no markdown):
{"entities":[{"name":"<display name>","type":"person|place|org|thing|other","key":"<slug>"}]}

Rules:
- name: human-readable (e.g. "Helen", "Blue Bottle").
- key: lowercase slug, spaces → hyphen (e.g. "helen", "blue-bottle").
- type: person (people), place (locations/venues), org (companies), thing (pets,
  objects, accounts, IDs), other.
- Only entities the fact is ABOUT. Skip pronouns, dates alone, and generic words.
- If nothing clear, return {"entities":[]}."""

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["person", "place", "org", "thing", "other"],
                    },
                    "key": {"type": "string"},
                },
                "required": ["name", "type", "key"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entities"],
    "additionalProperties": False,
}

_STOP = frozenset(
    {
        "my",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "of",
        "on",
        "in",
        "at",
        "to",
        "for",
        "with",
        "from",
        "i",
        "me",
        "we",
        "our",
        "you",
        "your",
        "it",
        "its",
        "this",
        "that",
        "favorite",
        "preferred",
        "birthday",
        "anniversary",
        "password",
        "number",
        "name",
        "called",
        "named",
        "order",
        "license",
        "plate",
        "hello",
        "hi",
        "hey",
        "thanks",
        "assist",
        "today",
        "please",
    }
)

_POSSESSIVE = re.compile(r"\b([A-Z][a-z]{1,30})'s\b")
_PROPER = re.compile(r"\b([A-Z][a-z]{2,30}(?:\s+[A-Z][a-z]{2,30}){0,2})\b")


def normalize_key(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s[:64]


def _heuristic_entities(fact: str) -> list[dict]:
    found: dict[str, dict] = {}
    for m in _POSSESSIVE.finditer(fact or ""):
        name = m.group(1)
        key = normalize_key(name)
        if key and key not in _STOP:
            found[key] = {"name": name, "type": "person", "key": key}
    for m in _PROPER.finditer(fact or ""):
        name = m.group(1).strip()
        # Skip sentence starters that aren't real entities when alone.
        if name.lower() in _STOP:
            continue
        key = normalize_key(name)
        if not key or key in found or key in _STOP:
            continue
        lowered = (fact or "").lower()
        etype = "other"
        if any(p in lowered for p in ("live", "address", "street", "cafe", "shop", "on ")):
            etype = "place"
        elif "'s" in (fact or "") and name in (fact or ""):
            etype = "person"
        elif any(p in lowered for p in ("dog", "cat", "pet", "car", "wifi", "password")):
            etype = "thing"
        found[key] = {"name": name, "type": etype, "key": key}
    return list(found.values())[:6]


def _parse_entities(text: str) -> list[dict]:
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except Exception:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for raw in data.get("entities") or []:
        name = (raw.get("name") or "").strip()
        key = normalize_key(raw.get("key") or name)
        etype = (raw.get("type") or "other").strip().lower()
        if etype not in _ENTITY_TYPES:
            etype = "other"
        if not name or not key or key in seen or key in _STOP:
            continue
        seen.add(key)
        out.append({"name": name[:80], "type": etype, "key": key})
        if len(out) >= 6:
            break
    return out


def _extract_sync(fact: str) -> list[dict]:
    text = generation._converse(
        _EXTRACT_SYSTEM,
        [{"role": "user", "content": [{"text": fact}]}],
        max_tokens=300,
        temperature=0.0,
        json_schema=_EXTRACT_SCHEMA,
        observation_name="extract-entities",
    )
    entities = _parse_entities(text)
    if entities:
        return entities
    return _heuristic_entities(fact)


async def extract_entities(fact: str) -> list[dict]:
    """Return [{name, type, key}, ...] for a memory fact."""
    fact = (fact or "").strip()
    if not fact:
        return []
    try:
        return await asyncio.to_thread(_extract_sync, fact)
    except Exception:
        return _heuristic_entities(fact)


async def link_entities_for_memory(
    email: str,
    memory_id: str,
    content: str,
    *,
    use_llm: bool = True,
) -> list[dict]:
    """Extract entities from content and attach them to the memory. Returns entities."""
    if use_llm:
        entities = await extract_entities(content)
    else:
        entities = _heuristic_entities(content)
    if not entities:
        return []
    linked: list[dict] = []
    for ent in entities:
        row = await db.upsert_entity(
            str(uuid.uuid4()),
            email,
            name=ent["name"],
            key=ent["key"],
            entity_type=ent["type"],
        )
        await db.link_memory_entity(memory_id, row["id"])
        linked.append(row)
    return linked


async def attach_named_entity(
    email: str,
    memory_id: str,
    *,
    name: str,
    entity_type: str = "other",
) -> dict | None:
    """Link a memory to an entity by display name (creates entity if needed)."""
    name = (name or "").strip()
    if not name:
        return None
    if not await db.memory_owned(email, memory_id):
        return None
    etype = (entity_type or "other").strip().lower()
    if etype not in _ENTITY_TYPES:
        etype = "other"
    key = normalize_key(name)
    if not key:
        return None
    row = await db.upsert_entity(
        str(uuid.uuid4()),
        email,
        name=name[:80],
        key=key,
        entity_type=etype,
    )
    await db.link_memory_entity(memory_id, row["id"])
    return row


async def detach_entity(email: str, memory_id: str, entity_id: str) -> bool:
    if not await db.memory_owned(email, memory_id):
        return False
    return await db.unlink_memory_entity(email, memory_id, entity_id)


async def rename_entity(
    email: str,
    entity_id: str,
    *,
    name: str,
    entity_type: str | None = None,
) -> dict | None:
    name = (name or "").strip()
    if not name:
        return None
    key = normalize_key(name)
    if not key:
        return None
    etype = None
    if entity_type is not None:
        etype = entity_type.strip().lower()
        if etype not in _ENTITY_TYPES:
            etype = "other"
    return await db.rename_entity(
        email, entity_id, name=name[:80], key=key, entity_type=etype
    )

async def backfill_unlinked_memories(email: str, *, limit: int = 25) -> int:
    """Heuristic-cluster memories that have none yet (fast; no LLM). Returns count."""
    ids = await db.list_memory_ids_without_entities(email, limit=limit)
    n = 0
    for mid, content in ids:
        await link_entities_for_memory(email, mid, content, use_llm=False)
        n += 1
    return n
