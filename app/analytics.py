"""The numbers the dashboards draw. Pure, replayed, and free of model calls.

Two audiences, two questions:

  Session Monitor   "is this child in the right place *right now*?"
  Release Impact    "did shipping v2 of the game actually help?"

Both are computed here rather than in the frontend, and both are *replays*: the
expected success rate plotted against each question is recomputed by re-running
Loop A over the attempt log (app/adaptation.py), not read back from whatever a
UI happened to display at the time. So a chart and the teaching decision it
describes cannot disagree, and any point on it can be defended after the fact.

Metric names are deliberately the ordinary ones --- time on task, completion
rate, recovery time, release impact --- because a teacher and an engineer should
be able to read the same chart without a glossary.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app import ability, adaptation, baseline, difficulty, error_taxonomy
from app.models import Attempt, ChildProfile

Vector = dict[str, Any]

# The band we are trying to keep a child inside. Pure adaptive testing aims at
# .50, which children experience as punishing; .75--.85 is where computer
# adaptive practice samples and where learning is fastest (the "85% rule").
BAND_LOW = 0.75
BAND_HIGH = 0.85

# A gap this long between two answers is a new sitting, not a long think.
SESSION_GAP = timedelta(minutes=20)

# Answered faster than half the child's own pace at that tier, and wrong.
GUESS_FRACTION_OF_PACE = 0.5
GUESS_MS_WITHOUT_PACE = 1500
# Right, but repeatedly taking twice as long as usual: load, not confusion.
LABOURED_FRACTION_OF_PACE = 2.0

# Enough of a session to be worth calling a session at all.
MIN_QUESTIONS_FOR_A_SESSION = 3


@dataclass(frozen=True)
class AttemptRow:
    """The projection of an attempt this module needs. No ORM, no database."""

    created_at: datetime
    vector: Vector
    operands: list[int]
    operator: str
    error_class: str
    is_correct: bool
    latency_ms: int
    tier_key: str
    game_version: int | None = None
    #: A share of the question spent visibly on task, 0..1.
    focus_score: float | None = None
    idle_time_ms: int | None = None
    jitter_ratio: float | None = None


@dataclass(frozen=True)
class Point:
    """One question, as the Session Monitor plots it."""

    index: int
    at: str
    problem: str
    correct: bool
    error_class: str
    # Loop A's own estimate of the child's chance on the question it just posed.
    # This is the y-axis of the challenge-fit chart, and the reason the chart is
    # a claim about difficulty rather than a restatement of the score.
    expected_success: float
    in_band: bool
    rung: int
    tier_label: str
    latency_ms: int
    # Latency as a multiple of this child's own pace at this tier. 1.0 is on
    # pace. Never a comparison against other children.
    pace_index: float | None
    movement: str
    rest_item: bool
    fluency_check: bool
    focus_score: float | None


@dataclass
class SessionMetrics:
    """The Session Monitor, in one payload."""

    points: list[Point] = field(default_factory=list)
    band_low: float = BAND_LOW
    band_high: float = BAND_HIGH
    questions: int = 0
    challenge_fit: float = 0.0
    success_rate: float = 0.0
    on_pace_rate: float = 0.0
    longest_error_run: int = 0
    mean_recovery_questions: float | None = None
    tier_changes: int = 0
    time_on_task_ms: int = 0
    idle_ms: int = 0
    focus_share: float | None = None
    mistake_mix: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [asdict(point) for point in self.points]
        return payload


def session_metrics(
    rows: Sequence[AttemptRow],
    skill_id: str,
    leniency_band: str,
    placement: Vector,
    window: int | None = None,
) -> SessionMetrics:
    """Replay the log, then read the last `window` questions off the replay.

    The replay always starts from the beginning: the expected success rate of the
    fortieth question depends on the thirty-nine before it, so a windowed chart
    still has to fold the whole history to be correct.
    """
    points = _replay_points(rows, skill_id, leniency_band, placement)
    shown = points[-window:] if window else points
    if not shown:
        return SessionMetrics()

    in_band = [p for p in shown if p.in_band]
    correct = [p for p in shown if p.correct]
    paced = [p for p in shown if p.pace_index is not None]
    # "On pace" is the same threshold Loop A treats as slow, so the chart and the
    # adaptation agree about what counts as laboured.
    on_pace = [
        p
        for p in paced
        if p.pace_index and p.pace_index <= baseline.SLOW_MULTIPLIER
    ]
    idle_ms = sum(p for p in (r.idle_time_ms for r in rows[-len(shown) :]) if p)
    solve_ms = sum(p.latency_ms for p in shown)
    focus = [r.focus_score for r in rows[-len(shown) :] if r.focus_score is not None]

    return SessionMetrics(
        points=shown,
        questions=len(shown),
        challenge_fit=round(len(in_band) / len(shown), 3),
        success_rate=round(len(correct) / len(shown), 3),
        on_pace_rate=round(len(on_pace) / len(paced), 3) if paced else 0.0,
        longest_error_run=_longest_error_run(shown),
        mean_recovery_questions=_mean_recovery(shown),
        tier_changes=len([p for p in shown if p.movement != adaptation.HOLD]),
        time_on_task_ms=solve_ms + idle_ms,
        idle_ms=idle_ms,
        focus_share=round(sum(focus) / len(focus), 3) if focus else None,
        mistake_mix=_mistake_mix(shown),
    )


# An unbroken run of questions, each paired with what Loop A believed at the time.
Sitting = list[tuple["AttemptRow", "Point"]]


@dataclass
class VersionMetrics:
    """One game version's behaviour, for the before/after comparison."""

    version: int | None
    label: str
    sessions: int
    questions: int
    questions_per_session: float
    completion_rate: float
    dropoff_rate: float
    challenge_fit: float
    success_rate: float
    guess_rate: float
    laboured_rate: float
    focus_share: float | None
    longest_error_run: float
    first_seen: str | None
    last_seen: str | None


