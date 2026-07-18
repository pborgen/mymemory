"""Unit tests for pipelines/chunk.py (no Postgres / API required)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pipelines"))

from chunk import chunk_text  # noqa: E402


def test_chunk_splits_paragraphs():
    text = (
        "The rate lock on loan LN-2026-4418 is 6.125% until 2026-08-15.\n\n"
        "The property address for loan LN-2026-4418 is 214 Cedar Lane."
    )
    chunks = chunk_text(text, max_chars=400, min_chars=20)
    assert len(chunks) == 2
    assert "rate lock" in chunks[0]
    assert "Cedar Lane" in chunks[1]


def test_chunk_wraps_long_paragraph():
    sentence = "Word " * 50  # ~250 chars
    text = (sentence + ". ") * 4
    chunks = chunk_text(text, max_chars=200, min_chars=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 220 for c in chunks)
