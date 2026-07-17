"""MyMemory MCP server — a learning-focused wrapper around the FastAPI API.

MCP servers expose three primitives (who decides to use each one differs):

  Tools      — the *model* calls these to take actions (store / recall / list)
  Resources  — the *host* (Cursor) loads these into context (read-only data)
  Prompts    — the *user* picks these by name (reusable message templates)

Run over stdio (what Cursor uses locally):

  uv run mymemory-mcp

Or open the MCP Inspector to poke at tools/resources/prompts by hand:

  uv run mcp dev src/mymemory_mcp/server.py
"""
from __future__ import annotations

import json
import uuid

from mcp.server.fastmcp import FastMCP

from . import api

mcp = FastMCP(
    "mymemory",
    instructions=(
        "Personal memory store for the MyMemory app. Use remember to save "
        "facts, recall to ask questions grounded in saved memories, and "
        "list_memories to see everything stored for the current user. "
        "Read memory://list for a snapshot of all memories."
    ),
)


# ---------------------------------------------------------------------------
# Tools — model-controlled actions (may have side effects)
# ---------------------------------------------------------------------------


@mcp.tool()
def remember(fact: str) -> str:
    """Save a fact about the user to their personal memory.

    Pass a clean, self-contained statement
    (e.g. "The user's car license plate is 8XYZ123").
    """
    return api.request("POST", "/api/memory", body={"content": fact, "source": "mcp"})


@mcp.tool()
def recall(question: str) -> str:
    """Ask a question answered from the user's saved memories.

    Example: "what is my license plate?"
    """
    return api.request(
        "POST",
        "/api/memory/chat",
        body={"message": question, "source": "mcp"},
    )


@mcp.tool()
def list_memories() -> str:
    """List every memory currently saved for the user."""
    return api.request("GET", "/api/memory")


@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete one memory by its id (from list_memories).

    Only UUIDs from list_memories are accepted — the API also scopes delete
    to the authenticated user (tool allowlist + authz).
    """
    try:
        uuid.UUID(memory_id)
    except (ValueError, TypeError, AttributeError):
        return json.dumps({"error": "memory_id must be a UUID from list_memories"})
    return api.request("DELETE", f"/api/memory/{memory_id}")


# ---------------------------------------------------------------------------
# Resources — application-controlled, read-only data
# ---------------------------------------------------------------------------


@mcp.resource("memory://list")
def memories_resource() -> str:
    """Snapshot of all memories for the current user (read-only)."""
    return api.request("GET", "/api/memory")


@mcp.resource("memory://{memory_id}")
def memory_resource(memory_id: str) -> str:
    """One memory looked up by id from the full list.

    MCP resource templates can't do arbitrary filters, so we fetch the list
    and pick the matching row. Prefer the list_memories tool for browsing.
    """
    raw = api.request("GET", "/api/memory")
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not isinstance(items, list):
        return raw
    for item in items:
        if isinstance(item, dict) and str(item.get("id")) == memory_id:
            return json.dumps(item, indent=2)
    return json.dumps({"error": "Not found", "id": memory_id})


# ---------------------------------------------------------------------------
# Prompts — user-controlled message templates
# ---------------------------------------------------------------------------


@mcp.prompt()
def remember_this(fact: str) -> str:
    """Draft a request to store a fact in MyMemory."""
    return (
        "Use the MyMemory `remember` tool to store this fact exactly "
        f"(do not rephrase):\n\n{fact}"
    )


@mcp.prompt()
def ask_memory(question: str) -> str:
    """Draft a request to recall something from MyMemory."""
    return (
        "Use the MyMemory `recall` tool to answer this question from "
        f"saved memories:\n\n{question}"
    )


def main() -> None:
    # stdio is the transport Cursor / Claude Desktop use for local servers.
    # Do not print to stdout — that channel is reserved for JSON-RPC.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
