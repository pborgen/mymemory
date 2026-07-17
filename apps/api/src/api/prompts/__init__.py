"""Prompt management — global, versioned system prompts stored in the DB.

The hardcoded prompt strings that drive the AI (orchestrator agent + memory
engine) are registered here as defaults, seeded into the database on startup,
and resolved at runtime via `store.resolve_active(key)` / `get_active(key)`.
Editing a prompt appends a new version (each save requires a `changeNote` for
audit); rollback re-points the active version. Inference pins the active
version on each chat turn for production debugging. See `defaults.py` for the
registry, `db.py` for schema + helpers, and `store.py` for the cached resolver.
"""
