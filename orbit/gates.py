"""Model-independent gates. A candidate that fails one is rejected regardless of score.

These exist because a fitness function is an optimiser's target, not a safety
argument: the score can always be gamed, so the things that must never happen to
a child are checked separately and are not weighted against anything.

Two of them are checked statically against the candidate's source (flashing
faster than 3 Hz, countdown timers, which pair badly with the executive-function
load this population is already carrying); the rest come from the rollouts.
"""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .rollout import RolloutResult

#: Any animation faster than this is a photosensitivity risk.
MIN_FLASH_INTERVAL_MS = 334  # 3 Hz
COUNTDOWN_PATTERN = re.compile(
    r"(countdown|time_?limit|timeLeft|secondsLeft|time_?remaining)", re.IGNORECASE
)
INTERVAL_PATTERN = re.compile(r"set(?:Interval|Timeout)\s*\(\s*[^,]+,\s*(\d+)")
COMMENT_PATTERNS = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"/\*.*?\*/", re.DOTALL),
    re.compile(r"(?m)(?<![:/])//[^\n]*"),
)


@dataclass(frozen=True)
class GateReport:
    passed: bool
    failures: list[str]

    def __bool__(self) -> bool:  # lets callers write `if report:`
        return self.passed


def read_candidate(candidate: str | Path) -> str:
    """Source of a candidate given either a path or a deployed URL."""
    text = str(candidate)
    if text.startswith(("http://", "https://")):
        with urllib.request.urlopen(text, timeout=30) as response:  # noqa: S310 - our own URL
            return response.read().decode("utf-8", "replace")
    if text.startswith("file://"):
        return Path(text[len("file://") :]).read_text(encoding="utf-8")
    return Path(text).read_text(encoding="utf-8")


def executable_source(source: str) -> str:
    """Source with comments removed.

    The gates scan for banned mechanics by name, and this file documents those
    same bans in prose, so a candidate that merely *explains* why it has no
    countdown must not be rejected for saying the word.
    """
    for pattern in COMMENT_PATTERNS:
        source = pattern.sub(" ", source)
    return source


def check_source(path: str | Path) -> list[str]:
    source = executable_source(read_candidate(path))
    failures: list[str] = []

    for match in INTERVAL_PATTERN.finditer(source):
        interval = int(match.group(1))
        if 0 < interval < MIN_FLASH_INTERVAL_MS:
            failures.append(
                f"timer fires every {interval}ms (>3 Hz animation risk)"
            )
            break

    if COUNTDOWN_PATTERN.search(source):
        failures.append("countdown timer detected")
    if "window.orbit" not in source:
        failures.append("evaluation contract missing from source")
    return failures


def check_rollouts(results: Sequence[RolloutResult], *, min_attempts: int = 5) -> list[str]:
    failures: list[str] = []
    if not results:
        return ["no rollouts produced"]

    for result in results:
        if result.console_errors:
            failures.append(
                f"javascript error during {result.profile}: {result.console_errors[0]}"
            )
            break

    completions = sum(
        1 for result in results if len(result.trace.attempts) >= min_attempts
    )
    if completions < len(results):
        failures.append(
            f"only {completions}/{len(results)} rollouts reached {min_attempts} items"
        )
    if all(result.trace.abandoned for result in results):
        failures.append("every simulated learner abandoned the session")
    return failures


def evaluate(path: str | Path, results: Sequence[RolloutResult]) -> GateReport:
    failures = check_source(path) + check_rollouts(results)
    return GateReport(passed=not failures, failures=failures)
