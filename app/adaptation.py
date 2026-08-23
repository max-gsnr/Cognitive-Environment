"""Loop A: turn one answered question into the next question's difficulty tier.

The movement vocabulary --- increment, hold, decrement, and the axis an error
class implicates --- is unchanged, because the audit log and the teacher UI speak
it. What changed is what decides: the tier is now *aimed* from an ability rating
(app/ability.py) instead of stepped one rung per answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import ability, difficulty, error_taxonomy
from app.baseline import is_slow

Vector = dict[str, Any]

HOLD = "hold"
INCREMENT = "increment"
DECREMENT = "decrement"

# Wrong answers that say nothing about difficulty: reading the operator the wrong
# way round, or an answer with no recognisable arithmetic in it. They hold the
# tier and they are not evidence about ability either, so they leave the rating
# alone --- Loop B is the one that should look at them.
NOT_EVIDENCE = frozenset(
    {error_taxonomy.OPERATOR_CONFUSION, error_taxonomy.UNCLASSIFIED}
)


@dataclass(frozen=True)
class Movement:
    direction: str
    axis: str | None
    error_class: str
    repeat_tier: bool = False


@dataclass(frozen=True)
class Decision:
    """Everything POST /attempts needs to answer 'why this question next?'."""

    vector: Vector
    movement: Movement
    rating: float
    expected_success: float
    errors_in_a_row: int


def decide_movement(
    error_class: str, latency_ms: int, baseline: float | None
) -> Movement:
    """The axis an answer implicates, and whether the tier should stand still."""
    slow = is_slow(latency_ms, baseline)

    if error_class == error_taxonomy.CORRECT:
        # Correct but laboured is not evidence for harder work. Latency holds the
        # tier; it never drives it, in either direction.
        return Movement(HOLD if slow else INCREMENT, None, error_class)

    if error_class in NOT_EVIDENCE:
        return Movement(HOLD, None, error_class)

    if error_class == error_taxonomy.COUNTING_SLIP:
        if slow:
            return Movement(DECREMENT, "magnitude", error_class)
        # Fast: number facts are not automatic yet. Repeat, do not soften.
        return Movement(HOLD, None, error_class, repeat_tier=True)

    return Movement(DECREMENT, error_taxonomy.AXIS_FOR_CLASS[error_class], error_class)


def replay(
    history: list[tuple[Vector, str, bool]],
    placement: Vector,
    skill_id: str,
    leniency_band: str,
) -> tuple[float, int]:
    """Fold the attempt log into (rating, attempts that counted towards it).

    The rating is never hidden state: it is a pure function of the attempts this
    child has already made, so the audit log can always reproduce it. The prior is
    the tier the child was first placed at --- intake's judgement, or the first
    tier in the log --- so a returning child is not re-taught from scratch.
    """
    if history:
        placement = history[0][0]
    rating = ability.starting_rating(placement, skill_id, leniency_band)
    counted = 0
    for vector, error_class, correct in history:
        if error_class in NOT_EVIDENCE:
            continue
        rating = ability.update_rating(rating, vector, skill_id, correct, counted)
        counted += 1
    return rating, counted


def errors_in_a_row(history: list[tuple[Vector, str, bool]]) -> int:
    run = 0
    for _vector, _error_class, correct in reversed(history):
        if correct:
            break
        run += 1
    return run


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
    rating: float,
    attempts_seen: int = 0,
    prior_errors_in_a_row: int = 0,
) -> Decision:
    error_class = error_taxonomy.classify_attempt(operands, operator, answer_given)
    movement = decide_movement(error_class, latency_ms, baseline)
    correct = error_class == error_taxonomy.CORRECT

    updated_rating = rating
    counted = attempts_seen
    if error_class not in NOT_EVIDENCE:
        updated_rating = ability.update_rating(
            rating, vector, skill_id, correct, attempts_seen
        )
        counted = attempts_seen + 1

    run = 0 if correct else prior_errors_in_a_row + 1

    # A run of errors outranks every hold: repeating a tier the child is failing
    # at, or standing still after an unreadable answer, is the thing this policy
    # exists to prevent.
    resting = run >= ability.REST_AFTER_ERRORS
    if not resting and (movement.repeat_tier or movement.direction == HOLD):
        chosen = dict(vector)
    else:
        chosen = ability.choose_tier(
            updated_rating,
            skill_id,
            floor,
            vector,
            leniency_band=leniency_band,
            attempts_seen=counted,
            errors_in_a_row=run,
            soften_axis=movement.axis,
        )

    return Decision(
        vector=chosen,
        movement=Movement(
            direction=_direction(vector, chosen, skill_id),
            axis=movement.axis,
            error_class=error_class,
            # A rest item is a new question by definition, so it outranks
            # "show that one again" the same way it outranks a hold.
            repeat_tier=movement.repeat_tier and not resting,
        ),
        rating=updated_rating,
        expected_success=ability.expected_success(updated_rating, chosen, skill_id),
        errors_in_a_row=run,
    )


def _direction(before: Vector, after: Vector, skill_id: str) -> str:
    """Report the movement the child actually experienced."""
    was, now = difficulty.rank(before, skill_id), difficulty.rank(after, skill_id)
    if now > was:
        return INCREMENT
    if now < was:
        return DECREMENT
    return HOLD
