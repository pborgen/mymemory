#!/usr/bin/env bash
# Start local pgvector Postgres on :5544 (reuse legacy container or compose).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--reset" ]]; then
  docker rm -f mymemory-pg >/dev/null 2>&1 || true
  docker compose down -v
  docker compose up -d postgres
else
  if docker inspect mymemory-pg >/dev/null 2>&1; then
    docker start mymemory-pg >/dev/null
  else
    docker compose up -d postgres
  fi
fi

for i in $(seq 1 30); do
  if docker exec mymemory-pg pg_isready -U postgres >/dev/null 2>&1; then
    echo "Postgres ready on localhost:5544 (container mymemory-pg)"
    exit 0
  fi
  sleep 0.5
done

echo "postgres did not become ready" >&2
exit 1
