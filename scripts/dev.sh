#!/usr/bin/env bash
# Dev launcher: checks Postgres, starts the FastAPI backend.
set -euo pipefail

cd "$(dirname "$0")/.."

API_DIR="apps/api"

# Load POSTGRES_URL from apps/api/.env if present
if [ -f "$API_DIR/.env" ]; then
  # shellcheck disable=SC1090
  set -a; source "$API_DIR/.env"; set +a
fi

PG_URL="${POSTGRES_URL:-${DATABASE_URL:-}}"
if [ -z "$PG_URL" ]; then
  echo "POSTGRES_URL not set. Copy $API_DIR/.env.example to $API_DIR/.env first." >&2
  exit 1
fi

echo "Checking Postgres connectivity…"
if command -v psql >/dev/null 2>&1; then
  psql "$PG_URL" -c "SELECT 1;" >/dev/null || {
    echo "Could not connect to Postgres at \$POSTGRES_URL" >&2; exit 1; }
  echo "Postgres OK."
else
  echo "psql not found — skipping connectivity check."
fi

echo "Starting FastAPI on :${PORT:-8080} …"
cd "$API_DIR"
exec uv run uvicorn api.main:app --reload --port "${PORT:-8080}"