@dataclass
class TimelinePoint:
    """One sitting, for the time series the version marker is drawn on."""

    at: str
    version: int | None
    questions: int
    challenge_fit: float
    success_rate: float
    focus_share: float | None
    completed: bool


def release_impact(
    rows: Sequence[AttemptRow],
    skill_id: str,
    leniency_band: str,
    placement: Vector,
    session_length: int,
) -> dict[str, Any]:
    """Compare the versions of the game this child has actually played.

    A naive before/after comparison is confounded two ways: the child improves
    over time regardless of the release, and the sittings either side may not be
    comparable. Neither is fully removable without an A/B test, which one child
    cannot supply, so instead we (a) hold difficulty out as its own metric --- if
    challenge fit moved, the comparison is not clean and the caveat says so ---
    and (b) return the whole per-sitting timeline so the trend is visible rather
    than hidden inside two averages.
    """
    points = _replay_points(rows, skill_id, leniency_band, placement)
    paired = list(zip(rows, points, strict=True))
    sittings = _sittings(paired)

    versions: list[VersionMetrics] = []
    for version in _versions_in_order(rows):
        member = [s for s in sittings if _version_of(s) == version]
        if member:
            versions.append(_version_metrics(version, member, session_length))

    timeline = [
        TimelinePoint(
            at=sitting[0][0].created_at.isoformat(),
            version=_version_of(sitting),
            questions=len(sitting),
            challenge_fit=_share(sitting, lambda p: p.in_band),
            success_rate=_share(sitting, lambda p: p.correct),
            focus_share=_focus(sitting),
            completed=len(sitting) >= session_length,
        )
        for sitting in sittings
    ]

    return {
        "versions": [asdict(v) for v in versions],
        "timeline": [asdict(t) for t in timeline],
        "band_low": BAND_LOW,
        "band_high": BAND_HIGH,
        "caveats": _caveats(versions, sittings),
    }


def _caveats(versions: list[VersionMetrics], sittings: list[Sitting]) -> list[str]:
    notes: list[str] = []
    if len(versions) < 2:
        notes.append(
            "Only one version has been played, so there is nothing to compare yet."
        )
    if any(v.sessions < 2 for v in versions):
        notes.append(
            "At least one version has a single sitting behind it: read the "
            "timeline, not the averages."
        )
    if len(versions) >= 2:
        drift = abs(versions[-1].challenge_fit - versions[0].challenge_fit)
        if drift > 0.15:
            notes.append(
                "Challenge fit moved by more than 15 points between versions, so "
                "part of any change in engagement is a change in difficulty, not "
                "a change in the game."
            )
        else:
            notes.append(
                "Challenge fit held steady across versions, so the difficulty the "
                "child faced is not what moved --- the game is."
            )
    if len(sittings) < 4:
        notes.append("Fewer than four sittings in total: directional, not conclusive.")
    return notes


