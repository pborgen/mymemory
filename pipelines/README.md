# Local data pipeline (Phase 6)

Laptop-friendly lake → chunk → embed → store, with lineage. **No AWS / MinIO /
DuckDB / Bedrock required** for the default path.

| Concept | Local default | Optional later |
| --- | --- | --- |
| Object lake (S3) | `data/raw/` | MinIO |
| ETL (Glue) | `pipelines/ingest.py` + `chunk.py` | Step Functions / Glue |
| Serving / embed (Lambda) | `POST /api/memory` on localhost | container job |
| Warehouse (Snowflake) | Postgres + `data/warehouse/facts.jsonl` | DuckDB file / Snowflake trial |

## Prerequisites

Same as day-to-day MyMemory:

1. Postgres (local) + API on `:8080`
2. Embeddings via your existing local/Tailscale providers (`EMBED_PROVIDER=ollama`, etc.)
3. `ALLOW_DEV_AUTH_HEADERS=true`

## Run

```bash
# Terminal 1
npm run api:dev

# Terminal 2 — dry-run (no embed; writes data/stage only)
cd pipelines
uv run --project ../apps/api python ingest.py --dry-run

# Full ingest (embeds via API — needs Ollama/vLLM reachable as usual)
MEMORY_USER_EMAIL=alex@dev.local \
  uv run --project ../apps/api python ingest.py

# Report
uv run --project ../apps/api python report.py --loan LN-2026-4418
uv run --project ../apps/api python report.py --tag underwriting
uv run --project ../apps/api python report.py --offline   # JSONL only
```

Sample raw docs live in `data/raw/mortgage/`.

## Lineage columns

Each pipeline-loaded memory stores:

- `sourceUri` — e.g. `raw/mortgage/LN-2026-4418_rate_lock.txt`
- `ingestedAt` — set when lineage is present
- `pipelineVersion` — e.g. `ingest-v1`

Chat-created memories leave these empty (still fully local-friendly).

## Architecture map

See [`docs/data-architecture.md`](../docs/data-architecture.md).
