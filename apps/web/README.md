# MyMemory Web

Next.js (App Router) web frontend for MyMemory. Two things in one app:

1. **Marketing landing page** (`/`) — advertises the product. Static, no auth.
2. **Functional web client** — a browser version of the iOS app:
   - `/login` — dev sign-in (lists accounts from `/api/dev/accounts`)
   - `/chat` — talk to the memory engine (store + recall)
   - `/memories` — browse and delete saved memories

It talks to the same FastAPI backend as `apps/mobile`, using the dev
`x-user-email` header for auth. Auth is persisted in `localStorage`.

## Run

```bash
# From repo root (after `npm install`):
npm run web:dev            # http://localhost:3000

# Or from apps/web:
npm run dev
```

The backend must be running and reachable from the browser. Point the web app
at it via `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8080`):

```bash
cp .env.example .env.local   # then edit NEXT_PUBLIC_API_URL if needed
```

Start the API with `ALLOW_DEV_AUTH_HEADERS=true` so the dev sign-in accounts
appear on the login screen. The backend already allows all CORS origins.

## Notes

- `src/theme.ts`, `src/types.ts`, and `src/api.ts` mirror their `apps/mobile`
  counterparts so web and iOS stay in sync. The web `api.ts` swaps
  expo-secure-store for `localStorage`.
- Production Google OAuth is wired on the backend (`POST /api/auth/google`) but
  not yet surfaced in the web UI — only dev sign-in is implemented here.
