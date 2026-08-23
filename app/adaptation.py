"""Loop A: turn one answered question into one movement of the difficulty vector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import difficulty, error_taxonomy
from app.baseline import is_slow

Vector = dict[str, Any]

HOLD = "hold"
INCREMENT = "increment"
DECREMENT = "decrement"


@dataclass(frozen=True)
class Movement:
    direction: str
    axis: str | None
    error_class: str
    repeat_tier: bool = False


def decide_movement(
    error_class: str, latency_ms: int, baseline: float | None
) -> Movement:
    """Direction and axis, before leniency and before the floor are applied."""
    slow = is_slow(latency_ms, baseline)

    if error_class == error_taxonomy.CORRECT:
        if slow:
            return Movement(DECREMENT, None, error_class)
        return Movement(INCREMENT, None, error_class)

    if error_class == error_taxonomy.OPERATOR_CONFUSION:
        # Possibly a reading error rather than a math error: hold the ladder and
        # follow up with a structurally similar question, flags off.
        return Movement(HOLD, None, error_class)

    if error_class == error_taxonomy.COUNTING_SLIP:
        if slow:
            return Movement(DECREMENT, "magnitude", error_class)
        # Fast: number facts are not automatic yet. Repeat, do not soften.
        return Movement(HOLD, None, error_class, repeat_tier=True)

    if error_class == error_taxonomy.UNCLASSIFIED:
        # Not a math signal. Loop B --- Devin --- gets this one.
        return Movement(HOLD, None, error_class)

    return Movement(DECREMENT, error_taxonomy.AXIS_FOR_CLASS[error_class], error_class)


def apply(
    vector: Vector,
    skill_id: str,
    movement: Movement,
    floor: Vector,
    leniency_band: str,
    decrement_credit: float,
) -> tuple[Vector, float]:
    """Apply a movement, scaling decrements down by the profile's leniency band.

    Leniency is banked rather than rounded away: a high-leniency child accrues
    0.34 of a decrement per rough attempt and only actually moves once the
    credit reaches a whole step, so one bad answer moves them less than it moves
    a low-leniency child without ever being silently discarded.
    """
    if movement.direction != DECREMENT:
        return dict(vector), decrement_credit

    weight = difficulty.LENIENCY_WEIGHTS.get(leniency_band, 1.0)
    credit = decrement_credit + weight
    if credit < 1.0:
        return dict(vector), credit

    moved = difficulty.apply_movement(
        vector, skill_id, DECREMENT, floor, axis=movement.axis
    )
    return moved, credit - 1.0


def next_vector(
    vector: Vector,
    skill_id: str,
    operands: list[int],
    operator: str,
    answer_given: int,
    latency_ms: int,
    baseline: float | None,
    floor: Vector,
    leniency_band: str,
    decrement_credit: float,
) -> tuple[Vector, Movement, float]:
    error_class = error_taxonomy.classify_attempt(operands, operator, answer_given)
    movement = decide_movement(error_class, latency_ms, baseline)

    if movement.direction == INCREMENT:
        return difficulty.increment(vector, skill_id), movement, decrement_credit

    updated, credit = apply(
        vector, skill_id, movement, floor, leniency_band, decrement_credit
    )
    return updated, movement, credit
