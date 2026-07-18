"""Governance: tags, soft-delete, audit trail."""
from __future__ import annotations

from api.memory import db as mem_db
from api.memory.engine import store_fact


async def test_store_tags_and_audit(client, auth):
    r = await client.post(
        "/api/memory",
        headers=auth,
        json={
            "content": "The rate lock on loan LN-2026-4418 is 6.125% until 2026-08-15.",
            "source": "test",
        },
    )
    assert r.status_code == 200, r.text
    mem = r.json()["memory"]
    assert "rate" in mem["piiTags"]
    assert "loan_number" in mem["piiTags"]
    assert mem["sensitivity"] == "sensitive"

    audit = await client.get("/api/memory/audit", headers=auth)
    assert audit.status_code == 200
    rows = audit.json()
    assert any(a["action"] == "store" and a.get("memoryId") == mem["id"] for a in rows)


async def test_soft_delete_and_audit(client, auth):
    stored = await store_fact(
        auth["x-user-email"],
        "Loan officer of record is Sam Rivera.",
        "test",
    )
    mid = stored["id"]
    d = await client.delete(f"/api/memory/{mid}", headers=auth)
    assert d.status_code == 200

    listed = await client.get("/api/memory", headers=auth)
    ids = {m["id"] for m in listed.json()}
    assert mid not in ids

    row = await mem_db._fetchrow(
        "SELECT deleted_at FROM memories WHERE id = $1", mid
    )
    assert row is not None and row["deleted_at"] is not None

    audit = await client.get("/api/memory/audit", headers=auth)
    assert any(a["action"] == "delete" and a.get("memoryId") == mid for a in audit.json())
