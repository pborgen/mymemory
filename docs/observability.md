# Observability — debugging and monitoring chat

Phase 2 of the AI engineer prep path. Goal: answer *“Walk me through debugging
a wrong answer in prod”* with a concrete path in MyMemory.

---

## Request correlation

Every HTTP request gets an `X-Request-Id` (middleware). Chat also returns
`requestId` in the JSON body and stores it on the assistant message `meta`.

| Where | Field |
| --- | --- |
| Response header | `X-Request-Id` |
| Chat JSON | `requestId` |
| Assistant `meta` | `requestId`, `timingsMs`, `memoryIds`, `promptVersions`, `emptyRetrieval` |
| Table | `chat_metrics.request_id` |
| Logs | JSON line field `requestId` |

**Debug drill**

1. User reports a bad answer → get `requestId` from the chat UI (short hash) or logs.
2. `GET /api/memory/debug/{requestId}` (admin) → action, timings, memory count, prompt versions, emptyRetrieval.
3. Cross-check prompt version in admin UI / history.
4. Fix (data / prompt / retrieval) → eval → activate with change note.

---

## Structured logs

Logs are one JSON object per line (`api.observability.JsonLogFormatter`).

Example chat event fields:

- `event`: `memory.chat` or `memory.chat.error`
- `requestId`, `email`, `sessionId`, `action`
- `emptyRetrieval`, `memoryIds`, `timingsMs`, `promptVersions`

---

## Metrics (SLIs)

Table `chat_metrics` records every chat turn. Admin UI: `/admin/metrics`.

| Signal | Why |
| --- | --- |
| request / error counts | Classic health |
| avg / p95 total latency | UX |
| classify / retrieve / generate avg | Where time goes |
| empty retrieval count | Soft RAG failure |
| store vs recall counts | Routing health |
| thumbs up/down | Online quality (`chat_feedback`) |

API: `GET /api/metrics/summary?hours=24` (admin).

---

## Feedback

`POST /api/memory/chat/feedback` with `{ requestId, rating: 1|-1, comment? }`.

Web chat shows 👍 / 👎 on assistant bubbles when `requestId` is present.

---

## Health

`GET /api/health` → Postgres required; Redis best-effort; reports gen/embed providers.

---

## Interview lines

> “Every chat turn gets a request ID, prompt version pins, retrieved memory IDs,
> and stage timings in structured logs and `chat_metrics`. I look up a bad answer
> by request ID and see whether it was empty retrieval, routing, or generation.”

> “I monitor empty-retrieval rate separately from HTTP 5xx — RAG fails soft.”

---

## What’s still optional (later)

- Prometheus / Grafana exporters
- Alerting on p95 / empty-retrieval spikes
- Full replay script that re-runs classify/retrieve/generate from a saved envelope
- Hard timeouts + circuit breaker on the Tailscale LLM hosts

---

## Langfuse (LLM traces)

Optional. **Off by default** — leave keys unset and the app behaves as before.

| Env | Purpose |
| --- | --- |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Enable tracing (auto when both set) |
| `LANGFUSE_BASE_URL` | Cloud default, or self-host URL |
| `LANGFUSE_ENABLED` | Force `true`/`false` |

Each `POST /api/memory/chat` emits a `memory-chat` chain with nested observations:

| Name | Type |
| --- | --- |
| `memory-chat` | chain (root; session + user + tags) |
| `classify-intent` / `generate-response` | generation (OpenAI drop-in when `GEN_PROVIDER=openai`) |
| `retrieve-context` | retriever |
| `embed-memory` | embedding |
| `block-*` | guardrail |

Trace id is seeded from `requestId` so thumbs map to score `user-thumbs`.
PII-shaped strings are masked before export. Set
`LANGFUSE_TRACING_ENVIRONMENT` (`development` default) so local traces stay
out of production dashboards.

Setup: [`infra/langfuse/README.md`](../infra/langfuse/README.md). Cursor skill:
`.agents/skills/langfuse` (symlink under `.cursor/skills/langfuse`).

`GET /api/health` reports `checks.langfuse.enabled`. Chat JSON includes
`langfuseTraceId` when enabled.
