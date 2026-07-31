#!/usr/bin/env bash
# Start Caddy + cloudflared on the GPU box (foreground logs).
# Prefer systemd units in production; this is the smoke-test launcher.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v caddy >/dev/null; then
  echo "caddy not found — install from https://caddyserver.com/docs/install" >&2
  exit 1
fi
if ! command -v cloudflared >/dev/null; then
  echo "cloudflared not found — install from Cloudflare Zero Trust docs" >&2
  exit 1
fi
if grep -q 'REPLACE_WITH_HOME_GPU_API_KEY\|YOURDOMAIN\|TUNNEL_UUID' Caddyfile config.yml; then
  echo "Edit Caddyfile + config.yml first (see README.md)" >&2
  exit 1
fi

echo "Starting Caddy (vLLM :8787 → :8001, Ollama :8788 → :11434)…"
caddy run --config Caddyfile --adapter caddyfile &
CADDY_PID=$!
trap 'kill $CADDY_PID 2>/dev/null || true' EXIT

echo "Starting cloudflared tunnel…"
cloudflared tunnel --config config.yml run
