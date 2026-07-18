# Optional local Langfuse (self-hosted)

MyMemory works **without** Langfuse. Tracing is a no-op until keys are set.

## Recommended local-friendly path: Langfuse Cloud (free)

1. Create a project at https://cloud.langfuse.com
2. Copy Public + Secret keys into `apps/api/.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
# optional; auto-enables when both keys are set
# LANGFUSE_ENABLED=true
```

3. Restart the API (`🐍 API (FastAPI :8099)` or `npm run api:dev`).
4. Send a chat turn → open Langfuse Traces → look for `memory.chat`.
5. Thumbs up/down in the UI scores the same trace (`user-feedback`).

No Docker, no conflict with Next.js `:3000` or Postgres `:5544`.

## Optional: self-host with Docker Compose

Langfuse’s full stack needs Postgres + ClickHouse + Redis + S3-compatible storage.
Use their official compose (don’t reuse the MyMemory `mymemory-pg` container):

```bash
# From https://langfuse.com/docs/deployment/self-host
# Map the web UI to :3100 so it doesn’t clash with Next.js :3000.
```

Then point the API at your instance:

```bash
LANGFUSE_BASE_URL=http://localhost:3100
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

## What gets traced

| Observation | Type |
| --- | --- |
| `memory.chat` | chain (root; trace id seeded from `requestId`) |
| `classify` / `generate` | generation |
| `retrieve` | retriever |
| `embed.store` | embedding |
| guardrails | guardrail |

See `docs/observability.md`.
