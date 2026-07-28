# MyMemory App

A personal memory store. A user (or any entity) tells a chatbot facts about
their life — "my car license plate is 8XYZ123" — and later asks for them back —
"what's my license plate?". Storage and recall are powered by vector RAG.

## Project Structure

Monorepo with npm workspaces:

- `apps/api` — **Python FastAPI backend** (standalone `uv` project). The single
  backend: serves all `/api/*` routes, raw SQL via `asyncpg`, pgvector for
  semantic memory search. The memory RAG lives under `src/api/memory/`. Routers
  are one file per feature in `src/api/routers/`, registered in `main.py`. Run
  with `uv run api` from `apps/api/`.
- `apps/mobile` — **Expo / React Native** client (TypeScript, expo-router). The
  iOS app: chat screen + memories list + login. Talks to the FastAPI backend;
  base URL from `EXPO_PUBLIC_API_URL`. No server code here.
- `apps/agent` — **Python LangChain agents** (standalone `uv` project, not an npm
  workspace). The `memory` agent is a tool-using CLI (`remember`/`recall` tools
  that call the API). One folder per agent under `src/agents/`; `common/` holds
  shared model/config helpers. Run with `uv run memory` from `apps/agent/`.
- `apps/mcp` — **MCP server** (standalone `uv` project). Exposes MyMemory to
  Cursor via the Model Context Protocol: tools (`remember`/`recall`/…), a
  `memory://` resource, and prompt templates. Talks to the FastAPI API over
  httpx. Run with `uv run mymemory-mcp` from `apps/mcp/`; Cursor config is
  `.cursor/mcp.json`.

## Tech Stack

- **Frontend:** Expo / React Native, expo-router (file-based), TanStack React
  Query, TypeScript. On-device iOS speech-to-text for voice input.
- **Backend:** FastAPI (Python) — async, `asyncpg`, raw SQL, no ORM.
- **Database:** PostgreSQL + **pgvector** — tables auto-created on startup
  (`ensure_tables()` in `apps/api/src/api/db.py`).
- **Auth:** Google OAuth (Bearer) + dev `x-user-email` header. Email is the
  primary user identifier; memories are scoped per email.
- **AI:** Pluggable model providers, configured independently for generation and
  embeddings (`GEN_PROVIDER` / `EMBED_PROVIDER` — each one of `openai` /
  `ollama` / `bedrock`; see `apps/api/src/api/config.py`).
  - **Where the models run — Mac local (default for laptop dev):** both
    generation and embeddings on **Ollama on this Mac**
    (`http://localhost:11434`). Copy `apps/api/.env.mac.example` → `.env`, then
    `npm run db:up` + `npm run mac:models` + `npm run api:dev`.
    - *Generation:* `GEN_PROVIDER=ollama`, model `qwen2.5` (or any chat model
      you `ollama pull`).
    - *Embeddings:* `EMBED_PROVIDER=ollama`, model `mxbai-embed-large`
      (1024-dim, matches `VECTOR(1024)`). Already-pulled `nomic-embed-text`
      works if you set `EMBED_DIM=768` on a fresh DB.
  - **Alternate — Tailscale GPU box:** generation via **vLLM** at
    `http://100.99.15.47:8001/v1` (`GEN_PROVIDER=openai`) and embeddings via
    remote Ollama at `http://100.99.15.47:11434`. Requires Tailscale; if either
    host is unreachable, `POST /api/memory/chat` fails at embed/generate.
    Settings are commented in `apps/api/.env` for easy switching.
  - AWS Bedrock (Claude/Nova generation, Amazon Titan embeddings) remains
    available by setting the relevant provider to `bedrock`.
  - **Restarting Ollama on the remote box (`100.99.15.47`, over Tailscale):**
    Ollama is a **user-local install** at `~/.local/bin/ollama` (no `sudo` on
    that host — sudo needs a password) and is **not** a systemd service, so it
    does **not** survive a reboot. If remote embed fails, SSH in as `paul` and
    restart it:
    ```bash
    ssh paul@100.99.15.47        # Tailscale SSH; remote user is `paul`
    OLLAMA_HOST=0.0.0.0:11434 setsid nohup ~/.local/bin/ollama serve \
      > ~/.ollama/logs/serve.log 2>&1 < /dev/null &
    ~/.local/bin/ollama pull mxbai-embed-large   # only if the model is missing
    ```
    Verify from a tailnet machine: `curl http://100.99.15.47:11434/api/tags`.
    Binds to `0.0.0.0` so it's reachable over the tailnet; the GPU is held by
    vLLM, so embeddings run on CPU.

