#!/usr/bin/env python3
"""Local-first ingest: raw files → stage chunks → embed via API → warehouse JSONL.

Defaults stay laptop-friendly:
  - Landing zone:  ./data/raw   (S3 stand-in; MinIO optional later)
  - Stage:         ./data/stage (cleaned chunks)
  - Serve path:    POST local FastAPI /api/memory (your existing embed providers)
  - Warehouse:     ./data/warehouse/facts.jsonl (Snowflake stand-in)

No AWS, MinIO, DuckDB, or Bedrock required.

Usage (API running with ALLOW_DEV_AUTH_HEADERS=true):

  cd pipelines
  MEMORY_API_URL=http://localhost:8080 \\
  MEMORY_USER_EMAIL=alex@dev.local \\
  uv run --project ../apps/api python ingest.py

Optional: --dry-run (stage only, no API calls).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from chunk import chunk_text

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
STAGE_DIR = REPO_ROOT / "data" / "stage"
WAREHOUSE_DIR = REPO_ROOT / "data" / "warehouse"
PIPELINE_VERSION = "ingest-v1"
DEFAULT_API = os.getenv("MEMORY_API_URL", "http://localhost:8080").rstrip("/")
DEFAULT_EMAIL = os.getenv("MEMORY_USER_EMAIL", "alex@dev.local")


def _source_uri(path: Path) -> str:
    """Portable lineage URI relative to the landing zone."""
    try:
        rel = path.relative_to(RAW_DIR)
    except ValueError:
        rel = path.name
    return f"raw/{rel.as_posix()}"


def _iter_raw_files(subdir: str | None) -> list[Path]:
    root = RAW_DIR / subdir if subdir else RAW_DIR
    if not root.is_dir():
        return []
    files = [
        p
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix.lower() in {".txt", ".md"}
    ]
    return files


def stage_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    uri = _source_uri(path)
    chunks = chunk_text(text)
    rows = []
    for i, content in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{uri}:{i}:{content}".encode()).hexdigest()[:16]
        rows.append(
            {
                "chunkId": chunk_id,
                "content": content,
                "sourceUri": uri,
                "chunkIndex": i,
                "pipelineVersion": PIPELINE_VERSION,
                "stagedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
    out = STAGE_DIR / f"{path.stem}.jsonl"
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def load_chunks(rows: list[dict], *, api_url: str, email: str, dry_run: bool) -> list[dict]:
    if dry_run:
        return [
            {
                **row,
                "memoryId": None,
                "dryRun": True,
                "piiTags": [],
                "sensitivity": "normal",
            }
            for row in rows
        ]

    headers = {"Content-Type": "application/json", "x-user-email": email}
    loaded: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        for row in rows:
            resp = client.post(
                f"{api_url}/api/memory",
                headers=headers,
                json={
                    "content": row["content"],
                    "source": "pipeline",
                    "sourceUri": row["sourceUri"],
                    "pipelineVersion": row["pipelineVersion"],
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"POST /api/memory failed ({resp.status_code}): {resp.text}"
                )
            mem = (resp.json() or {}).get("memory") or {}
            loaded.append(
                {
                    **row,
                    "memoryId": mem.get("id"),
                    "piiTags": mem.get("piiTags") or [],
                    "sensitivity": mem.get("sensitivity") or "normal",
                    "loadedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
    return loaded


def append_warehouse(rows: list[dict]) -> Path:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    out = WAREHOUSE_DIR / "facts.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local memory ingest pipeline")
    parser.add_argument(
        "--subdir",
        default="mortgage",
        help="Subfolder under data/raw to ingest (default: mortgage)",
    )
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Stage chunks only; skip embed/API and warehouse load markers",
    )
    args = parser.parse_args(argv)

    files = _iter_raw_files(args.subdir or None)
    if not files:
        print(f"No .txt/.md files under {RAW_DIR / (args.subdir or '')}")
        return 1

    print(f"Pipeline {PIPELINE_VERSION}")
    print(f"  raw → {RAW_DIR}")
    print(f"  stage → {STAGE_DIR}")
    print(f"  api → {args.api_url} as {args.email}")
    print(f"  files: {len(files)}")

    all_loaded: list[dict] = []
    for path in files:
        staged = stage_file(path)
        print(f"  staged {path.name}: {len(staged)} chunk(s)")
        loaded = load_chunks(
            staged, api_url=args.api_url, email=args.email, dry_run=args.dry_run
        )
        all_loaded.extend(loaded)

    if not args.dry_run:
        wh = append_warehouse(all_loaded)
        print(f"  warehouse → {wh} (+{len(all_loaded)} rows)")
    else:
        print("  dry-run: skipped API + warehouse append")

    print("Done. Try: uv run --project ../apps/api python report.py --loan LN-2026-4418")
    return 0


if __name__ == "__main__":
    sys.exit(main())
