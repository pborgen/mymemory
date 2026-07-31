# MyMemory Web

Next.js (App Router) frontend, built as a **static export** for S3 + CloudFront
(`output: "export"` in `next.config.mjs`). No Node server in production.

1. **Marketing landing page** (`/`) — static, no auth.
2. **App** — browser client for the same FastAPI backend as iOS:
   - `/login/` — dev sign-in
   - `/chat/` — store + recall
   - `/memories/` — browse / edit entities
   - `/admin/…` — prompts, users, metrics

Auth uses `localStorage` + `x-user-email` (dev) or Google Bearer (prod).

## Local

```bash
cd apps/web
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8080
npm install
npm run dev                  # http://localhost:3000
```

Or from repo root: `npm run web:dev`.

Static preview:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080 npm run build
npm start                    # serves ./out on :3000
```

## Deploy to S3 + CloudFront

```bash
cd infra && terraform apply   # once: bucket + distribution

NEXT_PUBLIC_API_URL=https://YOUR-API.awsapprunner.com \
  ./deploy-web-static.sh
```

Custom domain (`memory.informedbydata.com`): see `infra/DOMAINS.md`.

## Notes

- `apps/web` is **not** an npm workspace package (avoids React 19 from Expo
  breaking the Next 14 static export). Install deps inside `apps/web/`.
- Prompt editor is `/admin/prompts/edit/?key=…` (no dynamic `[key]` routes —
  required for static export).