def _version_metrics(
    version: int | None, sittings: list[Sitting], session_length: int
) -> VersionMetrics:
    points = [point for sitting in sittings for _row, point in sitting]
    rows = [row for sitting in sittings for row, _point in sitting]
    completed = [s for s in sittings if len(s) >= session_length]
    focus = [r.focus_score for r in rows if r.focus_score is not None]
    guesses = [p for p in points if not p.correct and _is_guess(p)]
    laboured = [
        p
        for p in points
        if p.correct and p.pace_index and p.pace_index >= LABOURED_FRACTION_OF_PACE
    ]
    runs = [_longest_error_run([p for _r, p in s]) for s in sittings]

    return VersionMetrics(
        version=version,
        label="Before" if version is None else f"v{version}",
        sessions=len(sittings),
        questions=len(points),
        questions_per_session=round(len(points) / len(sittings), 2),
        completion_rate=round(len(completed) / len(sittings), 3),
        dropoff_rate=round(1 - len(completed) / len(sittings), 3),
        challenge_fit=round(len([p for p in points if p.in_band]) / len(points), 3),
        success_rate=round(len([p for p in points if p.correct]) / len(points), 3),
        guess_rate=round(len(guesses) / len(points), 3),
        laboured_rate=round(len(laboured) / len(points), 3),
        focus_share=round(sum(focus) / len(focus), 3) if focus else None,
        longest_error_run=round(sum(runs) / len(runs), 2),
        first_seen=min(r.created_at for r in rows).isoformat(),
        last_seen=max(r.created_at for r in rows).isoformat(),
    )


def _is_guess(point: Point) -> bool:
    if point.pace_index is not None:
        return point.pace_index <= GUESS_FRACTION_OF_PACE
    return point.latency_ms < GUESS_MS_WITHOUT_PACE


def _replay_points(
    rows: Sequence[AttemptRow], skill_id: str, leniency_band: str, placement: Vector
) -> list[Point]:
    """Re-run Loop A over the log and record what it believed at every step."""
    if not rows:
        return []
    start = rows[0].vector or placement
    rating = ability.starting_rating(start, skill_id, leniency_band)
    counted = 0
    errors_in_a_row = 0
    pace = _PaceTracker()
    points: list[Point] = []

    for index, row in enumerate(rows):
        vector = row.vector or start
        expected = ability.expected_success(rating, vector, skill_id)
        baseline = pace.baseline(row.tier_key)
        previous = points[-1].rung if points else None
        rung = _rung(vector, skill_id)

        points.append(
            Point(
                index=index + 1,
                at=row.created_at.isoformat(),
                problem=_problem(row),
                correct=row.is_correct,
                error_class=row.error_class,
                expected_success=round(expected, 3),
                in_band=BAND_LOW <= expected <= BAND_HIGH,
                rung=rung,
                tier_label=_tier_label(vector),
                latency_ms=row.latency_ms,
                pace_index=(
                    round(row.latency_ms / baseline, 2) if baseline else None
                ),
                movement=_movement(previous, rung),
                # Both are functions of position in the log, so they can be
                # marked on the chart without being stored per row.
                rest_item=errors_in_a_row >= ability.REST_AFTER_ERRORS,
                fluency_check=bool(counted) and counted % ability.FLUENCY_EVERY == 0,
                focus_score=row.focus_score,
            )
        )

        if row.error_class not in adaptation.NOT_EVIDENCE:
            rating = ability.update_rating(
                rating, vector, skill_id, row.is_correct, counted
            )
            counted += 1
        errors_in_a_row = 0 if row.is_correct else errors_in_a_row + 1
        pace.record(row)

    return points


class _PaceTracker:
    """The child's own pace per tier, accumulated in log order.

    Mirrors app/baseline.py: correct attempts only, and no reading at all until
    there are enough of them, so "on pace" never means "we guessed".
    """

    def __init__(self) -> None:
        self._by_tier: dict[str, list[int]] = {}

    def record(self, row: AttemptRow) -> None:
        if row.is_correct:
            self._by_tier.setdefault(row.tier_key, []).append(row.latency_ms)

    def baseline(self, tier_key: str) -> float | None:
        samples = self._by_tier.get(tier_key, [])
        if len(samples) < 5:
            return None
        return sum(samples) / len(samples)


def _rung(vector: Vector, skill_id: str) -> int:
    return int(ability.tier_rating(vector, skill_id) / ability.RUNG)


def _movement(previous: int | None, rung: int) -> str:
    if previous is None or previous == rung:
        return adaptation.HOLD
    return adaptation.INCREMENT if rung > previous else adaptation.DECREMENT


def _problem(row: AttemptRow) -> str:
    if len(row.operands) < 2:
        return ""
    return f"{row.operands[0]} {row.operator} {row.operands[1]}"


