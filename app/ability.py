"""The ability estimate: where on the ladder this child's next question belongs.

Loop A used to move one rung per answer: one correct answer, one step harder.
That is a step *policy* with no notion of how hard the child actually finds the
work, and it escalates far faster than any child improves --- nine correct
answers took a child from 3+4 to 738+195, inside a single ten-question session.
An ADHD learner then spends the rest of the session failing, and the ladder
comes back down at half a rung per wrong answer.

So the state is no longer "which rung are we on" but "how strong is this child",
as a rating. Questions are then *aimed*: pick the rung whose expected success
rate is the one we want.

  target success   .75--.85. Pure adaptive testing aims at .50, which children
                   experience as discouraging; Math Garden's computer adaptive
                   practice samples at .75, and the fastest learning in
                   gradient-style learners sits near .85 (the "85% rule").
  rating updates   on correctness only. Response-time-adaptive scheduling buys
                   no measurable post-test gain over accuracy-adaptive, and
                   children with raised inattention report more difficulty
                   concentrating under it. Latency stays a diagnostic signal
                   (see app/baseline.py), not a difficulty driver.
  deadband         the aim has to drift most of a rung before the tier actually
                   changes. Difficulty *variability* during training tracks with
                   worse ADHD symptom outcomes, so a calm session is worth more
                   than perfect targeting.
  fluency items    every fifth question is aimed a rung low, and a run of errors
                   is answered with an easy one, to keep the density of success
                   up rather than grinding at the edge of ability.

Everything here is pure and cheap: no database, no model call. The rating is a
fold over the child's own attempt log, so it can always be replayed from it.

References
  Klinkenberg, Straatemeier & van der Maas, Computer adaptive practice of maths
  ability using a new item response model, 10.1016/j.compedu.2011.02.003
  Wilson et al., The eighty five percent rule for optimal learning,
  10.1038/s41467-019-12552-4
  Sonne et al., response-time-adaptive vs accuracy-adaptive training in
  children, 10.2196/33884
  Kollins et al., adaptive difficulty in a digital therapeutic for ADHD,
  10.1038/s41398-024-03045-0
  Imbo, Vandierendonck & Vergauwe, the role of working memory in carrying,
  10.1080/17470210600762447
"""

from __future__ import annotations

import math

from app import difficulty

Vector = difficulty.Vector

# Rating distance between two neighbouring rungs of the ladder.
RUNG = 100.0

# The step size shrinks as evidence accumulates: the first answers of a new
# child move the estimate far, so a ten-question session can still find the
# right level, while a settled child is not thrown around by one bad answer.
K_START = 90.0
K_FLOOR = 18.0
K_HALFLIFE = 12.0

# Leniency stops meaning "how slowly we take difficulty away" and starts meaning
# "how much success this child needs in order to stay in the game".
TARGET_SUCCESS: dict[str, float] = {"low": 0.75, "medium": 0.80, "high": 0.85}
DEFAULT_TARGET = 0.80

# Only re-aim once the estimate has drifted this far from the tier in play.
DEADBAND = 0.75 * RUNG

# Every fifth question is aimed a rung below target.
FLUENCY_EVERY = 5
FLUENCY_DROP = RUNG

# A run of errors is answered with a deliberately easy question.
REST_AFTER_ERRORS = 2
REST_DROP = 2 * RUNG


def _all_tiers(skill_id: str) -> list[Vector]:
    """Every tier of this skill that describes a question we can actually pose."""
    tiers: list[Vector] = []
    for digits, bands in difficulty.BANDS_BY_DIGITS.items():
        for band in bands:
            for flags in _flag_combinations(skill_id):
                vector = {**difficulty.base_vector(digits), "magnitude": band, **flags}
                if difficulty.satisfiable(vector, skill_id):
                    tiers.append(vector)
    # `rank` is the ladder's own ordering, so the rating scale and the ladder
    # cannot disagree about which of two tiers is harder.
    return sorted(
        tiers, key=lambda v: (difficulty.rank(v, skill_id), difficulty.tier_key(v))
    )


def _flag_combinations(skill_id: str) -> list[dict[str, bool]]:
    combinations: list[dict[str, bool]] = [{}]
    for flag in difficulty.SKILL_FLAGS.get(skill_id, []):
        combinations = [
            {**combination, flag: value}
            for combination in combinations
            for value in (False, True)
        ]
    return combinations


