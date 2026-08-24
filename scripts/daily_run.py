"""Trigger the daily reinvention of every live game from outside the API.

For cron or CI:  0 6 * * *  .venv/bin/python scripts/daily_run.py
Uses ORBIT_API_URL (default http://localhost:8000).
"""

from __future__ import annotations

import json
import os
import sys

import httpx


def main() -> int:
    base = os.environ.get("ORBIT_API_URL", "http://localhost:8000").rstrip("/")
    response = httpx.post(f"{base}/games/daily-run", timeout=300)
    response.raise_for_status()
    body = response.json()
    print(json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
