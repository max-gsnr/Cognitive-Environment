"""The difficulty vector: bands, the movement ladder, and question generation.

Every function here is pure. No database, no model call. This is Loop A --- the
real-time path --- and it must stay cheap enough to run inside POST /attempts.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from typing import Any

Vector = dict[str, Any]

ADDITION = "addition"
SUBTRACTION = "subtraction"

BAND_RANGES: dict[str, tuple[int, int]] = {
    "single": (1, 9),
    "low_double": (10, 29),
    "mid_double": (30, 69),
    "high_double": (70, 99),
    "low_triple": (100, 299),
    "mid_triple": (300, 699),
    "high_triple": (700, 999),
}

BANDS_BY_DIGITS: dict[int, list[str]] = {
    1: ["single"],
    2: ["low_double", "mid_double", "high_double"],
    3: ["low_triple", "mid_triple", "high_triple"],
}

FLOOR_DIGITS: dict[str, int] = {
    "single_digit": 1,
    "double_digit": 2,
    "triple_digit": 3,
}

MAX_DIGITS = 3

# Flags that exist for each skill, ordered by how hard they make a question.
SKILL_FLAGS: dict[str, list[str]] = {
    ADDITION: ["carries"],
    SUBTRACTION: ["borrows", "zero_in_minuend"],
}


def base_vector(digits: int = 1) -> Vector:
    return {
        "digits": digits,
        "magnitude": BANDS_BY_DIGITS[digits][0],
        "carries": False,
        "borrows": False,
        "zero_in_minuend": False,
    }


def floor_vector(difficulty_floor: str) -> Vector:
    return base_vector(FLOOR_DIGITS.get(difficulty_floor, 1))


def tier_key(vector: Vector) -> str:
    """A stable identity for 'this difficulty tier', used to bucket latencies."""
    return "|".join(
        f"{axis}={vector.get(axis)}"
        for axis in ("digits", "magnitude", "carries", "borrows", "zero_in_minuend")
    )


def _band_index(vector: Vector) -> int:
    bands = BANDS_BY_DIGITS[vector["digits"]]
    try:
        return bands.index(vector["magnitude"])
    except ValueError:
        return 0


def _flags_for(skill_id: str) -> list[str]:
    return SKILL_FLAGS.get(skill_id, [])


def rank(vector: Vector, skill_id: str) -> tuple[int, int, int]:
    """Order two vectors of the same skill. Used to compare against the floor."""
    flags_on = sum(1 for flag in _flags_for(skill_id) if vector.get(flag))
    return (vector["digits"], _band_index(vector), flags_on)


def satisfiable(vector: Vector, skill_id: str) -> bool:
    """Can this tier actually be drawn from? Some combinations describe nothing.

    A one-digit subtraction cannot borrow (a >= b leaves nothing to borrow), a
    zero to borrow across is itself a borrow, and two addends from 70-99 always
    carry in the tens column. Asking for those yields no question at all.
    """
    low, _ = BAND_RANGES[vector["magnitude"]]

    if skill_id == ADDITION:
        # The lowest pair in the band is the one least likely to carry.
        return bool(vector.get("carries")) or not _has_carry(low, low)

    if vector.get("zero_in_minuend") and not vector.get("borrows"):
        return False
    wants_borrow = vector.get("borrows") or vector.get("zero_in_minuend")
    return not (wants_borrow and vector["digits"] < 2)


def _ladder(vector: Vector, skill_id: str) -> Iterator[Vector]:
    """Harder tiers in ascending order: band, then flags, then a digit."""
    bands = BANDS_BY_DIGITS[vector["digits"]]
    index = _band_index(vector)

    if index < len(bands) - 1:
        yield {**vector, "magnitude": bands[index + 1]}

    for flag in _flags_for(skill_id):
        if not vector.get(flag):
            yield {**vector, flag: True}

    if vector["digits"] < MAX_DIGITS:
        yield base_vector(vector["digits"] + 1)


def increment(vector: Vector, skill_id: str) -> Vector:
    """First step of the ladder that describes a question we can actually pose."""
    for candidate in _ladder(vector, skill_id):
        if satisfiable(candidate, skill_id):
            return candidate
    return dict(vector)  # already at the ceiling


def decrement(vector: Vector, skill_id: str, axis: str | None = None) -> Vector:
    """Reverse the ladder, unless an error class named the axis that must move."""
    new = dict(vector)

    if axis in _flags_for(skill_id) and new.get(axis):
        new[axis] = False
        if axis == "borrows":
            new["zero_in_minuend"] = False  # a zero to borrow across is a borrow
        return new

    if axis == "digits" and new["digits"] > 1:
        return _drop_digit(new)

    if axis == "magnitude" and _band_index(new) > 0:
        new["magnitude"] = BANDS_BY_DIGITS[new["digits"]][_band_index(new) - 1]
        return new

    for flag in reversed(_flags_for(skill_id)):
        if new.get(flag):
            new[flag] = False
            return new

    index = _band_index(new)
    if index > 0:
        new["magnitude"] = BANDS_BY_DIGITS[new["digits"]][index - 1]
        return new

    if new["digits"] > 1:
        return _drop_digit(new)

    return new  # already at the easiest possible vector


def _drop_digit(vector: Vector) -> Vector:
    new = base_vector(vector["digits"] - 1)
    new["magnitude"] = BANDS_BY_DIGITS[new["digits"]][-1]
    return new


def clamp_to_floor(vector: Vector, floor: Vector, skill_id: str) -> Vector:
    """The vector never drops below the profile's floor for this skill."""
    if rank(vector, skill_id) < rank(floor, skill_id):
        return dict(floor)
    return vector


