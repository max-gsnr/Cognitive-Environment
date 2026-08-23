"""Write the Loop B eval fixtures in `evals/loop_b/`.

The fixtures are committed, so this only exists to regenerate them or add a case
without hand-writing a few hundred events. Each fixture is one recorded-looking
session plus the reading a clinician would give it, which is what the summarizer
is graded against (scripts/loop_b_eval.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "evals" / "loop_b"
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


def session(questions: int, *rest: dict[str, Any]) -> list[dict[str, Any]]:
    return [event("level_started"), *[event("problem_shown")] * questions, *rest]


def fixtures() -> list[dict[str, Any]]:
    return [
        {
            "name": "bored_on_easy_material",
            "why": (
                "Idle most of the session, still (no jitter), and answers that land "
                "nowhere on material already mastered -- the game has failed, "
                "not the math."
            ),
            "baseline_ms": BASELINE_MS,
            "events": session(
                6,
                *[event("idle_tick")] * 12,
                *[event("motion_event", type="repetitive_orbit")] * 4,
                *[answer(14000, False, "unclassified")] * 3,
                *[answer(3800, True, "correct")] * 3,
            ),
            "expected_signal": "bored_with_the_game",
            "expected_change_tier": "presentation",
        },
        {
            "name": "healthy_struggle",
            "why": (
                "Jitter plus corrections after a pause is a child working hard. "
                "Weakening the game here would be the wrong move."
            ),
            "baseline_ms": BASELINE_MS,
            "events": session(
                8,
                *[event("motion_event", type="micro_jitter")] * 9,
                *[event("edit_event", type="after_pause_correction")] * 5,
                *[event("edit_event", type="immediate_correction")] * 2,
                *[answer(7000, True, "correct")] * 5,
                *[answer(6000, False, "counting_slip")] * 3,
            ),
            "expected_signal": "healthy_struggle",
            "expected_change_tier": "none",
        },
        {
            "name": "impulsive_guessing",
            "why": "Wrong and far faster than the child's own pace, repeatedly.",
            "baseline_ms": BASELINE_MS,
            "events": session(
                8,
                *[event("motion_event", type="micro_jitter")] * 2,
                *[answer(900, False, "counting_slip")] * 5,
                *[answer(3900, True, "correct")] * 3,
            ),
            "expected_signal": "impulsive_guessing",
            "expected_change_tier": "content",
        },
        {
            "name": "working_memory_bottleneck",
            "why": (
                "Right, but repeatedly at twice their usual pace: the arithmetic is "
                "known and the holding of it is what costs."
            ),
            "baseline_ms": BASELINE_MS,
            "events": session(
                7,
                *[event("edit_event", type="after_pause_correction")] * 2,
                *[answer(11000, True, "correct")] * 5,
                *[answer(4200, True, "correct")] * 2,
            ),
            "expected_signal": "working_memory_bottleneck",
            "expected_change_tier": "structural",
        },
        {
            "name": "frustration_with_reported_bug",
            "why": (
                "A reported problem and an abandoned level outrank every other "
                "reading: a bug makes the rest a measurement of the bug."
            ),
            "baseline_ms": BASELINE_MS,
            "reported_problems": 1,
            "events": session(
                5,
                *[event("rage_click")] * 3,
                event("level_abandoned"),
                *[answer(1200, False, "unclassified")] * 4,
            ),
            "expected_signal": "frustration_or_bug",
            "expected_change_tier": "presentation",
        },
        {
            "name": "too_short_to_judge",
            "why": (
                "Two questions is not a session. Guessing a diagnosis from it is "
                "how a child gets their game rewritten for no reason."
            ),
            "baseline_ms": BASELINE_MS,
            "events": session(2, answer(900, False, "counting_slip")),
            "expected_signal": "inconclusive",
            "expected_change_tier": "none",
        },
        {
            "name": "orbiting_but_self_regulating",
            "why": (
                "The same orbiting as the bored fixture, but this child's profile "
                "says movement means focus -- so it is not evidence of boredom."
            ),
            "baseline_ms": BASELINE_MS,
            "restlessness_interpretation": "self_regulation",
            "events": session(
                6,
                *[event("motion_event", type="repetitive_orbit")] * 6,
                *[answer(13000, False, "unclassified")] * 2,
                *[answer(3900, True, "correct")] * 4,
            ),
            "expected_signal": "inconclusive",
            "expected_change_tier": "none",
        },
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fixture in fixtures():
        path = OUT / f"{fixture['name']}.json"
        path.write_text(json.dumps(fixture, indent=2) + "\n")
        print(f"wrote {path.relative_to(OUT.parents[1])}")


if __name__ == "__main__":
    main()
