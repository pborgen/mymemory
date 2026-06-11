# syntax=docker/dockerfile:1
#
# Python FastAPI backend (apps/api) for MyMemory — API only (the mobile client
# is a separate native Expo app, not served here).
# Build context must be the repo root:
#   docker build -f apps/api/Dockerfile -t mymemory-api .

FROM python:3.12-slim AS runner
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8080

WORKDIR /app/apps/api

# Install deps first (cached unless pyproject/lock change).
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# App source.
COPY apps/api/ ./
RUN uv sync --frozen --no-dev

EXPOSE 8080
# Run from the venv built above. --no-sync prevents uv from re-resolving/building
# at startup (which would hit PyPI — impossible behind the VPC connector with no
# NAT, and unnecessary since the image is already fully built).
CMD ["uv", "run", "--frozen", "--no-sync", "--no-dev", "api"]
