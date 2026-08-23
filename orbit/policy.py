"""Simulated learners that actually play the game.

A policy sees only what the game exposes through ``window.orbit.observe()`` — the
same information a child sees on screen — and returns a target position on the
number line plus how long it deliberated. Deliberation time is *simulated*: the
harness advances the virtual clock by it, so a four-minute session costs
milliseconds of wall time without the game being faked.

Wrong answers are drawn from real error patterns rather than uniform noise:
off-by-one, dropping the carry, and operation confusion are the mistakes this age
group actually makes, and they are what a scaffold has to be able to fix.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LearnerProfile:
    """A seeded synthetic child."""

    name: str = "sim"
    #: P(retrieves correctly) per difficulty tier, before within-session learning.
    skill: dict[int, float] = field(
        default_factory=lambda: {1: 0.92, 2: 0.8, 3: 0.55, 4: 0.35}
    )
    #: Probability of using an offered hint when unsure.
    hint_tendency: float = 0.25
    #: Chance of a fast, unconsidered guess (Baker-style gaming).
    impulsivity: float = 0.12
    #: Within-session learning: mastery added to a tier after a scaffolded error.
    learning_rate: float = 0.06
    #: Tolerance for consecutive failures before quitting.
    frustration_limit: int = 5
    base_think_ms: int = 2200
    think_ms_per_tier: int = 900


@dataclass
class Decision:
    value: int
    think_ms: int
    use_hint: bool = False
    quit: bool = False


class SimulatedLearner:
    """Stateful policy: it learns a little and it can give up."""

    def __init__(self, profile: LearnerProfile, seed: int = 0):
        self.profile = profile
        self.rng = random.Random(seed)
        self.skill = dict(profile.skill)
        self.wrong_streak = 0

    def _wrong_answer(self, a: int, b: int, op: str, answer: int, limit: int) -> int:
        kind = self.rng.random()
        if kind < 0.4:
            guess = answer + self.rng.choice((-1, 1))
        elif kind < 0.7 and op == "+":
            guess = answer - 10 if answer >= 10 else answer + 1  # dropped carry
        elif kind < 0.85:
            guess = a - b if op == "+" else a + b  # operation confusion
        else:
            guess = self.rng.randint(0, limit)
        return max(0, min(limit, guess if guess != answer else answer + 1))

    def act(self, observation: dict[str, Any]) -> Decision:
        problem = observation.get("problem")
        if not problem:
            return Decision(value=0, think_ms=200)

        a, b, op = int(problem["a"]), int(problem["b"]), str(problem["op"])
        tier = int(problem.get("difficulty", 1))
        limit = int(observation.get("number_line_max", 20))
        answer = a + b if op == "+" else a - b
        mastery = self.skill.get(tier, 0.5)

        if self.wrong_streak >= self.profile.frustration_limit:
            return Decision(value=0, think_ms=500, quit=True)

        if self.rng.random() < self.profile.impulsivity:
            slipped = self._wrong_answer(a, b, op, answer, limit)
            value = answer if self.rng.random() < 0.25 else slipped
            self._record(value == answer, tier, scaffolded=False)
            return Decision(value=value, think_ms=self.rng.randint(250, 800))

        think = self.profile.base_think_ms + tier * self.profile.think_ms_per_tier
        think = int(think * self.rng.uniform(0.7, 1.4))

        use_hint = mastery < 0.6 and self.rng.random() < self.profile.hint_tendency
        effective = min(0.98, mastery + 0.25) if use_hint else mastery
        correct = self.rng.random() < effective
        value = answer if correct else self._wrong_answer(a, b, op, answer, limit)
        self._record(correct, tier, scaffolded=bool(observation.get("hint_visible")))
        return Decision(value=value, think_ms=think, use_hint=use_hint)

    def _record(self, correct: bool, tier: int, *, scaffolded: bool) -> None:
        if correct:
            self.wrong_streak = 0
            self.skill[tier] = min(0.99, self.skill.get(tier, 0.5) + 0.01)
        else:
            self.wrong_streak += 1
            if scaffolded:
                self.skill[tier] = min(
                    0.99, self.skill.get(tier, 0.5) + self.profile.learning_rate
                )


#: A small cohort. Varying learners is what stops the search overfitting one child.
COHORT: tuple[LearnerProfile, ...] = (
    LearnerProfile(name="steady"),
    LearnerProfile(
        name="impulsive", impulsivity=0.35, hint_tendency=0.1, frustration_limit=4
    ),
    LearnerProfile(
        name="careful", impulsivity=0.03, base_think_ms=3800, hint_tendency=0.45
    ),
    LearnerProfile(
        name="struggling",
        skill={1: 0.7, 2: 0.55, 3: 0.3, 4: 0.15},
        learning_rate=0.1,
        frustration_limit=6,
    ),
)
