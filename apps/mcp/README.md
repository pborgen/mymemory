# MyMemory MCP Server

A small [Model Context Protocol](https://modelcontextprotocol.io) server that
exposes the MyMemory API to Cursor (or any MCP host). Built to learn MCP:
tools, resources, and prompts over stdio.

## What you'll learn

| Primitive   | Who decides to use it | In this server                                      |
|-------------|-----------------------|-----------------------------------------------------|
| **Tool**    | The model             | `remember`, `recall`, `list_memories`, `delete_memory` |
| **Resource**| The host / app        | `memory://list`, `memory://{memory_id}`             |
| **Prompt**  | The user              | `remember_this`, `ask_memory`                       |

The server never talks to an LLM itself — it only exposes capabilities. Cursor
(the **host**) runs a **client** that speaks MCP to this process over stdin/stdout.

## Prerequisites

1. MyMemory API running locally (`npm run api:dev` from the repo root).
2. API has `ALLOW_DEV_AUTH_HEADERS=true` (see `apps/api/.env`).
3. `uv` installed.

## Setup

```bash
cd apps/mcp
cp .env.example .env   # optional; defaults match local API
uv sync
```

## Run

```bash
# What Cursor launches (stdio JSON-RPC on stdin/stdout):
uv run mymemory-mcp

# Interactive Inspector (browser UI to call tools by hand):
uv run mcp dev src/mymemory_mcp/server.py
```

## Wire into Cursor

Project config is at the repo root: `.cursor/mcp.json`. After pulling this
branch, open **Cursor Settings → MCP** and confirm `mymemory` is listed and
enabled. Restart MCP (or reload the window) if tools don't appear.

Manual equivalent:

```json
{
  "mcpServers": {
    "mymemory": {
      "command": "uv",
      "args": ["run", "mymemory-mcp"],
      "cwd": "apps/mcp",
      "env": {
        "MEMORY_API_URL": "http://localhost:8080",
        "MEMORY_USER_EMAIL": "paul@dev.local"
      }
    }
  }
}
```

## Try it in chat

With the API up and the MCP server enabled:

- "Remember that my bike lock combo is 42-17-9"
- "What is my bike lock combo?"
- "List my memories"

Or invoke the `remember_this` / `ask_memory` prompts from the MCP prompt picker.

## Layout

```
apps/mcp/
  pyproject.toml          # uv project + mymemory-mcp entrypoint
  src/mymemory_mcp/
    api.py                # httpx client → FastAPI
    server.py             # FastMCP: tools / resources / prompts
```

## Mental model

```
You ↔ Cursor (host)
         └─ MCP client  ←stdio JSON-RPC→  mymemory-mcp (this process)
                                              └─ httpx → apps/api FastAPI
                                                              └─ Postgres
```
