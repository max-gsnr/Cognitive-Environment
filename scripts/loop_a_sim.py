"""Offline comparison of Loop A difficulty policies against a simulated learner.

Loop A decides which numbers a child sees next. It is cheap and deterministic,
which makes it auditable but also makes it easy to get the *pacing* wrong: the
policy on main raises difficulty after a single correct answer, so a competent
child crosses the whole ladder inside one ten-question session.

This harness exists so a pacing change can be argued with numbers instead of
taste. It plays each policy against the same simulated children and reports the
metrics the literature says matter for an ADHD learner:

  accuracy          target band is 0.75--0.85 (Klinkenberg 2011 samples items at
                    p=.75; Wilson 2019 puts fastest learning at ~85% correct)
  in_band           share of attempts whose success probability sat in .6--.9
  moves             tier changes per session: difficulty variability, which
                    tracks with worse ADHD outcomes (JMIR DTx analysis, 2026)
  harder            share of answers followed by a *harder* question --- the
                    complaint this change answers
  err-run           longest run of consecutive errors --- the frustration driver
  quit              share of sessions the child abandoned
  gain              latent competence gained over the whole program
  ceiling           share of attempts spent pinned at the hardest tier

Run: .venv/bin/python scripts/loop_a_sim.py
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import ability, adaptation, difficulty, error_taxonomy  # noqa: E402

SKILL = difficulty.ADDITION
SESSION_LENGTH = 10
SESSIONS = 20
TARGET_P = 0.80
BAND = (0.60, 0.90)


# --------------------------------------------------------------------------- #
# the simulated child
# --------------------------------------------------------------------------- #


def tier_load(vector: difficulty.Vector) -> float:
    """How much this tier demands. Carries are weighted as a working-memory tax."""
    return (
        vector["digits"]
        + 0.35 * difficulty._band_index(vector)
        + (0.9 if vector.get("carries") else 0.0)
    )


@dataclass
class Child:
    """Competence grows fastest when practice sits near the target success rate."""

    competence: float
    learning_rate: float = 0.005
    noise: float = 0.55
    frustration: float = 0.0

    def p_correct(self, vector: difficulty.Vector) -> float:
        gap = (self.competence - tier_load(vector)) / self.noise
        raw = 1.0 / (1.0 + math.exp(-gap))
        # Frustration eats accuracy before it ends the session.
        return max(0.02, min(0.98, raw * (1.0 - 0.12 * self.frustration)))

    def answer(self, vector: difficulty.Vector, rng: random.Random) -> tuple[bool, int]:
        p = self.p_correct(vector)
        correct = rng.random() < p
        latency = int(rng.gauss(2200 + 1400 * tier_load(vector), 600))
        if correct:
            self.frustration = max(0.0, self.frustration - 0.5)
        else:
            self.frustration += 1.0
        # Desirable difficulty: learning peaks near TARGET_P, dies at the extremes.
        self.competence += self.learning_rate * math.exp(
            -(((p - TARGET_P) / 0.22) ** 2)
        )
        return correct, max(400, latency)

    def gave_up(self) -> bool:
        return self.frustration >= 3.0


def wrong_answer(operands: list[int], rng: random.Random) -> int:
    """A plausible wrong answer, biased towards the carry-omission class."""
    a, b = operands
    if rng.random() < 0.55:
        width = max(len(str(a)), len(str(b)))
        left, right = str(a).rjust(width, "0"), str(b).rjust(width, "0")
        digits = [(int(x) + int(y)) % 10 for x, y in zip(left, right, strict=True)]
        return int("".join(str(d) for d in digits) or "0")
    return a + b + rng.choice([-10, -1, 1, 10])


# --------------------------------------------------------------------------- #
# policies
# --------------------------------------------------------------------------- #


@dataclass
class State:
    vector: difficulty.Vector
    floor: difficulty.Vector
    credit: float = 0.0
    streak: int = 0
    changes_this_session: int = 0
    rating: float = 0.0
    seen: int = 0
    errors_in_a_row: int = 0


Policy = Callable[[State, list[int], int, bool, int, random.Random], difficulty.Vector]

# What main did before this change, kept here so the comparison stays honest once
# the production code no longer contains it. One correct answer, one rung harder;
# a wrong answer banks a fraction of a rung of relief, scaled by leniency.
OLD_LENIENCY_WEIGHTS = {"low": 1.0, "medium": 0.5, "high": 0.34}


def policy_current(
    state: State, operands: list[int], answer: int, correct: bool, latency: int, rng
) -> difficulty.Vector:
    """main before this change: one correct answer is one step up the ladder."""
    error_class = error_taxonomy.classify_attempt(operands, "+", answer)
    if error_class == error_taxonomy.CORRECT:
        return difficulty.increment(state.vector, SKILL)
    if error_class in (error_taxonomy.OPERATOR_CONFUSION, error_taxonomy.UNCLASSIFIED):
        return state.vector

    state.credit += OLD_LENIENCY_WEIGHTS["medium"]
    if state.credit < 1.0:
        return state.vector
    state.credit -= 1.0
    return difficulty.apply_movement(
        state.vector,
        SKILL,
        "decrement",
        state.floor,
        axis=error_taxonomy.AXIS_FOR_CLASS[error_class],
    )


CONSECUTIVE_TO_STEP_UP = 3
MAX_CHANGES_PER_SESSION = 3


def policy_staircase(
    state: State, operands: list[int], answer: int, correct: bool, latency: int, rng
) -> difficulty.Vector:
    """1-up / 3-down staircase (Levitt 1971): converges on ~79% success.

    Cheaper than an ability estimate, but it carries no memory of how hard the
    child found the tiers below, so every session re-walks the same rungs.
    """
    if correct:
        state.streak += 1
        if state.streak < CONSECUTIVE_TO_STEP_UP:
            return state.vector
        if state.changes_this_session >= MAX_CHANGES_PER_SESSION:
            return state.vector
        state.streak = 0
        state.changes_this_session += 1
        return difficulty.increment(state.vector, SKILL)

    state.streak = 0
    updated = policy_current(state, operands, answer, correct, latency, rng)
    if difficulty.rank(updated, SKILL) != difficulty.rank(state.vector, SKILL):
        state.changes_this_session += 1
    return updated


def policy_shipped(
    state: State, operands: list[int], answer: int, correct: bool, latency: int, rng
) -> difficulty.Vector:
    """What this change ships: app/ability.py, called through app/adaptation.py.

    Computer Adaptive Practice (Klinkenberg 2011) rates the child and aims each
    question at p=.80, with a deadband so the tier does not move for every
    answer. The rating update is on correctness alone: response time deliberately
    stays out of it.
    """
    decision = adaptation.next_vector(
        vector=state.vector,
        skill_id=SKILL,
        operands=operands,
        operator="+",
        answer_given=answer,
        latency_ms=latency,
        baseline=None,
        floor=state.floor,
        leniency_band="medium",
        rating=state.rating,
        attempts_seen=state.seen,
        prior_errors_in_a_row=state.errors_in_a_row,
    )
    state.rating = decision.rating
    state.errors_in_a_row = decision.errors_in_a_row
    state.seen += 1
    return decision.vector


POLICIES: dict[str, Policy] = {
    "current (main)": policy_current,
    "staircase 1-up/3-down": policy_staircase,
    "shipped: ability + deadband": policy_shipped,
}


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def _tiers_by_load() -> list[difficulty.Vector]:
    """Every satisfiable tier, ordered by what the simulated child finds hard.

    Deliberately not app.ability's own ordering: 'at the ceiling' should mean
    what the child would call hardest, not what the policy believes is hardest.
    """
    tiers = [
        {**difficulty.base_vector(digits), "magnitude": band, "carries": carries}
        for digits in (1, 2, 3)
        for band in difficulty.BANDS_BY_DIGITS[digits]
        for carries in (False, True)
    ]
    return sorted(
        (v for v in tiers if difficulty.satisfiable(v, SKILL)),
        key=lambda v: (tier_load(v), difficulty.rank(v, SKILL)),
    )


TIERS = _tiers_by_load()


@dataclass
class Result:
    accuracy: float
    in_band: float
    tier_changes: float
    hard_jumps: float
    max_error_run: float
    quit_rate: float
    skill_gain: float
    ceiling_share: float


def simulate(
    policy: Policy, competence: float, seed: int, sessions: int = SESSIONS
) -> Result:
    rng = random.Random(seed)
    child = Child(competence=competence)
    start = child.competence
    floor = difficulty.base_vector(1)
    state = State(vector=dict(floor), floor=floor)
    # Seeded from the floor the intake interview set, so the first question is
    # aimed rather than guessed.
    state.rating = ability.starting_rating(floor, SKILL, "medium")

    attempts = correct_count = in_band = changes = jumps = quits = ceiling = 0
    error_runs: list[int] = []

    for _ in range(sessions):
        child.frustration = 0.0
        state.changes_this_session = 0
        run = 0
        best_run = 0
        for _ in range(SESSION_LENGTH):
            question = difficulty.next_question(state.vector, SKILL, rng)
            p = child.p_correct(state.vector)
            correct, latency = child.answer(state.vector, rng)
            answer = (
                question["correct_answer"]
                if correct
                else wrong_answer(question["operands"], rng)
            )

            attempts += 1
            correct_count += correct
            in_band += BAND[0] <= p <= BAND[1]
            ceiling += tier_load(state.vector) >= tier_load(TIERS[-1]) - 0.01
            run = 0 if correct else run + 1
            best_run = max(best_run, run)

            before = state.vector
            state.vector = policy(
                state, question["operands"], answer, correct, latency, rng
            )
            changes += difficulty.tier_key(state.vector) != difficulty.tier_key(before)
            jumps += tier_load(state.vector) - tier_load(before) > 0.5

            if child.gave_up():
                quits += 1
                break
        error_runs.append(best_run)

    return Result(
        accuracy=correct_count / attempts,
        in_band=in_band / attempts,
        tier_changes=changes / sessions,
        hard_jumps=jumps / attempts,
        max_error_run=statistics.mean(error_runs),
        quit_rate=quits / sessions,
        skill_gain=child.competence - start,
        ceiling_share=ceiling / attempts,
    )


def main() -> None:
    profiles = {"struggling": 1.9, "typical": 2.6, "strong": 3.4}
    runs = 200

    print(
        f"{SESSIONS} sessions x {SESSION_LENGTH} questions, "
        f"{runs} simulated children each\n"
    )
    header = (
        f"{'policy':<30}{'child':<12}{'acc':>7}{'in-band':>9}"
        f"{'moves':>7}{'harder':>8}{'err-run':>9}{'quit':>7}{'gain':>7}{'ceiling':>9}"
    )
    for name, policy in POLICIES.items():
        print(header)
        for label, competence in profiles.items():
            results = [simulate(policy, competence, seed) for seed in range(runs)]
            print(
                f"{name:<30}{label:<12}"
                f"{statistics.mean(r.accuracy for r in results):>7.0%}"
                f"{statistics.mean(r.in_band for r in results):>9.0%}"
                f"{statistics.mean(r.tier_changes for r in results):>7.1f}"
                f"{statistics.mean(r.hard_jumps for r in results):>8.0%}"
                f"{statistics.mean(r.max_error_run for r in results):>9.1f}"
                f"{statistics.mean(r.quit_rate for r in results):>7.0%}"
                f"{statistics.mean(r.skill_gain for r in results):>7.2f}"
                f"{statistics.mean(r.ceiling_share for r in results):>9.0%}"
            )
        print()


if __name__ == "__main__":
    main()
