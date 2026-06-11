# MyMemory

Tell a chatbot facts about your life — "my car license plate is 8XYZ123" — and
ask for them back later — "what's my license plate?". Vector RAG over your own
private memories.

Monorepo:

- `apps/api` — FastAPI + Postgres/pgvector backend (the memory engine).
- `apps/mobile` — Expo / React Native iOS app (chat + voice + memories list).
- `apps/agent` — LangChain `memory` agent CLI (for local testing).

## Quick start

```bash
# 1. Backend (needs Postgres with pgvector + AWS Bedrock access)
cd apps/api
cp .env.example .env        # set POSTGRES_URL, AWS_REGION, ALLOW_DEV_AUTH_HEADERS=true
uv sync
uv run api                  # http://localhost:8080

# 2. Try it from the CLI
cd ../agent
uv sync
uv run memory               # interactive remember / recall

# 3. Mobile app (Expo dev build for voice + Google sign-in)
cd ../mobile
npm install
EXPO_PUBLIC_API_URL=http://localhost:8080 npx expo start
```

See [CLAUDE.md](CLAUDE.md) for architecture details.