## Commands

```bash
# From repo root (Mac-local):
npm run db:up          # Postgres + pgvector on :5544 (Docker)
npm run mac:models     # Ensure local Ollama chat + embed models
npm run mac:dev        # db:up + mac:models + api:dev
npm run api:dev        # FastAPI (uvicorn --reload, :8080)
npm run web:dev        # Next.js web client
npm run mobile:dev     # Expo dev server
npm run agent:memory   # Memory agent CLI

# From apps/api:
uv run api             # Start the FastAPI server
uv sync                # Install/refresh Python deps
```

## Environment Variables

Copy `apps/api/.env.example` → `apps/api/.env`:

- `POSTGRES_URL` — PostgreSQL connection string (DB must have the `pgvector`
  extension available; the app runs `CREATE EXTENSION IF NOT EXISTS vector`).
- `ALLOW_DEV_AUTH_HEADERS=true` — Enables dev auth via `x-user-email` header.
- `GOOGLE_CLIENT_ID` — For production Google OAuth.
- `AWS_REGION` — Bedrock region (credentials via the standard AWS chain).
- `RAG_MODEL_ID` — Bedrock Claude model for answer generation.
- `EMBED_MODEL_ID` — Bedrock embedding model (default Titan Text Embeddings v2).

## Architecture Conventions

### Memory engine (`apps/api/src/api/memory/`)

The core loop is `POST /api/memory/chat`. Per message it:
1. Classifies intent (store a fact vs. ask a question) with a cheap Claude call.
2. **Store:** normalize the fact → embed (Titan) → `INSERT` into `memories`.
3. **Recall:** embed the query → pgvector cosine top-k over the user's memories
   → Claude answers grounded ONLY in the retrieved memories, citing sources.

Files mirror a classic RAG split: `embeddings.py` (Titan embed call),
`retrieval.py` (pgvector cosine search), `generation.py` (Claude on Bedrock),
`db.py` (memory + chat-history tables), `engine.py` (the store-or-recall router).

### Database (`apps/api/src/api/db.py`, `memory/db.py`)

- All schema in `ensure_tables()` / `ensure_memory_tables()` — created if not
  exists; migrations via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- Raw SQL via `asyncpg` — no ORM. JSONB codec in `_init_conn`. UUIDs via
  `uuid.uuid4()`. snake_case columns; helpers return camelCase dicts.
- Vectors stored in a `VECTOR(1024)` column (pgvector), HNSW cosine index.
  asyncpg sends the embedding as a `'[...]'` string literal cast to `vector`.

### Server (`apps/api/src/api/`)

- Routes grouped by feature into routers under `routers/`, registered in
  `main.py`'s `include_router` loop.
- Auth via FastAPI dependencies in `auth.py`: `require_user`. Reads
  `x-user-email` (dev) or `Authorization: Bearer` (prod Google ID token).
- Errors returned as `{ "error": "..." }` via exception handlers in `main.py`.

### Client (`apps/mobile`)

- **Screens** in `app/` (expo-router): `login`, `index` (chat), `memories`.
- **API client** in `src/api.ts` — thin wrappers around `apiFetch<T>(method, path, body)`.
- **Auth** in `src/auth.tsx` — React context, token in `expo-secure-store`.
- React Query for reads/writes; invalidate on mutation success.

## Adding a New Feature (typical flow)

1. Add table/columns + DB helpers in `apps/api/src/api/db.py` (or `memory/db.py`).
2. Add a router in `apps/api/src/api/routers/` and register it in `main.py`.
3. Add API client functions in `apps/mobile/src/api.ts`.
4. Add a React Query hook + screen in `apps/mobile/app/`.
