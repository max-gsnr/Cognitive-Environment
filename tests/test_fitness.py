"""The objective function's own sanity check.

The first fitness function I wrote was maximised by a game where everything is
trivial, which inverts the pedagogy. These tests are the guard: if a change makes
the easy game win, the search is broken and no amount of agent time fixes it.
"""

from __future__ import annotations

from orbit import fitness
from orbit.telemetry import Trace


def synthetic_trace(
    *,
    n: int,
    success_rate: float,
    difficulty: int,
    latency_ms: int = 3000,
    gap_ms: int = 0,
    abandoned: bool = False,
) -> Trace:
    """Build a trace with a chosen success rate and difficulty, no browser needed."""
    events: list[dict[str, object]] = []
    t = 0
    correct_target = round(n * success_rate)
    for index in range(n):
        correct = index < correct_target
        events.append(
            {
                "type": "problem_shown",
                "t_ms": t,
                "skill": f"tier_{difficulty}",
                "difficulty": difficulty,
            }
        )
        t += latency_ms
        events.append(
            {
                "type": "answer_submitted",
                "t_ms": t,
                "skill": f"tier_{difficulty}",
                "difficulty": difficulty,
                "correct": correct,
                "latency_ms": latency_ms,
                "hinted": False,
            }
        )
        if gap_ms:
            events.append({"type": "idle_tick", "t_ms": t, "gap_ms": gap_ms})
            t += gap_ms
    events.append(
        {
            "type": "level_abandoned" if abandoned else "level_complete",
            "t_ms": t,
            "solved": correct_target,
            "attempts": n,
        }
    )
    return Trace.from_events(events)


TRIVIAL = synthetic_trace(n=40, success_rate=1.0, difficulty=1, latency_ms=1200)
BRUTAL = synthetic_trace(n=20, success_rate=0.35, difficulty=4, latency_ms=6000)
SWEET_SPOT = synthetic_trace(n=28, success_rate=0.85, difficulty=3, latency_ms=4000)


def test_sweet_spot_beats_trivially_easy() -> None:
    """The regression that killed v1 of the objective."""
    assert fitness.score_trace(SWEET_SPOT).total > fitness.score_trace(TRIVIAL).total


def test_sweet_spot_beats_brutally_hard() -> None:
    assert fitness.score_trace(SWEET_SPOT).total > fitness.score_trace(BRUTAL).total


def test_difficulty_penalty_is_zero_at_target() -> None:
    at_target = synthetic_trace(n=20, success_rate=0.85, difficulty=2)
    assert fitness.score_trace(at_target).difficulty_penalty < 0.01


def test_mastery_gain_is_difficulty_weighted() -> None:
    """Same success rate and pacing, harder items: more credit."""
    easy = synthetic_trace(n=24, success_rate=0.85, difficulty=1)
    hard = synthetic_trace(n=24, success_rate=0.85, difficulty=4)
    assert (
        fitness.score_trace(hard).mastery_gain_per_min
        > fitness.score_trace(easy).mastery_gain_per_min
    )


def test_abandonment_dominates() -> None:
    """A learner who quits cannot win, whatever the rest of the score says."""
    quit_trace = synthetic_trace(n=12, success_rate=0.85, difficulty=3, abandoned=True)
    assert fitness.score_trace(quit_trace).total < fitness.score_trace(SWEET_SPOT).total


def test_off_task_time_reduces_engagement() -> None:
    distracted = synthetic_trace(n=20, success_rate=0.85, difficulty=3, gap_ms=12000)
    assert fitness.score_trace(distracted).engaged_fraction < 0.75
    assert fitness.score_trace(distracted).total < fitness.score_trace(SWEET_SPOT).total


def test_score_candidate_averages_rollouts() -> None:
    score = fitness.score_candidate([SWEET_SPOT, SWEET_SPOT])
    assert score.n_attempts == 2 * len(SWEET_SPOT.attempts)
    assert abs(score.total - fitness.score_trace(SWEET_SPOT).total) < 1e-9