def _tier_label(vector: Vector) -> str:
    flags = [
        vector.get("carries") and "carrying",
        vector.get("borrows") and "borrowing",
        vector.get("zero_in_minuend") and "zeros",
    ]
    named = [flag for flag in flags if flag]
    magnitude = str(vector.get("magnitude", "single")).replace("_", " ")
    digits = vector.get("digits", 1)
    return f"{digits}-digit {magnitude}" + (f", {' + '.join(named)}" if named else "")


def _longest_error_run(points: Sequence[Point]) -> int:
    longest = run = 0
    for point in points:
        run = 0 if point.correct else run + 1
        longest = max(longest, run)
    return longest


def _mean_recovery(points: Sequence[Point]) -> float | None:
    """Questions from a wrong answer to the next right one --- time to recovery.

    The metric an ADHD learner's session actually turns on: a child who recovers
    in one question is still playing, and a child who needs four has left.
    """
    gaps: list[int] = []
    pending: int | None = None
    for point in points:
        if point.correct:
            if pending is not None:
                gaps.append(point.index - pending)
                pending = None
        elif pending is None:
            pending = point.index
    return round(sum(gaps) / len(gaps), 2) if gaps else None


def _mistake_mix(points: Sequence[Point]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for point in points:
        if point.correct:
            continue
        counts[point.error_class] = counts.get(point.error_class, 0) + 1
    return [
        {"error_class": name, "label": _mistake_label(name), "count": count}
        for name, count in sorted(counts.items(), key=lambda item: -item[1])
    ]


MISTAKE_LABELS = {
    error_taxonomy.BORROW_OMITTED: "Forgot to borrow",
    error_taxonomy.BORROW_ACROSS_ZERO: "Borrowing across a zero",
    error_taxonomy.CARRY_OMITTED: "Forgot to carry",
    error_taxonomy.PLACE_VALUE_MISALIGNMENT: "Columns lined up wrong",
    error_taxonomy.OPERATOR_CONFUSION: "Read the sign the other way",
    error_taxonomy.COUNTING_SLIP: "Counting slip",
    error_taxonomy.UNCLASSIFIED: "No recognisable working",
}


def _mistake_label(error_class: str) -> str:
    return MISTAKE_LABELS.get(error_class, error_class.replace("_", " "))


def _sittings(paired: Sitting) -> list[Sitting]:
    """Split the log into sittings on a 20-minute gap, dropping trivial ones."""
    groups: list[list[Any]] = []
    for row, point in paired:
        if groups and row.created_at - groups[-1][-1][0].created_at <= SESSION_GAP:
            groups[-1].append((row, point))
        else:
            groups.append([(row, point)])
    return [g for g in groups if len(g) >= MIN_QUESTIONS_FOR_A_SESSION]


def _version_of(sitting: Sitting) -> int | None:
    versions = [row.game_version for row, _point in sitting if row.game_version]
    return max(versions) if versions else None


def _versions_in_order(rows: Sequence[AttemptRow]) -> list[int | None]:
    seen: list[int | None] = []
    for row in rows:
        version = row.game_version
        if version not in seen:
            seen.append(version)
    return sorted(seen, key=lambda v: (v is not None, v or 0))


def _share(sitting: Sitting, predicate: Callable[[Point], bool]) -> float:
    points = [point for _row, point in sitting]
    return round(len([p for p in points if predicate(p)]) / len(points), 3)


def _focus(sitting: Sitting) -> float | None:
    scores = [row.focus_score for row, _point in sitting if row.focus_score is not None]
    return round(sum(scores) / len(scores), 3) if scores else None


def rows_from_attempts(attempts: Sequence[Attempt]) -> list[AttemptRow]:
    """Adapt ORM rows without letting the ORM into the maths above."""
    return [
        AttemptRow(
            created_at=attempt.created_at,
            vector=attempt.difficulty_vector_snapshot or {},
            operands=attempt.operands or [],
            operator=attempt.operator,
            error_class=attempt.error_class,
            is_correct=attempt.is_correct,
            latency_ms=attempt.latency_to_submit_ms,
            tier_key=attempt.tier_key,
            game_version=attempt.game_version,
            # The game records focus out of 100; the dashboards speak in shares.
            focus_score=(
                attempt.focus_score / 100.0 if attempt.focus_score is not None else None
            ),
            idle_time_ms=attempt.idle_time_ms,
            jitter_ratio=attempt.jitter_ratio,
        )
        for attempt in attempts
    ]


def floor_for(profile: ChildProfile, skill_id: str) -> Vector:
    return difficulty.floor_vector(
        (profile.difficulty_floor or {}).get(skill_id, "single_digit")
    )
