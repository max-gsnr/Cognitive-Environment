"""The island map: where a child stands on the journey through the topics.

Loop A's difficulty ladder already encodes how good a child is at a skill --
their current tier IS their position. This module makes that tangible: each
topic is an island, the child's tier index along the skill's full ladder is
how far across the island they have travelled, and getting far enough across
builds the bridge to the next island (addition and subtraction lead on to
multiplication and division).

Pure functions: no database, no model calls, regression-testable.
"""

from __future__ import annotations

from typing import Any

from app import difficulty

# The journey, in order. Later islands may not be playable yet -- they still
# appear on the map so the child can see where the bridge leads.
TOPIC_PATH: list[dict[str, str]] = [
    {"skill_id": "addition", "label": "Addition", "emoji": "\u2795"},
    {"skill_id": "subtraction", "label": "Subtraction", "emoji": "\u2796"},
    {"skill_id": "multiplication", "label": "Multiplication", "emoji": "\u2716"},
    {"skill_id": "division", "label": "Division", "emoji": "\u2797"},
]

# How far across an island the child must be before the bridge to the next
# island starts building. Reaching the far shore means the island is mastered.
BRIDGE_STARTS_AT = 0.6
MASTERY_ACCURACY = 0.8

MASTERED = "mastered"
ACTIVE = "active"
UNLOCKED = "unlocked"
LOCKED = "locked"


def ladder(skill_id: str) -> list[dict[str, Any]]:
    """Every tier of a skill in ascending order, from easiest to the ceiling."""
    vector = difficulty.base_vector(1)
    tiers = [vector]
    while True:
        harder = difficulty.increment(vector, skill_id)
        if harder == vector:
            return tiers
        tiers.append(harder)
        vector = harder


def tier_position(vector: dict[str, Any], skill_id: str) -> tuple[int, int]:
    """(index, count) of the vector on the skill's full ladder."""
    tiers = ladder(skill_id)
    key = difficulty.tier_key(vector)
    for index, tier in enumerate(tiers):
        if difficulty.tier_key(tier) == key:
            return index, len(tiers)
    # A vector off the ladder (e.g. a decrement landed between rungs): rank it.
    ranked = sorted(
        range(len(tiers)), key=lambda i: difficulty.rank(tiers[i], skill_id)
    )
    below = [
        i
        for i in ranked
        if difficulty.rank(tiers[i], skill_id) <= difficulty.rank(vector, skill_id)
    ]
    return (below[-1] if below else 0), len(tiers)


def island_progress(
    vector: dict[str, Any] | None, skill_id: str, recent_accuracy: float | None
) -> dict[str, Any]:
    """How far across one island the child is, 0.0 (shore) to 1.0 (far shore)."""
    if vector is None:
        return {"progress": 0.0, "tier_index": 0, "tier_count": len(ladder(skill_id))}
    index, count = tier_position(vector, skill_id)
    progress = index / (count - 1) if count > 1 else 1.0
    at_ceiling = index == count - 1
    mastered = at_ceiling and (recent_accuracy or 0.0) >= MASTERY_ACCURACY
    return {
        "progress": round(progress, 3),
        "tier_index": index,
        "tier_count": count,
        "at_ceiling": at_ceiling,
        "mastered": mastered,
    }


def build_map(
    per_skill: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the journey from per-skill facts.

    `per_skill[skill_id]` carries what the caller read from the database:
    `vector` (or None), `recent_accuracy`, `streak`, `attempts`, `playable`.
    Islands unlock left to right: the next island opens once the previous
    one's progress reaches BRIDGE_STARTS_AT.
    """
    islands: list[dict[str, Any]] = []
    previous_progress = 1.0  # the first island is always open
    current: str | None = None

    for order, topic in enumerate(TOPIC_PATH):
        skill_id = topic["skill_id"]
        facts = per_skill.get(skill_id, {})
        vector = facts.get("vector")
        accuracy = facts.get("recent_accuracy")
        unlocked = previous_progress >= BRIDGE_STARTS_AT
        shape = island_progress(vector, skill_id, accuracy) if unlocked else {
            "progress": 0.0,
            "tier_index": 0,
            "tier_count": len(ladder(skill_id)),
        }

        if not unlocked:
            status = LOCKED
        elif shape.get("mastered"):
            status = MASTERED
        elif vector is not None:
            status = ACTIVE
        else:
            status = UNLOCKED
        if status == ACTIVE and current is None:
            current = skill_id

        bridge = (
            min(
                1.0,
                (shape["progress"] - BRIDGE_STARTS_AT) / (1 - BRIDGE_STARTS_AT),
            )
            if shape["progress"] >= BRIDGE_STARTS_AT
            else 0.0
        )
        islands.append(
            {
                **topic,
                "order": order,
                "status": status,
                "playable": bool(facts.get("playable")),
                "attempts": facts.get("attempts", 0),
                "recent_accuracy": accuracy,
                "streak": facts.get("streak", 0),
                "tier": vector,
                "tier_label": facts.get("tier_label"),
                "bridge_to_next": round(bridge, 3),
                **shape,
            }
        )
        previous_progress = shape["progress"] if status != LOCKED else 0.0

    mastered_count = sum(1 for island in islands if island["status"] == MASTERED)
    return {
        "islands": islands,
        "journey": {
            "mastered": mastered_count,
            "total": len(islands),
            "current": current,
            "next_locked": next(
                (i["skill_id"] for i in islands if i["status"] == LOCKED), None
            ),
        },
    }
