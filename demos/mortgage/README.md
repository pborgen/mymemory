# Mortgage / FinServ demo

Synthetic loan-file memories + governance features for interview storytelling.
**No real borrower PII** — all numbers and names are fake.

## What’s in the repo

| Artifact | Purpose |
| --- | --- |
| `demos/mortgage/loan_file.json` | Seed facts + sample questions |
| `demos/mortgage/seed.py` | POST facts into the API |
| `memories.pii_tags` / `sensitivity` | Governance tags on store |
| `memories.deleted_at` | Soft delete (retention-friendly) |
| `memory_audit_log` | Append-only who stored/recalled/blocked/deleted |
| `GET /api/memory/audit` | User-visible audit trail |

## Seed

```bash
# Terminal 1 — API
cd apps/api && uv run api

# Terminal 2 — seed as Alex (dev account)
cd demos/mortgage
MEMORY_API_URL=http://localhost:8080 \
MEMORY_USER_EMAIL=alex@dev.local \
uv run --project ../../apps/api python seed.py
```

(`uv run --project` pulls `httpx` from the API env.)

## Demo script (FinTech interviewer)

1. Sign in as `alex@dev.local`.
2. Ask: “What is my loan number?” → should return `LN-2026-4418` from memories.
3. Ask: “When does my rate lock expire?” → grounded answer only.
4. Ask: “What is my SSN?” → refuse / empty retrieval (never invent).
5. Try storing `My SSN is 123-45-6789` → PII guardrail blocks.
6. Open memories list → see `piiTags` like `loan_number`, `rate`, `underwriting`.
7. `GET /api/memory/audit` → show store/recall/blocked events with request IDs.
8. Delete a memory → soft-delete (`deleted_at`); audit shows `delete`.

## Retention policy (documented, not fully automated)

| Class | Policy (demo) |
| --- | --- |
| `normal` | Soft-delete on user request; eligible for hard purge after 90 days |
| `sensitive` | Soft-delete; review before purge; keep audit row |
| `restricted` | Requires `CONFIRM_SENSITIVE` to store; soft-delete only via authenticated user; audit retained |

Hard purge jobs are out of scope for this demo — the important interview point is
**soft delete + tags + immutable audit**.

## Interview line

> “I reframed the same RAG stack as a mortgage knowledge assistant over a
> synthetic loan file, with refuse-if-unknown, PII tags/sensitivity, soft-delete,
> and an append-only audit log of store/recall/block events.”
