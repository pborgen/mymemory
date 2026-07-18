# Data architecture — local first, mapped to AWS

MyMemory’s default stack stays on your laptop / Tailscale GPU box. Phase 6 adds
a **local lake → transform → embed → serve / warehouse** path so FinTech
interview stories map cleanly to S3 / Glue / Snowflake / Lambda **without
deploying any of those**.

## Local topology (what you actually run)

```text
data/raw/                 # immutable landing zone (S3 stand-in)
    └── mortgage/*.txt
         │
         ▼
pipelines/ingest.py       # extract + chunk (Glue / ETL stand-in)
    └── data/stage/*.jsonl
         │
         ▼
POST /api/memory          # embed-on-ingest via existing providers
    │                     # (Ollama / vLLM on Tailscale — unchanged)
    ├── Postgres+pgvector # online RAG store
    └── data/warehouse/facts.jsonl   # append-only warehouse extract
```

**Chat and mobile keep working exactly as before.** Pipeline lineage fields are
optional; chat-created memories leave `sourceUri` / `pipelineVersion` empty.

### Local-friendly guarantees

| Requirement | How we keep it local |
| --- | --- |
| No AWS account | File landing zone + local API |
| No MinIO daemon | `data/raw/` on disk (swap to MinIO later if you want) |
| No DuckDB install | Warehouse = JSONL (+ live `GET /api/memory/report`) |
| Same embed/gen | Reuses `EMBED_PROVIDER` / `GEN_PROVIDER` already in `.env` |
| Offline demo | `ingest.py --dry-run` + `report.py --offline` |

## Lineage

On pipeline load, each memory row stores:

| Column | Example | Purpose |
| --- | --- | --- |
| `source_uri` | `raw/mortgage/LN-2026-4418_rate_lock.txt` | Trace fact → file |
| `ingested_at` | timestamptz | When the pipeline wrote it |
| `pipeline_version` | `ingest-v1` | Reproducible transform |

Reporting:

```bash
curl -H 'x-user-email: alex@dev.local' \
  'http://localhost:8080/api/memory/report?loan=LN-2026-4418'
```

## Map to a FinServ / AWS JD

| JD skill | This repo | Interview line |
| --- | --- | --- |
| **S3 data lake** | `data/raw/` immutable landing | “Raw docs land once; transforms never rewrite raw.” |
| **Glue / ETL** | `pipelines/chunk.py` + `ingest.py` | “Extract → clean/chunk → stage JSONL → load.” |
| **Lambda / batch job** | CLI ingest (cron-able) | “Embed-on-ingest job calls the same API the app uses.” |
| **pgvector / RAG API** | FastAPI + Postgres | “Online store for retrieval; Bedrock optional later.” |
| **Snowflake / warehouse** | `facts.jsonl` + `/api/memory/report` | “Append-only facts with tags + lineage for audits.” |
| **Bedrock** | `GEN_PROVIDER=bedrock` (optional) | “Same API; swap provider env — no rewrite.” |
| **IAM** | Dev `x-user-email` today | “Prod: least-privilege task role; no long-lived keys in app.” |

## Optional upgrades (still not required)

1. **MinIO** — point `RAW_DIR` at an `s3://` bucket via `aws s3 sync` or boto3; keep the same relative `source_uri` scheme.
2. **DuckDB** — `READ` the JSONL warehouse for SQL demos (`SELECT * FROM 'data/warehouse/facts.jsonl'`).
3. **Snowflake trial** — load JSONL with a COPY; keep Postgres as the online RAG store.
4. **Bedrock** — flip providers in `.env`; re-run ingest to compare embed quality.

## Commands cheat sheet

```bash
npm run api:dev

cd pipelines
uv run --project ../apps/api python ingest.py --dry-run
MEMORY_USER_EMAIL=alex@dev.local uv run --project ../apps/api python ingest.py
uv run --project ../apps/api python report.py --loan LN-2026-4418
```

See also: [`pipelines/README.md`](../pipelines/README.md), mortgage demo
[`demos/mortgage/`](../demos/mortgage/).
