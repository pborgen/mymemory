# Mortgage demo + governance

See the runnable demo under [`../demos/mortgage/`](../demos/mortgage/).

This page is the short pointer used from the job-prep roadmap (Phase 5 / FinServ).

## Governance features shipped

1. **`pii_tags` + `sensitivity`** on each memory (heuristic tags: loan_number, rate, ssn, …).
2. **Append-only `memory_audit_log`** for store / recall / blocked / delete.
3. **Soft delete** via `deleted_at` (search/list skip deleted rows).
4. **Documented retention** classes in `demos/mortgage/README.md`.

## Quick start

```bash
cd demos/mortgage
MEMORY_USER_EMAIL=alex@dev.local uv run --project ../../apps/api python seed.py
```

Then chat as Alex and run the demo script in that README.
