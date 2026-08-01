"""Per-user feature toggles — defaults keep the chat UI uncluttered.

Stored as JSONB on `profiles.settings`. Unknown keys are ignored on write;
reads always merge with DEFAULT_SETTINGS so new features appear safely.
"""
from __future__ import annotations

from typing import Any

# Keys the API accepts. Values are booleans unless noted in FEATURE_CATALOG.
DEFAULT_SETTINGS: dict[str, bool] = {
    # Chat UX (can add UI chrome)
    "quickChips": False,
    "showSources": False,
    # Chat intelligence (mostly invisible until used in conversation)
    "forgetByTopic": True,
    "editCorrect": True,
    "conflictDetection": False,
    "timeAwareAnswers": False,
    # Memories UI
    "entityCards": False,
    "sensitiveLock": False,
    # Capture / data
    "pasteInbox": False,
    "importExport": False,
    "reminders": False,
    # Advanced / experimental
    "whisperMic": False,
    "iosIntegrations": False,
}

FEATURE_CATALOG: list[dict[str, Any]] = [
    {
        "key": "quickChips",
        "group": "Chat",
        "name": "Quick chips after save",
        "description": "Show Undo / Ask later shortcuts under a newly saved memory.",
    },
    {
        "key": "showSources",
        "group": "Chat",
        "name": "Show why this answer",
        "description": "List the memories used to ground each recall reply.",
    },
    {
        "key": "forgetByTopic",
        "group": "Chat",
        "name": "Forget by topic",
        "description": "Say “forget my wifi password” to remove a matching memory, not only the last one.",
    },
    {
        "key": "editCorrect",
        "group": "Chat",
        "name": "Edit / correct memories",
        "description": "Say “actually my plate is …” to update an existing fact instead of duplicating it.",
    },
    {
        "key": "conflictDetection",
        "group": "Chat",
        "name": "Conflict detection",
        "description": "When a new fact overlaps an old one, update the earlier memory instead of storing a duplicate.",
    },
    {
        "key": "timeAwareAnswers",
        "group": "Chat",
        "name": "Time-aware answers",
        "description": "Prefer newer memories when answering (e.g. current vs old address).",
    },
    {
        "key": "entityCards",
        "group": "Memories",
        "name": "Entity cards",
        "description": "Group memories by person/place (Jenna, car, …) on the Memories screen.",
    },
    {
        "key": "sensitiveLock",
        "group": "Memories",
        "name": "Sensitive lock",
        "description": "Blur high-sensitivity memories in the list until you tap to reveal.",
    },
    {
        "key": "pasteInbox",
        "group": "Capture",
        "name": "Paste inbox",
        "description": "Paste several facts at once from Settings and save each line as a memory.",
    },
    {
        "key": "importExport",
        "group": "Capture",
        "name": "Import / export",
        "description": "Download all memories as JSON, import a text/CSV dump, or delete everything.",
    },
    {
        "key": "reminders",
        "group": "Capture",
        "name": "Reminders",
        "description": "Say “remind me to …” in chat; manage due items under Settings.",
    },
    {
        "key": "whisperMic",
        "group": "Advanced",
        "name": "Enhanced mic (Whisper)",
        "description": "Prefer higher-accuracy speech recognition when the server supports it (falls back to on-device).",
    },
    {
        "key": "iosIntegrations",
        "group": "Advanced",
        "name": "iOS Shortcuts & widget hints",
        "description": "Show deep-link / Shortcuts tips for Siri and home-screen capture.",
    },
]


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
