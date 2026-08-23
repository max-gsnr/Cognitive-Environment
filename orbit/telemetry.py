"""Typed view over the game's event stream.

The game emits plain dicts so it stays a single dependency-free HTML file; this
module is the only place that knows their shape, so a change to the game's event
vocabulary breaks in one place instead of five.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

PROBLEM_SHOWN = "problem_shown"
ANSWER_SUBMITTED = "answer_submitted"
HINT_REQUESTED = "hint_requested"
IDLE_TICK = "idle_tick"
LEVEL_COMPLETE = "level_complete"
LEVEL_ABANDONED = "level_abandoned"


@dataclass(frozen=True)
class Attempt:
    """One answered item."""

    skill: str
    difficulty: int
    correct: bool
    latency_ms: int
    hinted: bool
    t_ms: int

    @property
    def credit(self) -> float:
        """Correctness discounted for hint use, mirroring the game's own rule."""
        if not self.correct:
            return 0.0
        return 0.5 if self.hinted else 1.0


@dataclass
class Trace:
    """A single playthrough: its raw events plus the derived attempt list."""

    events: list[dict[str, Any]] = field(default_factory=list)
    seed: int = 0

    @classmethod
    def from_events(cls, events: Iterable[dict[str, Any]], seed: int = 0) -> Trace:
        return cls(events=[dict(event) for event in events], seed=seed)

    def of_type(self, kind: str) -> list[dict[str, Any]]:
        return [event for event in self.events if event.get("type") == kind]

    @property
    def attempts(self) -> list[Attempt]:
        out: list[Attempt] = []
        for event in self.of_type(ANSWER_SUBMITTED):
            out.append(
                Attempt(
                    skill=str(event.get("skill", "unknown")),
                    difficulty=int(event.get("difficulty", 1)),
                    correct=bool(event.get("correct")),
                    latency_ms=int(event.get("latency_ms", 0)),
                    hinted=bool(event.get("hinted")),
                    t_ms=int(event.get("t_ms", 0)),
                )
            )
        return out

    @property
    def duration_ms(self) -> int:
        if not self.events:
            return 0
        return max(int(event.get("t_ms", 0)) for event in self.events)

    @property
    def abandoned(self) -> bool:
        return bool(self.of_type(LEVEL_ABANDONED))

    def success_rate(self) -> float:
        attempts = self.attempts
        if not attempts:
            return 0.0
        return sum(1 for a in attempts if a.correct) / len(attempts)