LADDER: dict[str, list[Vector]] = {
    skill: _all_tiers(skill) for skill in (difficulty.ADDITION, difficulty.SUBTRACTION)
}

TIER_RATING: dict[str, dict[str, float]] = {
    skill: {
        difficulty.tier_key(vector): RUNG * index
        for index, vector in enumerate(tiers)
    }
    for skill, tiers in LADDER.items()
}


def tier_rating(vector: Vector, skill_id: str) -> float:
    """The rating of the tier, or of the nearest tier the ladder does describe."""
    ratings = TIER_RATING[skill_id]
    key = difficulty.tier_key(vector)
    if key in ratings:
        return ratings[key]
    target = difficulty.rank(vector, skill_id)
    nearest = min(
        LADDER[skill_id], key=lambda v: abs(_rank_distance(v, target, skill_id))
    )
    return ratings[difficulty.tier_key(nearest)]


def _rank_distance(vector: Vector, target: tuple[int, int, int], skill_id: str) -> int:
    rank = difficulty.rank(vector, skill_id)
    return sum((a - b) ** 2 for a, b in zip(rank, target, strict=True))


def starting_rating(floor: Vector, skill_id: str, leniency_band: str) -> float:
    """A new child is assumed to belong at their floor, at the target rate."""
    return tier_rating(floor, skill_id) + target_offset(leniency_band)


def target_offset(leniency_band: str) -> float:
    """How far above a tier a rating must sit for that tier to be at target."""
    target = TARGET_SUCCESS.get(leniency_band, DEFAULT_TARGET)
    return -400.0 * math.log10(1.0 / target - 1.0)


def k_factor(attempts_seen: int) -> float:
    return K_FLOOR + (K_START - K_FLOOR) / (1.0 + attempts_seen / K_HALFLIFE)


def expected_success(rating: float, vector: Vector, skill_id: str) -> float:
    """The chance this child answers a question from this tier correctly."""
    return 1.0 / (1.0 + 10 ** ((tier_rating(vector, skill_id) - rating) / 400.0))


def update_rating(
    rating: float, vector: Vector, skill_id: str, correct: bool, attempts_seen: int
) -> float:
    expected = expected_success(rating, vector, skill_id)
    return rating + k_factor(attempts_seen) * ((1.0 if correct else 0.0) - expected)


def choose_tier(
    rating: float,
    skill_id: str,
    floor: Vector,
    current: Vector,
    *,
    leniency_band: str = "medium",
    attempts_seen: int = 0,
    errors_in_a_row: int = 0,
    soften_axis: str | None = None,
) -> Vector:
    """The tier the next question should come from."""
    resting = errors_in_a_row >= REST_AFTER_ERRORS
    aim = rating - target_offset(leniency_band)

    # Deterministic rather than random, so a session can be replayed exactly.
    if attempts_seen and attempts_seen % FLUENCY_EVERY == 0:
        aim -= FLUENCY_DROP
    if resting:
        aim -= REST_DROP

    drifted = abs(aim - tier_rating(current, skill_id)) > DEADBAND
    chosen = _nearest_tier(aim, skill_id, floor) if drifted or resting else current

    # An error class that names a flag takes that flag off, so the follow-up
    # question is about the thing the child got wrong rather than merely easier.
    # Softening never *adds* a step down: the rating already handled the level.
    flags = difficulty.SKILL_FLAGS.get(skill_id, [])
    if soften_axis in flags and chosen.get(soften_axis):
        chosen = difficulty.apply_movement(
            chosen, skill_id, "decrement", floor, axis=soften_axis
        )
    return difficulty.clamp_to_floor(chosen, floor, skill_id)


def _nearest_tier(aim: float, skill_id: str, floor: Vector) -> Vector:
    ratings = TIER_RATING[skill_id]
    allowed = [
        vector
        for vector in LADDER[skill_id]
        if difficulty.rank(vector, skill_id) >= difficulty.rank(floor, skill_id)
    ] or LADDER[skill_id]
    return dict(min(allowed, key=lambda v: abs(ratings[difficulty.tier_key(v)] - aim)))
