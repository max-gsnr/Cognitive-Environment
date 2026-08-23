"""Loop B, made legible: why each version of the game exists, and what stopped it.

The game rows already carry everything an auditor needs -- which signal triggered
the iteration, what tier of change that signal permitted, what the Devin session
reported about its own work, what our independent re-check found, and the prompt
revision and session behind it. Nothing reads it, so the most defensible part of
the system is also the invisible one.

This module turns those rows into one honest record per version. It narrates
nothing: every field is copied or counted from the row, a missing check is
reported as missing rather than as a pass, and a version that never shipped stays
in the log with the reason it was refused.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app import telemetry_signals as ts
from app.telemetry_signals import CHANGE_TIER, FIX

# The gates the Devin session must report on, and what each one is for in words a
# judge or a teacher can check against the game in front of them.
DEVIN_GATES: dict[str, str] = {
    "schema": "Questions come from our backend, in the shape it defines",
    "assertions": "The game's own tests pass",
    "playthrough": "A full level can actually be completed",
    "render_accessibility": "Readable, keyboard reachable, no fast flashing",
}

# Our re-check (app/gates.py) is deliberately not the same list: it is the part we
# can prove ourselves, in code the generating agent never sees.
OUR_CHECKS: dict[str, str] = {
    "files": "The files it claims to have written exist",
    "shell_contract": "It asks us for questions instead of inventing them",
    "instrumentation": "Every event Loop B reads is still emitted",
    "no_fast_flashing": "Nothing flashes faster than 3Hz (WCAG 2.3.1)",
    "focus_visible": "Focus is visible for keyboard play",
    "playthrough": "We played it headless and it answered three questions",
}

SIGNAL_LABEL: dict[str, str] = {
    "frustration_or_bug": "Frustration or a bug",
    "healthy_struggle": "Working hard, and getting there",
    "bored_with_the_game": "Disengaging from the game",
    "impulsive_guessing": "Guessing instead of solving",
    "working_memory_bottleneck": "Holding too much in mind at once",
    "inconclusive": "Not enough evidence yet",
}

TIER_LABEL: dict[str, str] = {
    "none": "No change permitted",
    "presentation": "Presentation only",
    "content": "Content",
    "structural": "Structure",
}

STATE_LABEL: dict[str, str] = {
    "live": "Live for this child",
    "shipped": "Passed, superseded",
    "blocked": "Blocked by our checks",
    "in_progress": "Being built",
    "failed": "Build failed",
}

# Which numbers actually justify each reading, so the evidence shown is the
# evidence the rule used -- not every field we happen to have.
EVIDENCE: dict[str, tuple[tuple[str, str, str], ...]] = {
    "frustration_or_bug": (
        ("abandons", "Levels left unfinished", "count"),
        ("rage_clicks", "Rage clicks", "count"),
    ),
    "healthy_struggle": (
        ("micro_jitter", "Restless bursts while thinking", "count"),
        ("after_pause_ratio", "Corrections made after a pause", "share"),
    ),
    "bored_with_the_game": (
        ("idle_ratio", "Session spent idle", "share"),
        ("repetitive_orbit", "Aimless circling", "count"),
        ("disengaged_answers", "Answers given without trying", "count"),
    ),
    "impulsive_guessing": (
        ("fast_wrong_ratio", "Answers wrong and rushed", "share"),
        ("answers", "Answers seen", "count"),
    ),
    "working_memory_bottleneck": (
        ("slow_correct_ratio", "Right, but laboured", "share"),
        ("solve_seconds", "Time spent solving", "seconds"),
    ),
    "inconclusive": (
        ("questions", "Questions seen", "count"),
        ("answers", "Answers seen", "count"),
    ),
}

# The diagnosis is a priority ladder over recorded numbers (telemetry_signals
# .dominant), so it can be shown as the ladder rather than as a conclusion: every
# rule, in the order it was tried, the threshold it compared against, and where it
# stopped. Rules below the one that fired were never reached, and say so.
#
# Each condition is (metric key, comparison, threshold, how it joins the previous).
LADDER: tuple[tuple[str, tuple[tuple[str, str, float, str], ...]], ...] = (
    (
        ts.FRUSTRATION,
        (("rage_clicks", ">", 0, ""), ("abandons", ">", 0, "or")),
    ),
    (ts.INCONCLUSIVE, (("questions", "<", ts.MIN_QUESTIONS, ""),)),
    (
        ts.HEALTHY_STRUGGLE,
        (
            ("micro_jitter", ">=", ts.HIGH_JITTER, ""),
            ("after_pause_ratio", ">=", ts.HIGH_AFTER_PAUSE_RATIO, "and"),
        ),
    ),
    (
        ts.BORED,
        (
            ("idle_ratio", ">=", ts.HIGH_IDLE_RATIO, ""),
            ("repetitive_orbit", ">", 0, "or"),
            ("disengaged_answers", ">", 0, "and"),
        ),
    ),
    (ts.IMPULSIVE, (("fast_wrong_ratio", ">=", ts.HIGH_FAST_WRONG_RATIO, ""),)),
    (
        ts.WORKING_MEMORY,
        (("slow_correct_ratio", ">=", ts.HIGH_SLOW_CORRECT_RATIO, ""),),
    ),
)

METRIC_LABEL: dict[str, str] = {
    "questions": "questions seen",
    "answers": "answers given",
    "idle_seconds": "seconds idle",
    "solve_seconds": "seconds solving",
    "idle_ratio": "share of the session idle",
    "repetitive_orbit": "aimless circling",
    "disengaged_answers": "answers given without trying",
    "micro_jitter": "restless bursts while thinking",
    "immediate_corrections": "corrections made at once",
    "after_pause_corrections": "corrections made after a pause",
    "after_pause_ratio": "share of corrections after a pause",
    "fast_wrong_ratio": "answers wrong and rushed",
    "slow_correct_ratio": "right, but laboured",
    "rage_clicks": "rage clicks",
    "abandons": "levels left unfinished",
}

VERDICT = re.compile(r"^\s*([a-z]+)", re.IGNORECASE)
PASSING = {"pass", "passed", "ok", "true", "yes"}
SKIPPED = {"skip", "skipped", "n/a", "na"}


@dataclass(frozen=True)
class GameRow:
    """One row of `games`, flattened so the log can be computed without the ORM."""

    id: str
    version: int
    status: str
    is_live: bool
    created_at: datetime
    pr_url: str | None = None
    devin_session_id: str | None = None
    gate_results: dict[str, Any] | None = None
    test_report: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None


def evolution_log(rows: Sequence[GameRow]) -> dict[str, Any]:
    """Every version of this child's game, newest first, with why and whether."""
    entries = [_entry(row) for row in sorted(rows, key=lambda row: row.version)]
    entries.reverse()
    return {"versions": entries, "summary": _summary(entries)}


