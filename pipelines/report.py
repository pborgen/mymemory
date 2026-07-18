#!/usr/bin/env python3
"""Report over ingested memories — local Snowflake stand-in.

Prefers the live API (`GET /api/memory/report`) so lineage/tags stay current.
Falls back to `data/warehouse/facts.jsonl` if the API is unreachable
(offline laptop demo).

  uv run --project ../apps/api python report.py --loan LN-2026-4418
  uv run --project ../apps/api python report.py --tag rate
  uv run --project ../apps/api python report.py --offline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "facts.jsonl"
DEFAULT_API = os.getenv("MEMORY_API_URL", "http://localhost:8080").rstrip("/")
DEFAULT_EMAIL = os.getenv("MEMORY_USER_EMAIL", "alex@dev.local")


def _from_api(api_url: str, email: str, loan: str, tag: str) -> list[dict] | None:
    params = {}
    if loan:
        params["loan"] = loan
    if tag:
        params["tag"] = tag
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{api_url}/api/memory/report",
                headers={"x-user-email": email},
                params=params,
            )
            if resp.status_code >= 400:
                print(f"API error {resp.status_code}: {resp.text}", file=sys.stderr)
                return None
            return resp.json()
    except httpx.HTTPError as exc:
        print(f"API unreachable ({exc}); try --offline", file=sys.stderr)
        return None


def _from_warehouse(loan: str, tag: str) -> list[dict]:
    if not WAREHOUSE.is_file():
        return []
    rows: list[dict] = []
    with WAREHOUSE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            content = (row.get("content") or "").lower()
            tags = row.get("piiTags") or []
            if loan and loan.lower() not in content:
                continue
            if tag and tag not in tags:
                continue
            rows.append(row)
    return rows


def _print_rows(rows: list[dict], *, source: str) -> None:
    print(f"{len(rows)} row(s) from {source}\n")
    for row in rows:
        tags = row.get("piiTags") or []
        uri = row.get("sourceUri") or ""
        version = row.get("pipelineVersion") or ""
        content = row.get("content") or ""
        mid = row.get("id") or row.get("memoryId") or ""
        print(f"- {content}")
        meta = []
        if mid:
            meta.append(f"id={mid}")
        if uri:
            meta.append(f"uri={uri}")
        if version:
            meta.append(f"pipeline={version}")
        if tags:
            meta.append(f"tags={tags}")
        sens = row.get("sensitivity")
        if sens:
            meta.append(f"sensitivity={sens}")
        if meta:
            print(f"  ({', '.join(meta)})")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory warehouse report")
    parser.add_argument("--loan", default="", help="Filter content containing loan id")
    parser.add_argument("--tag", default="", help="Filter by piiTags value (e.g. rate)")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Read only data/warehouse/facts.jsonl (no API)",
    )
    args = parser.parse_args(argv)

    if args.offline:
        rows = _from_warehouse(args.loan, args.tag)
        _print_rows(rows, source=str(WAREHOUSE))
        return 0

    rows = _from_api(args.api_url, args.email, args.loan, args.tag)
    if rows is None:
        rows = _from_warehouse(args.loan, args.tag)
        _print_rows(rows, source=f"{WAREHOUSE} (fallback)")
        return 0 if rows else 1
    _print_rows(rows, source=f"{args.api_url}/api/memory/report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
