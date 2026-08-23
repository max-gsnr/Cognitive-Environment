"""The child's own recent pace, never a fixed external benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

WINDOW = timedelta(days=3)
MINIMUM_SAMPLE = 5
SLOW_MULTIPLIER = 1.5
DISENGAGED_MULTIPLIER = 3.0


@dataclass(frozen=True)
class LatencySample:
    latency_ms: int
    created_at: datetime


def compute_baseline(
    samples: list[LatencySample], now: datetime | None = None
) -> float | None:
    """Moving average over correct attempts in this tier, inside a 3-day window.

    Returns None below the minimum sample size, which means no latency-based
    movement fires at all --- correctness alone still moves the vector.
    """
    now = now or datetime.now(UTC)
    cutoff = now - WINDOW
    recent = [
        sample.latency_ms for sample in samples if _aware(sample.created_at) >= cutoff
    ]
    if len(recent) < MINIMUM_SAMPLE:
        return None
    return sum(recent) / len(recent)


def is_slow(latency_ms: int, baseline: float | None) -> bool:
    return baseline is not None and latency_ms > SLOW_MULTIPLIER * baseline


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
