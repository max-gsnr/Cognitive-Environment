"""Our own checks on a generated game, graded against a good and a broken one."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app import difficulty, gates
from app.routers.games import gates_passed

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = str(FIXTURES / "good_game")
BAD = str(FIXTURES / "bad_game")
VECTOR = difficulty.floor_vector("single_digit")

ALL_REPORTED_PASSING = {
    gate: "PASS - fine"
    for gate in ("schema", "assertions", "playthrough", "render_accessibility")
}


def test_a_conforming_game_passes_every_static_check() -> None:
    results = gates.verify_static(GOOD)
    assert not [name for name, value in results.items() if value.startswith("FAIL")]


def test_a_game_that_owns_its_own_difficulty_is_caught() -> None:
    results = gates.verify_static(BAD)
    assert results["shell_contract"].startswith("FAIL")
    assert "next-question" in results["shell_contract"]


def test_missing_telemetry_is_caught_because_loop_b_would_go_blind() -> None:
    results = gates.verify_static(BAD)
    assert results["instrumentation"].startswith("FAIL")
    assert "idle_tick" in results["instrumentation"]


def test_a_10hz_flash_is_caught() -> None:
    """WCAG 2.3.1, and a seizure risk is not something to take on report."""
    assert gates.verify_static(BAD)["no_fast_flashing"].startswith("FAIL")
    assert gates.verify_static(GOOD)["no_fast_flashing"].startswith("PASS")


def test_invisible_keyboard_focus_is_caught() -> None:
    assert gates.verify_static(BAD)["focus_visible"].startswith("FAIL")


def test_a_missing_game_directory_fails_rather_than_passing_vacuously() -> None:
    assert gates.verify_static(None)["files"].startswith("FAIL")
    assert gates.verify_static("/nonexistent/game")["files"].startswith("FAIL")


def test_a_report_of_passing_gates_is_not_enough_when_our_check_failed() -> None:
    assert gates_passed(ALL_REPORTED_PASSING)
    assert not gates_passed({**ALL_REPORTED_PASSING, "independent": {"passed": False}})
    assert gates_passed({**ALL_REPORTED_PASSING, "independent": {"passed": True}})


def test_static_failures_short_circuit_the_browser_check() -> None:
    results = asyncio.run(gates.verify(BAD, "addition", VECTOR))
    assert results["passed"] is False
    assert "playthrough" not in results


def test_a_playthrough_draws_questions_and_posts_answers() -> None:
    pytest.importorskip("playwright.async_api")
    verdict = asyncio.run(gates.verify_playthrough(GOOD, "addition", VECTOR))
    assert verdict.startswith("PASS"), verdict


def test_an_unrunnable_browser_check_is_a_skip_not_a_pass() -> None:
    """A gap we could not look at must not read like a gap that is not there."""
    results = asyncio.run(gates.verify(GOOD, "addition", VECTOR))
    if results.get("skipped"):
        assert "playthrough" in results["skipped"]
    assert results["passed"] is True