def _entry(row: GameRow) -> dict[str, Any]:
    provenance = row.provenance or {}
    report = row.test_report or {}
    signals = provenance.get("telemetry_signals") or {}
    checks = _checks(row.gate_results)
    blocked = [check for check in checks if check["verdict"] == "fail"]

    return {
        "game_id": row.id,
        "version": row.version,
        "label": f"v{row.version}",
        "created_at": row.created_at.isoformat(),
        "from_version": provenance.get("from_version"),
        "state": _state(row, blocked),
        "state_label": STATE_LABEL.get(_state(row, blocked), row.status),
        "status": row.status,
        "is_live": row.is_live,
        "trigger": _trigger(signals, report),
        "permitted_change": _permitted(signals, report),
        "summary": report.get("summary"),
        "changes_made": report.get("changes_made") or [],
        "diff_summary": report.get("before_after_diff_summary"),
        "checks": checks,
        "checks_passed": bool(checks) and not blocked,
        "blocked_by": [check["label"] for check in blocked],
        "provenance": {
            "agent": provenance.get("agent"),
            "prompt": provenance.get("prompt"),
            "prompt_revision": provenance.get("prompt_revision"),
            "devin_session_id": row.devin_session_id,
            "pr_url": row.pr_url,
            "requested_at": provenance.get("created_at"),
        },
    }


def _state(row: GameRow, blocked: list[dict[str, Any]]) -> str:
    if row.is_live:
        return "live"
    if row.status in {"generating", "iterating"}:
        return "in_progress"
    if blocked or row.status == "gates_failed":
        return "blocked"
    if row.status == "failed":
        return "failed"
    return "shipped"


