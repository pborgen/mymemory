#!/usr/bin/env python3
"""Seed synthetic mortgage facts into MyMemory via the HTTP API.

Usage (API must be running with ALLOW_DEV_AUTH_HEADERS=true):

  cd demos/mortgage
  MEMORY_API_URL=http://localhost:8080 \\
  MEMORY_USER_EMAIL=alex@dev.local \\
  python seed.py

Then sign in as alex@dev.local and ask the sample questions from loan_file.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
API_URL = os.getenv("MEMORY_API_URL", "http://localhost:8080").rstrip("/")
USER_EMAIL = os.getenv("MEMORY_USER_EMAIL", "alex@dev.local")


def main() -> int:
    data = json.loads((ROOT / "loan_file.json").read_text())
    facts = data["facts"]
    headers = {
        "Content-Type": "application/json",
        "x-user-email": USER_EMAIL,
    }
    print(f"Seeding {len(facts)} facts for {USER_EMAIL} via {API_URL}")
    with httpx.Client(timeout=120.0) as client:
        for fact in facts:
            resp = client.post(
                f"{API_URL}/api/memory",
                headers=headers,
                json={"content": fact, "source": "mortgage-demo"},
            )
            if resp.status_code >= 400:
                print(f"FAIL ({resp.status_code}): {fact}\n  {resp.text}")
                return 1
            body = resp.json()
            mem = body.get("memory") or {}
            print(
                f"OK  tags={mem.get('piiTags')} sensitivity={mem.get('sensitivity')}\n"
                f"    {fact}"
            )
    print("\nSample questions:")
    for q in data.get("sampleQuestions", []):
        print(f"  - {q}")
    print("\nAudit trail: GET /api/memory/audit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
