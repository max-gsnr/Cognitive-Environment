"""Raw PostHog events in, named behavioural signals out. No model involved.

Loop B's iteration prompt used to ask the Devin session to compute the idle
ratio, the edit ratio and the disengagement check itself, then report which
signal dominated. That made the diagnosis unmeasurable: the same input could
yield a different reading every run, and nothing could be regression-tested.

The arithmetic in that prompt is arithmetic, so it lives here instead --
deterministic, unit-tested, and replayable against recorded fixtures (see
`evals/loop_b/` and `scripts/loop_b_eval.py`). The session still gets the raw
access it had; it now also gets our numbers as ground truth, and its job
narrows to reading them and changing the game.

The signal-to-meaning mapping is the table from the prompt, which follows the
ADHD literature the difficulty policy was built on: stillness plus an
unrecoverable answer on easy material is disengagement, while jitter plus
after-pause self-correction is effortful engagement and must not be "fixed"
(Kofler et al., working memory and ADHD, 10.1080/17470210600762447), and
repeated slow-but-correct answers point at a working-memory bottleneck rather
than a knowledge gap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

IDLE_TICK_SECONDS = 5

# A tick is 5s of no input, so a third of the session spent idle is a lot.
HIGH_IDLE_RATIO = 0.33
# Below this, "still" is not a reading -- there is not enough session to judge.
MIN_QUESTIONS = 3
# Guessing: wrong, and answered faster than half the child's usual pace.
FAST_FRACTION_OF_BASELINE = 0.5
FAST_MS_WITHOUT_BASELINE = 1500
HIGH_FAST_WRONG_RATIO = 0.4
# Working memory: right, but repeatedly taking twice as long as usual.
SLOW_FRACTION_OF_BASELINE = 2.0
HIGH_SLOW_CORRECT_RATIO = 0.4
# The disengagement check from the prompt: 3x baseline on an unclassifiable answer.
DISENGAGED_LATENCY_MULTIPLE = 3.0
# Working hard: jitter and pauses before self-correcting, rather than stillness.
HIGH_JITTER = 3
HIGH_AFTER_PAUSE_RATIO = 0.5

# Signals, and the change tier each one calls for.
FRUSTRATION = "frustration_or_bug"
HEALTHY_STRUGGLE = "healthy_struggle"
BORED = "bored_with_the_game"
IMPULSIVE = "impulsive_guessing"
WORKING_MEMORY = "working_memory_bottleneck"
INCONCLUSIVE = "inconclusive"

CHANGE_TIER = {
    FRUSTRATION: "presentation",
    HEALTHY_STRUGGLE: "none",
    BORED: "presentation",
    IMPULSIVE: "content",
    WORKING_MEMORY: "structural",
    INCONCLUSIVE: "none",
}

FIX = {
    FRUSTRATION: "fix the reported bug first, then remove remaining fail-state UI "
    "and shorten the level",
    HEALTHY_STRUGGLE: "change nothing -- this is effortful engagement, not failure",
    BORED: "raise reward frequency and tighten pacing",
    IMPULSIVE: "add a ~2.5s gentle cooldown before the next guess is accepted",
    WORKING_MEMORY: "add a visual scaffold: countable draggable objects instead "
    "of typed digits",
    INCONCLUSIVE: "collect another session before changing the game",
}


@dataclass(frozen=True)
class Signals:
    """What the session did, in numbers. Every field is derived, none inferred."""

    questions: int
    answers: int
    idle_seconds: int
    solve_seconds: float
    idle_ratio: float
    immediate_corrections: int
    after_pause_corrections: int
    after_pause_ratio: float
    micro_jitter: int
    repetitive_orbit: int
    rage_clicks: int
    abandons: int
    disengaged_answers: int
    fast_wrong_ratio: float
    slow_correct_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize(
    events: list[dict[str, Any]],
    baseline_ms: float | None = None,
    at_or_below_mastered: bool = True,
) -> Signals:
    """Fold a session's events into the signals the iteration prompt reasons over.

    `baseline_ms` is the child's usual pace at this tier (app/baseline.py). Without
    it, "fast" and "slow" fall back to fixed thresholds rather than silently
    reading every answer as on-pace.
    """
    counts = _counts(events)
    answers = _answers(events)

    idle_seconds = counts.get("idle_tick", 0) * IDLE_TICK_SECONDS
    solve_seconds = sum(_ms(a) for a in answers) / 1000
    on_task = idle_seconds + solve_seconds

    immediate, after_pause = _edits(events)
    edits = immediate + after_pause

    fast_cutoff = (
        baseline_ms * FAST_FRACTION_OF_BASELINE
        if baseline_ms
        else FAST_MS_WITHOUT_BASELINE
    )
    slow_cutoff = baseline_ms * SLOW_FRACTION_OF_BASELINE if baseline_ms else None
    wrong = [a for a in answers if not a.get("correct")]
    right = [a for a in answers if a.get("correct")]

    return Signals(
        questions=counts.get("problem_shown", 0),
        answers=len(answers),
        idle_seconds=idle_seconds,
        solve_seconds=round(solve_seconds, 1),
        idle_ratio=round(idle_seconds / on_task, 3) if on_task else 0.0,
        immediate_corrections=immediate,
        after_pause_corrections=after_pause,
        after_pause_ratio=round(after_pause / edits, 3) if edits else 0.0,
        micro_jitter=_motion(events, "micro_jitter"),
        repetitive_orbit=_motion(events, "repetitive_orbit"),
        rage_clicks=counts.get("rage_click", 0) + counts.get("$rageclick", 0),
        abandons=counts.get("level_abandoned", 0),
        disengaged_answers=_disengaged(events, baseline_ms, at_or_below_mastered),
        fast_wrong_ratio=(
            round(len([a for a in wrong if _ms(a) < fast_cutoff]) / len(answers), 3)
            if answers
            else 0.0
        ),
        slow_correct_ratio=(
            round(
                len([a for a in right if slow_cutoff and _ms(a) > slow_cutoff])
                / len(answers),
                3,
            )
            if answers
            else 0.0
        ),
    )


def dominant(
    signals: Signals,
    reported_problems: int = 0,
    restlessness_interpretation: str = "unknown",
) -> str:
    """Name the one signal the iteration should act on, in priority order.

    Frustration outranks everything because a bug makes every other signal a
    measurement of the bug. Effortful engagement is checked next, so that a child
    who is working hard is never "helped" by weakening the game.
    """
    if reported_problems or signals.rage_clicks or signals.abandons:
        return FRUSTRATION

    if signals.questions < MIN_QUESTIONS:
        return INCONCLUSIVE

    if (
        signals.micro_jitter >= HIGH_JITTER
        and signals.after_pause_ratio >= HIGH_AFTER_PAUSE_RATIO
    ):
        return HEALTHY_STRUGGLE

    # Orbiting is disengagement or self-soothing depending on the child; when the
    # profile reads it as self-regulation it is not evidence of boredom.
    orbiting = (
        signals.repetitive_orbit > 0
        and restlessness_interpretation != "self_regulation"
    )
    still = signals.idle_ratio >= HIGH_IDLE_RATIO or orbiting
    if still and signals.disengaged_answers:
        return BORED

    if signals.fast_wrong_ratio >= HIGH_FAST_WRONG_RATIO:
        return IMPULSIVE

    if signals.slow_correct_ratio >= HIGH_SLOW_CORRECT_RATIO:
        return WORKING_MEMORY

    return INCONCLUSIVE


def report(
    events: list[dict[str, Any]],
    baseline_ms: float | None = None,
    reported_problems: int = 0,
    restlessness_interpretation: str = "unknown",
    at_or_below_mastered: bool = True,
) -> dict[str, Any]:
    """The whole read on a session, ready to drop into the prompt or an eval."""
    signals = summarize(
        events,
        baseline_ms=baseline_ms,
        at_or_below_mastered=at_or_below_mastered,
    )
    name = dominant(
        signals,
        reported_problems=reported_problems,
        restlessness_interpretation=restlessness_interpretation,
    )
    return {
        "signals": signals.as_dict(),
        "dominant_signal": name,
        "change_tier": CHANGE_TIER[name],
        "suggested_fix": FIX[name],
        "baseline_ms": baseline_ms,
    }


def _counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        name = str(event.get("event", ""))
        counts[name] = counts.get(name, 0) + 1
    return counts


def _answers(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event.get("properties") or {}
        for event in events
        if event.get("event") == "answer_submitted"
    ]


def _edits(events: list[dict[str, Any]]) -> tuple[int, int]:
    immediate = after_pause = 0
    for event in events:
        if event.get("event") != "edit_event":
            continue
        kind = (event.get("properties") or {}).get("type")
        if kind == "immediate_correction":
            immediate += 1
        elif kind == "after_pause_correction":
            after_pause += 1
    return immediate, after_pause


def _motion(events: list[dict[str, Any]], kind: str) -> int:
    return len(
        [
            event
            for event in events
            if event.get("event") == "motion_event"
            and (event.get("properties") or {}).get("type") == kind
        ]
    )


def _disengaged(
    events: list[dict[str, Any]],
    baseline_ms: float | None,
    at_or_below_mastered: bool,
) -> int:
    """The prompt's per-question check: unclassifiable, very slow, and still.

    A confused child jitters and edits after a pause. A bored child goes still,
    so jitter anywhere in the session disqualifies the reading.
    """
    if baseline_ms is None or not at_or_below_mastered:
        return 0
    if _motion(events, "micro_jitter"):
        return 0
    cutoff = baseline_ms * DISENGAGED_LATENCY_MULTIPLE
    return len(
        [
            answer
            for answer in _answers(events)
            if not answer.get("correct")
            and answer.get("error_class") == "unclassified"
            and _ms(answer) > cutoff
        ]
    )


def _ms(answer: dict[str, Any]) -> float:
    value = answer.get("time_to_solve_ms") or answer.get("latency_to_submit_ms") or 0
    return float(value)
