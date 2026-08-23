"""The deterministic read on a session: same events in, same diagnosis out."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import telemetry_signals as ts

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "loop_b"
BASELINE_MS = 4000.0


def event(name: str, **properties: Any) -> dict[str, Any]:
    return {"event": name, "properties": properties}


def answer(latency_ms: int, correct: bool, error_class: str) -> dict[str, Any]:
    return event(
        "answer_submitted",
        time_to_solve_ms=latency_ms,
        correct=correct,
        error_class=error_class,
    )


def test_idle_ratio_is_idle_time_over_time_on_task() -> None:
    signals = ts.summarize(
        [event("idle_tick")] * 4 + [answer(5000, True, "correct")] * 4
    )
    # 20s idle against 20s solving.
    assert signals.idle_seconds == 20
    assert signals.solve_seconds == 20.0
    assert signals.idle_ratio == 0.5


def test_a_session_with_no_events_reads_as_nothing_rather_than_dividing_by_zero() -> (
    None
):
    signals = ts.summarize([])
    assert signals.idle_ratio == 0.0
    assert signals.fast_wrong_ratio == 0.0
    assert ts.dominant(signals) == ts.INCONCLUSIVE


def test_fast_and_wrong_is_measured_against_the_childs_own_pace() -> None:
    events = [answer(1900, False, "counting_slip")] * 4
    # 1.9s is impulsive for a child who usually takes 4s ...
    assert ts.summarize(events, baseline_ms=BASELINE_MS).fast_wrong_ratio == 1.0
    # ... and unremarkable for a child who usually takes 2.
    assert ts.summarize(events, baseline_ms=2000.0).fast_wrong_ratio == 0.0


def test_slow_needs_a_baseline_and_never_guesses_one() -> None:
    events = [answer(30000, True, "correct")] * 5
    assert ts.summarize(events, baseline_ms=BASELINE_MS).slow_correct_ratio == 1.0
    assert ts.summarize(events).slow_correct_ratio == 0.0


def test_jitter_disqualifies_the_disengagement_reading() -> None:
    """A confused child jitters; a bored child goes still. Only stillness counts."""
    still = [answer(20000, False, "unclassified")] * 3
    assert ts.summarize(still, baseline_ms=BASELINE_MS).disengaged_answers == 3
    jittering = [*still, event("motion_event", type="micro_jitter")]
    assert ts.summarize(jittering, baseline_ms=BASELINE_MS).disengaged_answers == 0


def test_disengagement_is_not_read_above_mastered_material() -> None:
    events = [answer(20000, False, "unclassified")] * 3
    signals = ts.summarize(events, baseline_ms=BASELINE_MS, at_or_below_mastered=False)
    assert signals.disengaged_answers == 0


def test_a_reported_problem_outranks_every_other_signal() -> None:
    """A bug makes every other measurement a measurement of the bug."""
    events = [event("problem_shown")] * 8 + [answer(900, False, "counting_slip")] * 6
    signals = ts.summarize(events, baseline_ms=BASELINE_MS)
    assert ts.dominant(signals) == ts.IMPULSIVE
    assert ts.dominant(signals, reported_problems=1) == ts.FRUSTRATION


def test_effort_is_never_read_as_needing_an_easier_game() -> None:
    events = (
        [event("problem_shown")] * 6
        + [event("motion_event", type="micro_jitter")] * 5
        + [event("edit_event", type="after_pause_correction")] * 3
        + [answer(9000, True, "correct")] * 5
    )
    signals = ts.summarize(events, baseline_ms=BASELINE_MS)
    # Slow-and-correct on its own would say working memory; the effort outranks it.
    assert signals.slow_correct_ratio >= ts.HIGH_SLOW_CORRECT_RATIO
    assert ts.dominant(signals) == ts.HEALTHY_STRUGGLE
    assert ts.CHANGE_TIER[ts.HEALTHY_STRUGGLE] == "none"


def test_a_short_session_is_inconclusive_not_diagnosed() -> None:
    events = [event("problem_shown")] * 2 + [answer(500, False, "counting_slip")] * 2
    assert ts.dominant(ts.summarize(events, baseline_ms=BASELINE_MS)) == ts.INCONCLUSIVE


def test_orbiting_is_read_through_the_profile() -> None:
    events = (
        [event("problem_shown")] * 6
        + [event("motion_event", type="repetitive_orbit")] * 4
        + [answer(20000, False, "unclassified")] * 3
    )
    signals = ts.summarize(events, baseline_ms=BASELINE_MS)
    assert ts.dominant(signals) == ts.BORED
    assert (
        ts.dominant(signals, restlessness_interpretation="self_regulation")
        != ts.BORED
    )


def test_report_carries_a_tier_and_a_fix_for_every_signal() -> None:
    report = ts.report([], baseline_ms=None)
    assert report["change_tier"] == "none"
    assert report["suggested_fix"]
    assert set(ts.CHANGE_TIER) == set(ts.FIX)


@pytest.mark.parametrize(
    "path", sorted(FIXTURES.glob("*.json")), ids=lambda path: path.stem
)
def test_recorded_sessions_get_the_reading_they_should(path: Path) -> None:
    """The offline eval set (scripts/loop_b_eval.py), run as part of the suite."""
    fixture = json.loads(path.read_text())
    report = ts.report(
        fixture["events"],
        baseline_ms=fixture.get("baseline_ms"),
        reported_problems=fixture.get("reported_problems", 0),
        restlessness_interpretation=fixture.get(
            "restlessness_interpretation", "unknown"
        ),
    )
    assert report["dominant_signal"] == fixture["expected_signal"], fixture["why"]
    assert report["change_tier"] == fixture["expected_change_tier"]