def _trigger(signals: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """What was observed before this version was asked for.

    The first version has no trigger -- there was no session to read yet -- and an
    iteration whose telemetry never arrived says so instead of showing zeroes.
    """
    name = signals.get("dominant_signal") or report.get("diagnosis")
    numbers = signals.get("signals") or {}
    if not signals.get("available", bool(numbers)):
        return {
            "available": False,
            "reason": signals.get("reason") or "no telemetry was recorded",
            "signal": name,
            "signal_label": SIGNAL_LABEL.get(str(name), name),
            "evidence": [],
            "ladder": [],
            "measured": [],
        }
    return {
        "available": True,
        "reason": None,
        "signal": name,
        "signal_label": SIGNAL_LABEL.get(str(name), name),
        "event_count": signals.get("event_count"),
        "evidence": _evidence(str(name), numbers),
        "ladder": _ladder(str(name), numbers),
        "measured": _measured(numbers),
    }


def _ladder(fired: str, numbers: dict[str, Any]) -> list[dict[str, Any]]:
    """The whole decision, rule by rule, against the numbers it was given.

    Shown in full because that is what makes a diagnosis checkable: a reader sees
    the rules that did not hold and the rules that were never reached, and can
    recompute any of them from the same figures.
    """
    rows: list[dict[str, Any]] = []
    reached = True
    for name, conditions in LADDER:
        terms = [_term(numbers, *condition) for condition in conditions]
        matched = reached and _holds(terms) and name == fired
        rows.append(
            {
                "signal": name,
                "label": SIGNAL_LABEL.get(name, name),
                "tier": CHANGE_TIER.get(name),
                "terms": terms,
                "outcome": (
                    "fired" if matched else ("not_reached" if not reached else "no")
                ),
            }
        )
        if matched:
            reached = False
    return rows


def _term(
    numbers: dict[str, Any], key: str, comparison: str, threshold: float, joiner: str
) -> dict[str, Any]:
    value = numbers.get(key)
    return {
        "key": key,
        "label": METRIC_LABEL.get(key, key.replace("_", " ")),
        "comparison": comparison,
        "threshold": threshold,
        "value": value,
        "joiner": joiner,
        "met": None if value is None else _compare(float(value), comparison, threshold),
    }


def _compare(value: float, comparison: str, threshold: float) -> bool:
    if comparison == ">":
        return value > threshold
    if comparison == "<":
        return value < threshold
    return value >= threshold


def _holds(terms: list[dict[str, Any]]) -> bool:
    """`or` binds tighter than `and`, which is how the rules are written in code."""
    groups: list[list[bool]] = []
    for term in terms:
        met = bool(term["met"])
        if term["joiner"] == "or" and groups:
            groups[-1].append(met)
        else:
            groups.append([met])
    return all(any(group) for group in groups)


def _measured(numbers: dict[str, Any]) -> list[dict[str, Any]]:
    """Every figure the session produced. The raw table underneath the rules."""
    return [
        {
            "key": key,
            "label": METRIC_LABEL.get(key, key.replace("_", " ")),
            "value": value,
        }
        for key, value in numbers.items()
    ]


def _evidence(name: str, numbers: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "unit": unit, "value": numbers[key]}
        for key, label, unit in EVIDENCE.get(name, ())
        if numbers.get(key) is not None
    ]


def _permitted(signals: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """The tier the signal allows, and the tier the agent says it stayed within.

    These are two different facts: the first is our rule, the second is a claim.
    Showing them side by side is the point -- a mismatch is the interesting case.
    """
    name = str(signals.get("dominant_signal") or "")
    allowed = signals.get("change_tier") or CHANGE_TIER.get(name)
    claimed = report.get("change_tier")
    return {
        "allowed": allowed,
        "allowed_label": TIER_LABEL.get(str(allowed), allowed),
        "claimed": claimed,
        "claimed_label": TIER_LABEL.get(str(claimed), claimed),
        "within_scope": None if not (allowed and claimed) else claimed == allowed,
        "rule": signals.get("suggested_fix") or FIX.get(name),
    }


def _checks(gate_results: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Both scoreboards, one row per check: what Devin said, what we found.

    A gate the session never reported is a failure, not a blank, because a version
    used to go live on the strength of its own report.
    """
    results = gate_results or {}
    if not results:
        # Nothing has been checked yet -- an empty scoreboard, not a failing one.
        return []
    independent = results.get("independent")
    ours = independent if isinstance(independent, dict) else {}

    rows = [
        {
            "name": name,
            "label": label,
            "source": "agent",
            **_verdict(results.get(name), missing_is_failure=True),
        }
        for name, label in DEVIN_GATES.items()
    ]
    rows += [
        {
            "name": name,
            "label": label,
            "source": "ours",
            **_verdict(ours.get(name), missing_is_failure=False),
        }
        for name, label in OUR_CHECKS.items()
        if ours
    ]
    return rows


def _verdict(value: Any, missing_is_failure: bool) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"verdict": "pass" if value else "fail", "detail": None}
    if not isinstance(value, str):
        return {
            "verdict": "fail" if missing_is_failure else "not_run",
            "detail": "never reported" if missing_is_failure else None,
        }
    word = VERDICT.match(value)
    head = word.group(1).lower() if word else ""
    if head in SKIPPED:
        return {"verdict": "skipped", "detail": value}
    return {"verdict": "pass" if head in PASSING else "fail", "detail": value}


def _summary(entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The four counts the loop is actually judged on."""
    states = [entry["state"] for entry in entries]
    live = next((entry for entry in entries if entry["state"] == "live"), None)
    declined = [
        entry
        for entry in entries
        if entry["permitted_change"]["allowed"] == "none"
    ]
    checked = [entry for entry in entries if entry["checks"]]
    return {
        "proposed": len(entries),
        "shipped": len([state for state in states if state in {"live", "shipped"}]),
        "blocked": len([state for state in states if state == "blocked"]),
        "in_progress": len([state for state in states if state == "in_progress"]),
        "live_version": live["version"] if live else None,
        "no_change_needed": len(declined),
        "checked": len(checked),
        "disagreements": len(
            [entry for entry in checked if _disagreed(entry["checks"])]
        ),
    }


def _disagreed(checks: Sequence[dict[str, Any]]) -> bool:
    """The version passed its own report but failed ours -- the case gates exist for."""
    agent_passed = all(
        check["verdict"] == "pass" for check in checks if check["source"] == "agent"
    )
    ours = [check for check in checks if check["source"] == "ours"]
    return bool(ours) and agent_passed and any(c["verdict"] == "fail" for c in ours)
