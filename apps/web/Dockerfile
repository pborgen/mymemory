# syntax=docker/dockerfile:1
#
# Next.js web client for MyMemory, deployed to App Runner as a Node SSR service.
# Build context must be the repo root:
#   docker build -f apps/web/Dockerfile --build-arg NEXT_PUBLIC_API_URL=https://… -t mymemory-web .
#
# NEXT_PUBLIC_API_URL is inlined into the client bundle at build time, so it must
# be passed as a build arg (the public HTTPS URL of the deployed FastAPI API).

# ── Build stage ───────────────────────────────────────────
FROM node:20-slim AS build
WORKDIR /app

# Install deps from the web app's own manifest (self-contained, not the workspace).
COPY apps/web/package.json ./
RUN npm install

COPY apps/web/ ./

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build   # output: "standalone" -> .next/standalone

# ── Runtime stage ─────────────────────────────────────────
FROM node:20-slim AS run
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The standalone output bundles a minimal node_modules + server.js.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
