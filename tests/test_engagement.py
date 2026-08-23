"""Engagement detectors: log-based only, no diagnosis.

These are Baker-style behaviour detectors over the event log — fast wrong answers,
hint abuse, idle gaps. They are inputs to the objective function, never a claim
about a child.
"""

from __future__ import annotations

from orbit import engagement
from orbit.telemetry import Trace


def answer(t_ms: int, *, correct: bool, latency_ms: int, hinted: bool = False) -> dict:
    return {
        "type": "answer_submitted",
        "t_ms": t_ms,
        "skill": "add",
        "difficulty": 1,
        "correct": correct,
        "latency_ms": latency_ms,
        "hinted": hinted,
    }


def test_fast_wrong_answers_are_flagged_as_guessing() -> None:
    trace = Trace.from_events(
        [answer(i * 500, correct=False, latency_ms=300) for i in range(8)]
    )
    signals = engagement.measure(trace)
    assert signals.fast_guess_rate > 0.9
    assert signals.gaming_proxy > 0.5


def test_slow_correct_answers_are_not_guessing() -> None:
    trace = Trace.from_events(
        [answer(i * 4000, correct=True, latency_ms=3800) for i in range(8)]
    )
    signals = engagement.measure(trace)
    assert signals.fast_guess_rate == 0.0
    assert signals.engaged_fraction == 1.0


def test_fast_correct_answers_are_not_guessing() -> None:
    """Fluency looks like guessing unless correctness is taken into account."""
    trace = Trace.from_events(
        [answer(i * 900, correct=True, latency_ms=600) for i in range(8)]
    )
    assert engagement.measure(trace).fast_guess_rate == 0.0


def test_idle_gaps_reduce_engaged_fraction() -> None:
    events: list[dict] = []
    t = 0
    for index in range(6):
        events.append(answer(t, correct=True, latency_ms=2000))
        t += 2000
        if index % 2 == 0:
            events.append({"type": "idle_tick", "t_ms": t, "gap_ms": 15000})
            t += 15000
    signals = engagement.measure(Trace.from_events(events))
    assert signals.off_task_ticks == 3
    assert signals.engaged_fraction < 0.6


def test_wrong_streak_is_tracked() -> None:
    pattern = [True, False, False, False, False, True]
    trace = Trace.from_events(
        [answer(i * 3000, correct=ok, latency_ms=2500) for i, ok in enumerate(pattern)]
    )
    assert engagement.measure(trace).max_wrong_streak == 4


def test_hint_rate_and_median_latency() -> None:
    trace = Trace.from_events(
        [
            answer(0, correct=True, latency_ms=1000, hinted=True),
            answer(3000, correct=True, latency_ms=3000),
            answer(6000, correct=True, latency_ms=5000),
        ]
    )
    signals = engagement.measure(trace)
    assert abs(signals.hint_rate - 1 / 3) < 1e-9
    assert signals.median_latency_ms == 3000


def test_gaming_proxy_is_bounded() -> None:
    trace = Trace.from_events(
        [answer(i * 400, correct=False, latency_ms=200, hinted=True) for i in range(10)]
    )
    assert engagement.measure(trace).gaming_proxy <= 1.0


def test_empty_trace_is_safe() -> None:
    signals = engagement.measure(Trace.from_events([]))
    assert signals.engaged_fraction == 0.0
    assert signals.gaming_proxy == 0.0
