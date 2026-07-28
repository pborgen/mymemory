#!/usr/bin/env bash
# Ensure Ollama is up and pull the Mac-local chat + embed models.
set -euo pipefail

CHAT_MODEL="${OLLAMA_CHAT_MODEL:-qwen2.5}"
EMBED_MODEL="${EMBED_MODEL_ID:-mxbai-embed-large}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama not found. Install from https://ollama.com (or: brew install ollama)" >&2
  exit 1
fi

if ! curl -sf "http://localhost:11434/api/tags" >/dev/null; then
  echo "Starting Ollama serve..."
  # macOS app usually auto-serves; CLI fallback for headless / brew installs.
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  for i in $(seq 1 30); do
    curl -sf "http://localhost:11434/api/tags" >/dev/null && break
    sleep 0.5
  done
  if ! curl -sf "http://localhost:11434/api/tags" >/dev/null; then
    echo "Ollama did not become ready. Check /tmp/ollama-serve.log or open the Ollama app." >&2
    exit 1
  fi
fi

echo "Pulling chat model: ${CHAT_MODEL}"
ollama pull "${CHAT_MODEL}"

echo "Pulling embed model: ${EMBED_MODEL}"
ollama pull "${EMBED_MODEL}"

echo "Mac models ready:"
ollama list
