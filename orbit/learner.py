"""Bayesian Knowledge Tracing, deliberately constrained.

Standard BKT has four free parameters per skill (L0, T, guess, slip). Fitting all
four to a few minutes of play from one child is not just noisy, it is
*unidentifiable*: Beck & Chang (2007) show an infinite family of parameter sets
that make identical predictions but different claims about what the learner
knows, and propose priors to break the tie.

So this implementation:

* fixes guess/slip to literature-plausible values (0.2 / 0.1),
* fits only L0 and T, by MAP with Beta priors over a grid,
* reports calibration and a bootstrapped Brier score instead of an AUC, because
  AUC over ~30 binary outcomes is not a number worth defending.

Reference: Corbett & Anderson (1995), doi:10.1007/BF01099821.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .telemetry import Attempt

GUESS = 0.2
SLIP = 0.1
#: Beta(a, b) priors: L0 mildly pessimistic, T mildly optimistic about learning.
PRIOR_L0 = (2.0, 3.0)
PRIOR_T = (2.0, 6.0)
GRID = tuple(round(0.02 + i * 0.04, 3) for i in range(25))  # 0.02 … 0.98


def _log_beta_prior(value: float, prior: tuple[float, float]) -> float:
    a, b = prior
    return (a - 1.0) * math.log(value) + (b - 1.0) * math.log(1.0 - value)


@dataclass(frozen=True)
class SkillModel:
    """Fitted parameters and the posterior mastery they imply."""

    skill: str
    l0: float
    transit: float
    mastery: float
    n_attempts: int

    def predict(self, mastery: float) -> float:
        """P(correct) given current mastery."""
        return mastery * (1.0 - SLIP) + (1.0 - mastery) * GUESS


def _forward(observations: Sequence[bool], l0: float, transit: float) -> tuple[float, float]:
    """Return (log-likelihood, posterior mastery) for one parameter pair."""
    mastery = l0
    log_likelihood = 0.0
    for correct in observations:
        p_correct = mastery * (1.0 - SLIP) + (1.0 - mastery) * GUESS
        p_correct = min(max(p_correct, 1e-6), 1 - 1e-6)
        log_likelihood += math.log(p_correct if correct else 1.0 - p_correct)
        if correct:
            posterior = mastery * (1.0 - SLIP) / p_correct
        else:
            posterior = mastery * SLIP / (1.0 - p_correct)
        mastery = posterior + (1.0 - posterior) * transit
    return log_likelihood, mastery


def fit_skill(skill: str, observations: Sequence[bool]) -> SkillModel:
    """MAP fit of (L0, T) over a grid. Falls back to the prior mean if unobserved."""
    if not observations:
        return SkillModel(skill, 0.4, 0.25, 0.4, 0)
    best = (-math.inf, GRID[0], GRID[0], GRID[0])
    for l0 in GRID:
        prior_l0 = _log_beta_prior(l0, PRIOR_L0)
        for transit in GRID:
            log_likelihood, mastery = _forward(observations, l0, transit)
            score = log_likelihood + prior_l0 + _log_beta_prior(transit, PRIOR_T)
            if score > best[0]:
                best = (score, l0, transit, mastery)
    _, l0, transit, mastery = best
    return SkillModel(skill, l0, transit, mastery, len(observations))


class LearnerModel:
    """A per-skill BKT fit for one learner."""

    def __init__(self, skills: dict[str, SkillModel]):
        self.skills = skills

    @classmethod
    def fit(cls, attempts: Iterable[Attempt]) -> LearnerModel:
        by_skill: dict[str, list[bool]] = {}
        for attempt in attempts:
            by_skill.setdefault(attempt.skill, []).append(attempt.correct)
        return cls({skill: fit_skill(skill, obs) for skill, obs in by_skill.items()})

    def mastery(self, skill: str) -> float:
        model = self.skills.get(skill)
        return model.mastery if model else 0.4

    def predict_sequence(self, attempts: Sequence[Attempt]) -> list[float]:
        """Predicted P(correct) before each attempt, replaying the fitted params."""
        mastery = {skill: model.l0 for skill, model in self.skills.items()}
        predictions: list[float] = []
        for attempt in attempts:
            model = self.skills.get(attempt.skill)
            if model is None:
                predictions.append(GUESS)
                continue
            current = mastery.get(attempt.skill, model.l0)
            p_correct = current * (1.0 - SLIP) + (1.0 - current) * GUESS
            predictions.append(p_correct)
            if attempt.correct:
                posterior = current * (1.0 - SLIP) / max(p_correct, 1e-6)
            else:
                posterior = current * SLIP / max(1.0 - p_correct, 1e-6)
            mastery[attempt.skill] = posterior + (1.0 - posterior) * model.transit
        return predictions


def brier_score(predictions: Sequence[float], outcomes: Sequence[bool]) -> float:
    if not predictions:
        return float("nan")
    squared = [(p - float(o)) ** 2 for p, o in zip(predictions, outcomes, strict=True)]
    return sum(squared) / len(squared)


def bootstrap_brier(
    predictions: Sequence[float],
    outcomes: Sequence[bool],
    *,
    samples: int = 2000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Point estimate and a percentile 95% CI — the CI is the point of reporting it."""
    point = brier_score(predictions, outcomes)
    if len(predictions) < 2:
        return point, float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(predictions)
    draws = []
    for _ in range(samples):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(
            brier_score([predictions[i] for i in idx], [outcomes[i] for i in idx])
        )
    draws.sort()
    return point, draws[int(0.025 * samples)], draws[int(0.975 * samples) - 1]


def calibration_bins(
    predictions: Sequence[float], outcomes: Sequence[bool], bins: int = 3
) -> list[dict[str, float]]:
    """Predicted vs observed correctness, with n per bin so small samples show it."""
    out: list[dict[str, float]] = []
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        picked = [
            (p, o)
            for p, o in zip(predictions, outcomes, strict=True)
            if (lo <= p < hi) or (index == bins - 1 and p == hi)
        ]
        if not picked:
            continue
        out.append(
            {
                "bin_low": lo,
                "bin_high": hi,
                "n": len(picked),
                "predicted": sum(p for p, _ in picked) / len(picked),
                "observed": sum(float(o) for _, o in picked) / len(picked),
            }
        )
    return out
