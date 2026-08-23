"""Which mutation operator to spend the next Devin session on.

ShinkaEvolve (ICLR 2026) uses a bandit to pick among LLMs; the same argument
applies with more force to the *operator*, because here one arm-pull is an agent
session and the budget is tens of pulls, not thousands. A UCB1 posterior over
"did this operator improve fitness" is the cheapest thing that both exploits a
lever that is working and keeps trying the others.

Reward is bounded to [0, 1] deliberately: the raw fitness delta is unbounded and
a single lucky candidate would otherwise pin the arm forever.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Arm:
    name: str
    pulls: int = 0
    reward: float = 0.0
    #: Prior in [0, 1] from the trace (see :func:`orbit.operators.indications`).
    prior: float = 0.5

    @property
    def mean(self) -> float:
        if not self.pulls:
            return self.prior
        # Blend the prior in as one pseudo-observation so an untried operator
        # that the logs point at is preferred over one that is merely untried.
        return (self.reward + self.prior) / (self.pulls + 1)


@dataclass
class Bandit:
    """UCB1 over operator names, persistable across generations and runs."""

    arms: dict[str, Arm] = field(default_factory=dict)
    exploration: float = 0.7

    @classmethod
    def over(cls, names: list[str], priors: dict[str, float] | None = None) -> Bandit:
        priors = priors or {}
        return cls(
            arms={
                name: Arm(name=name, prior=float(priors.get(name, 0.5))) for name in names
            }
        )

    @property
    def total_pulls(self) -> int:
        return sum(arm.pulls for arm in self.arms.values())

    def score(self, name: str) -> float:
        arm = self.arms[name]
        if not arm.pulls:
            # Unplayed arms sort by prior, above every played arm's bonus range.
            return 10.0 + arm.prior
        total = max(1, self.total_pulls)
        return arm.mean + self.exploration * math.sqrt(math.log(total) / arm.pulls)

    def select(self, k: int = 1) -> list[str]:
        """The k highest-UCB operators — one Devin session each, run in parallel."""
        ranked = sorted(self.arms, key=lambda name: (-self.score(name), name))
        return ranked[:k]

    def update(self, name: str, *, parent_fitness: float, candidate_fitness: float) -> float:
        """Record an outcome. Returns the bounded reward that was credited."""
        arm = self.arms.setdefault(name, Arm(name=name))
        delta = candidate_fitness - parent_fitness
        # Squash: 0 for "made it worse", 0.5 for neutral, ->1 for a clear win.
        reward = 1.0 / (1.0 + math.exp(-4.0 * delta))
        arm.pulls += 1
        arm.reward += reward
        return reward

    def reprior(self, priors: dict[str, float]) -> None:
        """Refresh priors from the newest trace without losing observed history."""
        for name, prior in priors.items():
            if name in self.arms:
                self.arms[name].prior = float(prior)

    def as_dict(self) -> dict[str, object]:
        return {
            "exploration": self.exploration,
            "arms": {name: asdict(arm) for name, arm in self.arms.items()},
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Bandit:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            arms={name: Arm(**arm) for name, arm in raw["arms"].items()},
            exploration=float(raw.get("exploration", 0.7)),
        )
