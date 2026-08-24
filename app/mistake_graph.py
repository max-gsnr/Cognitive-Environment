"""The child's mistakes as an intertwined network, not a flat count.

Every wrong answer is a node in a per-child graph. Mistakes of the same error
class are linked to each other, classes in the same cognitive family (all the
regrouping omissions, say) are linked more weakly, and classes that co-occur
in the same play window are linked by what actually happened. Folding the
instances up per class yields a profile of the child's PAST mistakes versus
their CURRENT ones -- persistent, emerging, resolved, dormant -- which is what
a reinvention session needs to decide what kind of game to build next.

Pure functions over Attempt rows: no model calls, fully regression-testable,
same inputs always produce the same graph.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app import error_taxonomy
from app.models import Attempt

# Cognitive families: classes inside one family share a mechanism, so a game
# that fixes one is likely to touch its siblings.
FAMILY_FOR_CLASS: dict[str, str] = {
    error_taxonomy.BORROW_OMITTED: "regrouping",
    error_taxonomy.BORROW_ACROSS_ZERO: "regrouping",
    error_taxonomy.CARRY_OMITTED: "regrouping",
    error_taxonomy.PLACE_VALUE_MISALIGNMENT: "structure",
    error_taxonomy.OPERATOR_CONFUSION: "attention",
    error_taxonomy.COUNTING_SLIP: "attention",
    error_taxonomy.UNCLASSIFIED: "unknown",
}

CURRENT_WINDOW_DAYS = 7

PERSISTENT = "persistent"  # in the past AND still happening
EMERGING = "emerging"  # only in the current window
RESOLVED = "resolved"  # in the past, gone from the current window


def _iso(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat()


def build_graph(
    attempts: list[Attempt], now: datetime | None = None
) -> dict[str, Any]:
    """Fold a child's wrong answers into the linked mistake network."""
    now = now or datetime.now(UTC)
    cutoff = (now - timedelta(days=CURRENT_WINDOW_DAYS)).replace(tzinfo=None)
    mistakes = [a for a in attempts if not a.is_correct]

    instances: list[dict[str, Any]] = []
    by_class: dict[str, list[Attempt]] = {}
    for attempt in mistakes:
        by_class.setdefault(attempt.error_class, []).append(attempt)
        instances.append(
            {
                "attempt_id": attempt.id,
                "error_class": attempt.error_class,
                "family": FAMILY_FOR_CLASS.get(attempt.error_class, "unknown"),
                "skill_id": attempt.skill_id,
                "tier": attempt.tier_key,
                "question": f"{attempt.operands[0]} {attempt.operator} "
                f"{attempt.operands[1]}",
                "answer_given": attempt.answer_given,
                "correct_answer": attempt.correct_answer,
                "at": _iso(attempt.created_at),
                "current": attempt.created_at >= cutoff,
            }
        )

    nodes = []
    for error_class, rows in sorted(by_class.items()):
        rows.sort(key=lambda a: a.created_at)
        past = [a for a in rows if a.created_at < cutoff]
        current = [a for a in rows if a.created_at >= cutoff]
        if past and current:
            trend = PERSISTENT
        elif current:
            trend = EMERGING
        else:
            trend = RESOLVED
        nodes.append(
            {
                "error_class": error_class,
                "family": FAMILY_FOR_CLASS.get(error_class, "unknown"),
                "total": len(rows),
                "past": len(past),
                "current": len(current),
                "trend": trend,
                "first_seen": _iso(rows[0].created_at),
                "last_seen": _iso(rows[-1].created_at),
                "tiers": sorted({a.tier_key for a in rows}),
            }
        )

    edges = _class_edges(by_class)
    return {
        "generated_at": now.isoformat(),
        "current_window_days": CURRENT_WINDOW_DAYS,
        "nodes": nodes,
        "edges": edges,
        "instances": instances,
        "profile": _profile(nodes),
    }


def _class_edges(by_class: dict[str, list[Attempt]]) -> list[dict[str, Any]]:
    """Links between mistake classes: shared family, plus observed co-occurrence
    (both classes produced mistakes on the same calendar day)."""
    classes = sorted(by_class)
    days = {
        error_class: {a.created_at.date() for a in rows}
        for error_class, rows in by_class.items()
    }
    edges = []
    for i, left in enumerate(classes):
        for right in classes[i + 1 :]:
            same_family = (
                FAMILY_FOR_CLASS.get(left, "unknown")
                == FAMILY_FOR_CLASS.get(right, "unknown")
            )
            co_occurrences = len(days[left] & days[right])
            if not same_family and co_occurrences == 0:
                continue
            edges.append(
                {
                    "between": [left, right],
                    "same_family": same_family,
                    "co_occurrences": co_occurrences,
                    "weight": round(
                        (0.5 if same_family else 0.0) + 0.1 * co_occurrences, 2
                    ),
                }
            )
    return edges


def _profile(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    current_nodes = [n for n in nodes if n["current"] > 0]
    dominant = max(current_nodes, key=lambda n: n["current"], default=None)
    return {
        "persistent": [n["error_class"] for n in nodes if n["trend"] == PERSISTENT],
        "emerging": [n["error_class"] for n in nodes if n["trend"] == EMERGING],
        "resolved": [n["error_class"] for n in nodes if n["trend"] == RESOLVED],
        "dominant_current": dominant["error_class"] if dominant else None,
        "dominant_family": dominant["family"] if dominant else None,
    }
