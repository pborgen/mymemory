"""Per-user feature toggles — defaults keep the chat UI uncluttered.

Stored as JSONB on `profiles.settings`. Unknown keys are ignored on write;
reads always merge with DEFAULT_SETTINGS so new features appear safely.
"""
from __future__ import annotations

from typing import Any

# Keys the API accepts. Values are booleans unless noted in FEATURE_CATALOG.
DEFAULT_SETTINGS: dict[str, bool] = {
    # Looking — UI chrome
    "quickChips": False,
    "showSources": False,
    "entityCards": False,
    "sensitiveLock": False,
    # Smart chat — conversation intelligence
    "forgetByTopic": True,
    "editCorrect": True,
    "conflictDetection": False,
    "timeAwareAnswers": False,
    # Library — bring facts in / take them out
    "pasteInbox": False,
    "importExport": False,
    "reminders": False,
    # Devices — platform extras
    "whisperMic": False,
    "iosIntegrations": False,
}

# Stable rail order (Map insertion order follows first appearance in catalog).
GROUP_ORDER: list[str] = ["Looking", "Smart chat", "Library", "Devices"]

FEATURE_CATALOG: list[dict[str, Any]] = [
    # ── Looking ───────────────────────────────────────────
    {
        "key": "quickChips",
        "group": "Looking",
        "subgroup": "Chat chrome",
        "name": "Quick chips after save",
        "description": "Show Undo / Ask later shortcuts under a newly saved memory.",
    },
    {
        "key": "showSources",
        "group": "Looking",
        "subgroup": "Chat chrome",
        "name": "Show why this answer",
        "description": "List the memories used to ground each recall reply.",
    },
    {
        "key": "entityCards",
        "group": "Looking",
        "subgroup": "Memories list",
        "name": "Entity cards",
        "description": "Group memories by person/place (Jenna, car, …) on the Memories screen.",
    },
    {
        "key": "sensitiveLock",
        "group": "Looking",
        "subgroup": "Memories list",
        "name": "Sensitive lock",
        "description": "Blur high-sensitivity memories in the list until you tap to reveal.",
    },
    # ── Smart chat ────────────────────────────────────────
    {
        "key": "forgetByTopic",
        "group": "Smart chat",
        "subgroup": "Undo & edit",
        "name": "Forget by topic",
        "description": "Say “forget my wifi password” to remove a matching memory, not only the last one.",
    },
    {
        "key": "editCorrect",
        "group": "Smart chat",
        "subgroup": "Undo & edit",
        "name": "Edit / correct memories",
        "description": "Say “actually my plate is …” to update an existing fact instead of duplicating it.",
    },
    {
        "key": "conflictDetection",
        "group": "Smart chat",
        "subgroup": "Answers",
        "name": "Conflict detection",
        "description": "When a new fact overlaps an old one, update the earlier memory instead of storing a duplicate.",
    },
    {
        "key": "timeAwareAnswers",
        "group": "Smart chat",
        "subgroup": "Answers",
        "name": "Time-aware answers",
        "description": "Prefer newer memories when answering (e.g. current vs old address).",
    },
    # ── Library ───────────────────────────────────────────
    {
        "key": "pasteInbox",
        "group": "Library",
        "subgroup": "Import",
        "name": "Paste inbox",
        "description": "Paste several facts at once from Settings and save each line as a memory.",
    },
    {
        "key": "importExport",
        "group": "Library",
        "subgroup": "Import",
        "name": "Import / export",
        "description": "Download all memories as JSON, import a text/CSV dump, or delete everything.",
    },
    {
        "key": "reminders",
        "group": "Library",
        "subgroup": "Follow-ups",
        "name": "Reminders",
        "description": "Say “remind me to …” in chat; manage due items under Settings.",
    },
    # ── Devices ───────────────────────────────────────────
    {
        "key": "whisperMic",
        "group": "Devices",
        "subgroup": "Voice",
        "name": "Enhanced mic (Whisper)",
        "description": "Prefer higher-accuracy speech recognition when the server supports it (falls back to on-device).",
    },
    {
        "key": "iosIntegrations",
        "group": "Devices",
        "subgroup": "Apple",
        "name": "iOS Shortcuts & widget tips",
        "description": "Show deep-link / Shortcuts tips for Siri and home-screen capture.",
    },
]


def ordered_groups(catalog: list[dict[str, Any]] | None = None) -> list[str]:
    """Group names in rail order, then any unknown groups alphabetically."""
    items = catalog if catalog is not None else FEATURE_CATALOG
    seen = {str(i.get("group") or "") for i in items}
    ordered = [g for g in GROUP_ORDER if g in seen]
    extras = sorted(g for g in seen if g and g not in GROUP_ORDER)
    return ordered + extras


def merge_settings(raw: dict | None) -> dict[str, bool]:
    """Return a full settings dict with defaults filled in."""
    out = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for key, default in DEFAULT_SETTINGS.items():
            if key in raw:
                out[key] = bool(raw[key])
    return out


def patch_settings(current: dict | None, updates: dict) -> dict[str, bool]:
    """Apply a partial update; ignore unknown keys."""
    merged = merge_settings(current)
    if not isinstance(updates, dict):
        return merged
    for key in DEFAULT_SETTINGS:
        if key in updates:
            merged[key] = bool(updates[key])
    return merged
