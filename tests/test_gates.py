"""The gates are the safety argument, so they are tested separately from fitness.

A gate that fires on the wrong candidate is as expensive as one that misses: a
false positive burns a Devin session's whole output, so both directions matter.
"""

from __future__ import annotations

from pathlib import Path

from orbit import gates
from orbit.policy import COHORT
from orbit.rollout import RolloutResult
from orbit.telemetry import Trace
from tests.test_fitness import SWEET_SPOT, synthetic_trace

CONTRACT = "window.orbit={observe(){},drainEvents(){},isOver(){}};"


def source(path: Path, body: str) -> Path:
    path.write_text(f"<html><script>{body}</script></html>", encoding="utf-8")
    return path


def rollouts(trace: Trace, *, console_errors: list[str] | None = None) -> list[RolloutResult]:
    return [
        RolloutResult(
            trace=trace,
            console_errors=console_errors or [],
            profile=COHORT[0].name,
        )
    ]


def test_a_documented_ban_is_not_a_violation(tmp_path: Path) -> None:
    path = source(
        tmp_path / "commented.html",
        "// Design note: no countdown timer, no timeLeft display.\n" + CONTRACT,
    )
    assert gates.check_source(path) == []


def test_an_actual_countdown_is_rejected(tmp_path: Path) -> None:
    path = source(tmp_path / "timer.html", CONTRACT + "let timeLeft = 30;")
    assert "countdown timer detected" in gates.check_source(path)


def test_fast_animation_is_rejected(tmp_path: Path) -> None:
    path = source(tmp_path / "flash.html", CONTRACT + "setInterval(flash, 100);")
    failures = gates.check_source(path)
    assert any("3 Hz" in failure for failure in failures)


def test_slow_animation_is_allowed(tmp_path: Path) -> None:
    path = source(tmp_path / "slow.html", CONTRACT + "setInterval(tick, 1000);")
    assert gates.check_source(path) == []


def test_missing_contract_is_rejected(tmp_path: Path) -> None:
    path = source(tmp_path / "bare.html", "let x = 1;")
    assert "evaluation contract missing from source" in gates.check_source(path)


def test_console_errors_fail_the_candidate() -> None:
    failures = gates.check_rollouts(rollouts(SWEET_SPOT, console_errors=["TypeError: x"]))
    assert any("javascript error" in failure for failure in failures)


def test_universal_abandonment_fails_the_candidate() -> None:
    trace = synthetic_trace(n=20, success_rate=0.85, difficulty=3, abandoned=True)
    failures = gates.check_rollouts(rollouts(trace))
    assert "every simulated learner abandoned the session" in failures
