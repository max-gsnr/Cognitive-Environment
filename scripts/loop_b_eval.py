"""Grade the Loop B reading against recorded sessions. Offline, no model calls.

Loop A has a simulator (scripts/loop_a_sim.py); this is the equivalent for Loop
B's diagnosis. Each fixture in `evals/loop_b/` is a session plus the reading it
should get, so a change to the thresholds in app/telemetry_signals.py either
keeps every case or shows exactly which child it would now misread.

    python scripts/loop_b_eval.py

Exits non-zero on any mismatch, so it can gate a change to the summarizer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import telemetry_signals  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "loop_b"


def load() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted(FIXTURES.glob("*.json"))]


def grade(fixture: dict[str, Any]) -> dict[str, Any]:
    report = telemetry_signals.report(
        fixture["events"],
        baseline_ms=fixture.get("baseline_ms"),
        reported_problems=fixture.get("reported_problems", 0),
        restlessness_interpretation=fixture.get(
            "restlessness_interpretation", "unknown"
        ),
        at_or_below_mastered=fixture.get("at_or_below_mastered", True),
    )
    return {
        "name": fixture["name"],
        "expected": fixture["expected_signal"],
        "got": report["dominant_signal"],
        "tier_expected": fixture["expected_change_tier"],
        "tier_got": report["change_tier"],
        "report": report,
    }


def main() -> int:
    results = [grade(fixture) for fixture in load()]
    if not results:
        print(f"no fixtures in {FIXTURES}")
        return 1

    width = max(len(result["name"]) for result in results)
    failures = 0
    for result in results:
        ok = (
            result["expected"] == result["got"]
            and result["tier_expected"] == result["tier_got"]
        )
        failures += not ok
        mark = "ok  " if ok else "FAIL"
        print(
            f"{mark} {result['name']:<{width}}  expected {result['expected']}"
            f" -> got {result['got']} ({result['tier_got']})"
        )
        if not ok:
            print(f"     signals: {json.dumps(result['report']['signals'])}")

    print(f"\n{len(results) - failures}/{len(results)} fixtures read correctly")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