def apply_movement(
    vector: Vector,
    skill_id: str,
    direction: str,
    floor: Vector,
    axis: str | None = None,
) -> Vector:
    if direction == "increment":
        return increment(vector, skill_id)
    if direction == "decrement":
        return clamp_to_floor(decrement(vector, skill_id, axis), floor, skill_id)
    return dict(vector)


def next_question(
    vector: Vector, skill_id: str, rng: random.Random | None = None
) -> dict[str, Any]:
    """Generate operands from the vector. Pure: no LLM, no Devin, no database."""
    rng = rng or random.Random()
    low, high = BAND_RANGES[vector["magnitude"]]

    for _ in range(200):
        candidate = (
            _addition_operands(vector, low, high, rng)
            if skill_id == ADDITION
            else _subtraction_operands(vector, low, high, rng)
        )
        if candidate is not None:
            a, b = candidate
            operator = "+" if skill_id == ADDITION else "-"
            answer = a + b if operator == "+" else a - b
            if answer < 0 or a < 0 or b < 0:
                continue
            if len(str(a)) > MAX_DIGITS or len(str(b)) > MAX_DIGITS:
                continue
            return {
                "operands": [a, b],
                "operator": operator,
                "correct_answer": answer,
                "difficulty_vector_snapshot": dict(vector),
            }

    # Fall back to the plainest question this band allows rather than looping.
    a = b = low
    operator = "+" if skill_id == ADDITION else "-"
    return {
        "operands": [a, b],
        "operator": operator,
        "correct_answer": a + b if operator == "+" else 0,
        "difficulty_vector_snapshot": dict(vector),
    }


def _has_carry(a: int, b: int) -> bool:
    while a > 0 or b > 0:
        if (a % 10) + (b % 10) >= 10:
            return True
        a //= 10
        b //= 10
    return False


def _has_borrow(a: int, b: int) -> bool:
    while b > 0:
        if (a % 10) < (b % 10):
            return True
        a //= 10
        b //= 10
    return False


def _zero_in_borrow_column(a: int, b: int) -> bool:
    while b > 0:
        if a % 10 == 0 and b % 10 > 0:
            return True
        a //= 10
        b //= 10
    return False


def _addition_operands(
    vector: Vector, low: int, high: int, rng: random.Random
) -> tuple[int, int] | None:
    a = rng.randint(low, high)
    b = rng.randint(low, high)
    if _has_carry(a, b) is not bool(vector.get("carries")):
        return None
    return a, b


def _subtraction_operands(
    vector: Vector, low: int, high: int, rng: random.Random
) -> tuple[int, int] | None:
    a = rng.randint(low, high)
    b = rng.randint(low, min(high, a))
    if a < b:
        return None
    if _has_borrow(a, b) is not bool(vector.get("borrows")):
        return None
    wants_zero = bool(vector.get("zero_in_minuend"))
    if _zero_in_borrow_column(a, b) is not wants_zero:
        return None
    return a, b
