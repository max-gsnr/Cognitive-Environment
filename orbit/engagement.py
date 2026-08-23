"""Log-based engagement features.

These are behaviour detectors in the sense Baker uses the term: features computed
from interaction logs only — no video, no self-report, no clinical claim. Baker's
gaming-the-system work treats systematic fast guessing and hint-farming as
signals that a learner is exploiting the software rather than thinking, and his
CHI 2007 off-task model detects disengagement from log features alone.

Nothing here diagnoses a child. They are inputs to a fitness function.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .telemetry import HINT_REQUESTED, IDLE_TICK, Trace

#: An answer faster than this, and wrong, cannot have involved computing it.
FAST_GUESS_MS = 1000
#: Gap after which time stops counting as engaged time.
OFF_TASK_MS = 6000


@dataclass(frozen=True)
class Engagement:
    engaged_fraction: float
    fast_guess_rate: float
    hint_rate: float
    off_task_ticks: int
    max_wrong_streak: int
    median_latency_ms: float

    @property
    def gaming_proxy(self) -> float:
        """Bounded 0–1 blend of the two gaming signals."""
        return min(1.0, 0.6 * self.fast_guess_rate + 0.4 * self.hint_rate)


def measure(trace: Trace) -> Engagement:
    attempts = trace.attempts
    if not attempts:
        return Engagement(0.0, 0.0, 0.0, len(trace.of_type(IDLE_TICK)), 0, 0.0)

    fast_guesses = sum(
        1 for a in attempts if not a.correct and a.latency_ms < FAST_GUESS_MS
    )
    # Count both signals: a candidate may drop the explicit hint event while
    # still marking answers as scaffolded, or vice versa.
    hints = max(len(trace.of_type(HINT_REQUESTED)), sum(1 for a in attempts if a.hinted))
    idle = trace.of_type(IDLE_TICK)
    off_task_ms = sum(
        int(event.get("gap_ms", 0))
        for event in idle
        if int(event.get("gap_ms", 0)) >= OFF_TASK_MS
    )

    streak = best = 0
    for attempt in attempts:
        streak = 0 if attempt.correct else streak + 1
        best = max(best, streak)

    duration = max(trace.duration_ms, 1)
    return Engagement(
        engaged_fraction=max(0.0, 1.0 - off_task_ms / duration),
        fast_guess_rate=fast_guesses / len(attempts),
        hint_rate=hints / len(attempts),
        off_task_ticks=len(idle),
        max_wrong_streak=best,
        median_latency_ms=median(a.latency_ms for a in attempts),
    )
