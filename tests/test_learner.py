"""Learner-model tests. The claim under test is modest on purpose.

With ~30 attempts we do not claim identifiable BKT parameters (Beck & Chang 2007);
guess and slip are fixed and only L0 and T are fitted. What we do claim is that
the fit moves in the right direction and that the calibration numbers we put in
front of judges are computed correctly.
"""

from __future__ import annotations

from orbit.learner import (
    GUESS,
    SLIP,
    LearnerModel,
    bootstrap_brier,
    brier_score,
    calibration_bins,
    fit_skill,
)
from orbit.telemetry import Attempt


def attempts(skill: str, pattern: str, difficulty: int = 1) -> list[Attempt]:
    """`pattern` is a string of 1/0 characters, oldest attempt first."""
    return [
        Attempt(
            skill=skill,
            difficulty=difficulty,
            correct=char == "1",
            latency_ms=3000,
            hinted=False,
            t_ms=index * 3000,
        )
        for index, char in enumerate(pattern)
    ]


def test_mastery_rises_when_the_learner_improves() -> None:
    improving = fit_skill("add", [False, False, False, True, True, True, True, True])
    assert improving.mastery > improving.l0


def test_mastery_stays_low_when_the_learner_does_not() -> None:
    stuck = fit_skill("add", [False] * 8)
    assert stuck.mastery < 0.35


def test_prediction_is_bounded_by_guess_and_slip() -> None:
    model = fit_skill("add", [True] * 10)
    assert model.predict(0.0) == GUESS
    assert abs(model.predict(1.0) - (1.0 - SLIP)) < 1e-9


def test_fit_is_per_skill() -> None:
    model = LearnerModel.fit(
        attempts("easy", "11111111") + attempts("hard", "00000000", difficulty=4)
    )
    assert model.skills["easy"].mastery > model.skills["hard"].mastery


def test_predict_sequence_tracks_within_skill_learning() -> None:
    sequence = attempts("add", "00001111")
    predictions = LearnerModel.fit(sequence).predict_sequence(sequence)
    assert len(predictions) == len(sequence)
    assert predictions[-1] > predictions[0]


def test_brier_score_bounds() -> None:
    assert brier_score([1.0, 0.0], [True, False]) == 0.0
    assert brier_score([0.0, 1.0], [True, False]) == 1.0


def test_bootstrap_returns_an_interval_containing_the_point_estimate() -> None:
    predictions = [0.7] * 20
    outcomes = [True] * 14 + [False] * 6
    point, low, high = bootstrap_brier(predictions, outcomes, samples=200, seed=1)
    assert low <= point <= high


def test_calibration_bins_report_sample_sizes() -> None:
    predictions = [0.1, 0.2, 0.5, 0.55, 0.9, 0.95]
    outcomes = [False, False, True, False, True, True]
    bins = calibration_bins(predictions, outcomes, bins=3)
    assert sum(int(b["n"]) for b in bins) == len(predictions)
    for entry in bins:
        assert 0.0 <= entry["predicted"] <= 1.0
        assert 0.0 <= entry["observed"] <= 1.0


def test_empty_input_is_safe() -> None:
    model = LearnerModel.fit([])
    assert model.skills == {}
    assert model.predict_sequence([]) == []
