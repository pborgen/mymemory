# MyMemory

Tell a chatbot facts about your life — "my car license plate is 8XYZ123" — and
ask for them back later — "what's my license plate?". Vector RAG over your own
private memories.

Monorepo:

- `apps/api` — FastAPI + Postgres/pgvector backend (the memory engine).
- `apps/mobile` — Expo / React Native iOS app (chat + voice + memories list).
- `apps/agent` — LangChain `memory` agent CLI (for local testing).
- `apps/web` — Next.js web client.

## Quick start (Mac, models on this machine)

Runs Postgres in Docker and chat/embeddings via **local Ollama** (Apple Silicon
or Intel). No Tailscale GPU box and no AWS required.

```bash
# Prerequisites: Docker Desktop + Ollama (https://ollama.com or brew install ollama)

# 1. Copy Mac-local API env (or use the committed defaults in .env.example)
cd apps/api
cp .env.mac.example .env   # skip if .env already points at localhost Ollama
uv sync

# 2. From repo root: Postgres + pull models + API
cd ../..
npm run mac:dev            # db:up + mac:models + api:dev → http://localhost:8080

# Or step by step:
npm run db:up              # pgvector on localhost:5544
npm run mac:models         # pulls qwen2.5 + mxbai-embed-large
npm run api:dev

# 3. Web UI
npm run web:dev            # http://localhost:3000

# 4. Or CLI agent
cd apps/agent && uv sync && uv run memory
```

Switch back to the remote Tailscale vLLM/Ollama hosts by uncommenting the
alternate block in `apps/api/.env` (see comments there).

See [CLAUDE.md](CLAUDE.md) for architecture details.
