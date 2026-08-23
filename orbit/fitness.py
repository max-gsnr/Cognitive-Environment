"""The objective function the search optimises.

The first version of this score rewarded mastery gain per minute plus engagement
minus abandonment — and every one of those terms is maximised by making the game
trivially easy, which inverts the whole point. Two terms fix that:

* mastery gain is weighted by item difficulty, so credit scales with cognitive
  demand rather than with how many items scroll past;
* a penalty on ``|success_rate - target|`` with target 0.85, the optimal training
  accuracy derived by Wilson et al. (Nat. Commun. 2019, doi:10.1038/s41467-019-12552-4)
  and consistent with Bjork's desirable-difficulties work.

An extraneous-load proxy (share of session time that is not deliberation on an
item) stands in for Sweller's extraneous load: overhead that consumes working
memory without teaching anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from statistics import mean

from . import engagement as engagement_module
from .learner import LearnerModel
from .telemetry import Trace

TARGET_SUCCESS = 0.85
#: The child's allotted session length. Mastery gain is expressed per minute of
#: *allotted* time, not per minute actually played — otherwise a game that ends
#: after 30 seconds gets a rate bonus for the time it never used, and quitting
#: early becomes an optimisation.
REFERENCE_SESSION_MS = 240_000


@dataclass(frozen=True)
class Weights:
    mastery: float = 1.0
    engagement: float = 0.6
    abandonment: float = 1.2
    load: float = 0.3
    difficulty: float = 0.8

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


#: Frozen, so it is safe to share as the default for every scoring call.
DEFAULT_WEIGHTS = Weights()


@dataclass(frozen=True)
class Score:
    total: float
    mastery_gain_per_min: float
    engaged_fraction: float
    abandonment_rate: float
    extraneous_load: float
    success_rate: float
    difficulty_penalty: float
    n_attempts: int

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def difficulty_weighted_mastery_gain(trace: Trace) -> float:
    """Posterior mastery minus fitted prior, weighted by each skill's difficulty."""
    attempts = trace.attempts
    if not attempts:
        return 0.0
    model = LearnerModel.fit(attempts)
    difficulty = {a.skill: a.difficulty for a in attempts}
    total = 0.0
    for skill, fitted in model.skills.items():
        gain = max(0.0, fitted.mastery - fitted.l0)
        total += gain * difficulty.get(skill, 1)
    return total


def extraneous_load(trace: Trace) -> float:
    """Fraction of session time that was not spent deliberating on an item."""
    duration = trace.duration_ms
    if duration <= 0:
        return 0.0
    thinking = sum(a.latency_ms for a in trace.attempts)
    return min(1.0, max(0.0, 1.0 - thinking / duration))


def score_trace(trace: Trace, weights: Weights = DEFAULT_WEIGHTS) -> Score:
    minutes = max(trace.duration_ms, REFERENCE_SESSION_MS) / 60000.0
    gain = difficulty_weighted_mastery_gain(trace) / minutes
    signals = engagement_module.measure(trace)
    success = trace.success_rate()
    penalty = abs(success - TARGET_SUCCESS) / TARGET_SUCCESS
    load = extraneous_load(trace)
    abandonment = 1.0 if trace.abandoned else 0.0

    total = (
        weights.mastery * gain
        + weights.engagement * signals.engaged_fraction
        - weights.abandonment * abandonment
        - weights.load * load
        - weights.difficulty * penalty
    )
    return Score(
        total=total,
        mastery_gain_per_min=gain,
        engaged_fraction=signals.engaged_fraction,
        abandonment_rate=abandonment,
        extraneous_load=load,
        success_rate=success,
        difficulty_penalty=penalty,
        n_attempts=len(trace.attempts),
    )


def score_candidate(traces: Sequence[Trace], weights: Weights = DEFAULT_WEIGHTS) -> Score:
    """Average the per-trace scores over simulated learners."""
    if not traces:
        raise ValueError("a candidate needs at least one rollout to be scored")
    scores = [score_trace(trace, weights) for trace in traces]
    return Score(
        total=mean(s.total for s in scores),
        mastery_gain_per_min=mean(s.mastery_gain_per_min for s in scores),
        engaged_fraction=mean(s.engaged_fraction for s in scores),
        abandonment_rate=mean(s.abandonment_rate for s in scores),
        extraneous_load=mean(s.extraneous_load for s in scores),
        success_rate=mean(s.success_rate for s in scores),
        difficulty_penalty=mean(s.difficulty_penalty for s in scores),
        n_attempts=sum(s.n_attempts for s in scores),
    )
