"""What the dashboards claim has to survive being checked against the log."""

from __future__ import annotations

from datetime import datetime, timedelta

from app import analytics, difficulty

SKILL = "addition"
START = datetime(2026, 1, 5, 9, 0, 0)


def row(
    index: int,
    *,
    correct: bool = True,
    latency_ms: int = 6000,
    vector: dict | None = None,
    version: int | None = 1,
    focus: float | None = 80.0,
    at: datetime | None = None,
    error_class: str | None = None,
) -> analytics.AttemptRow:
    v = vector or difficulty.base_vector(1)
    return analytics.AttemptRow(
        created_at=at or START + timedelta(seconds=45 * index),
        vector=v,
        operands=[4, 3],
        operator="+",
        error_class=error_class or ("correct" if correct else "counting_slip"),
        is_correct=correct,
        latency_ms=latency_ms,
        tier_key=difficulty.tier_key(v),
        game_version=version,
        focus_score=focus,
        idle_time_ms=500,
    )


def placement() -> dict:
    return difficulty.base_vector(1)


def test_no_attempts_yields_an_empty_dashboard_not_a_crash() -> None:
    metrics = analytics.session_metrics([], SKILL, "medium", placement())
    assert metrics.questions == 0
    assert metrics.points == []
    assert metrics.mean_recovery_questions is None


def test_challenge_fit_counts_questions_inside_the_target_band() -> None:
    metrics = analytics.session_metrics(
        [row(i) for i in range(10)], SKILL, "medium", placement()
    )
    assert metrics.questions == 10
    in_band = [p for p in metrics.points if p.in_band]
    assert metrics.challenge_fit == round(len(in_band) / 10, 3)
    for point in metrics.points:
        assert point.in_band == (0.75 <= point.expected_success <= 0.85)


def test_expected_success_is_replayed_not_stored() -> None:
    """The same log always redraws the same chart, from the log alone."""
    rows = [row(i, correct=i % 3 != 0) for i in range(12)]
    first = analytics.session_metrics(rows, SKILL, "medium", placement())
    second = analytics.session_metrics(rows, SKILL, "medium", placement())
    assert [p.expected_success for p in first.points] == [
        p.expected_success for p in second.points
    ]


def test_a_window_still_folds_the_whole_history() -> None:
    """Question 12 in a 5-question window keeps the rating from all 12."""
    rows = [row(i, correct=True) for i in range(12)]
    full = analytics.session_metrics(rows, SKILL, "medium", placement())
    windowed = analytics.session_metrics(rows, SKILL, "medium", placement(), window=5)
    assert windowed.questions == 5
    assert [p.index for p in windowed.points] == [8, 9, 10, 11, 12]
    assert windowed.points[-1].expected_success == full.points[-1].expected_success


def test_recovery_measures_wrong_answer_to_next_right_one() -> None:
    pattern = [True, False, False, True, True, False, True]
    metrics = analytics.session_metrics(
        [row(i, correct=ok) for i, ok in enumerate(pattern)],
        SKILL,
        "medium",
        placement(),
    )
    # Wrong at 2 recovered at 4 (2 questions), wrong at 6 recovered at 7 (1).
    assert metrics.mean_recovery_questions == 1.5
    assert metrics.longest_error_run == 2


def test_pace_is_silent_until_the_child_has_a_baseline() -> None:
    """No baseline means no pace claim, exactly as Loop A behaves."""
    rows = [row(i) for i in range(8)]
    metrics = analytics.session_metrics(rows, SKILL, "medium", placement())
    assert [p.pace_index for p in metrics.points[:5]] == [None] * 5
    assert metrics.points[5].pace_index == 1.0


def test_mistake_mix_is_ordered_and_plain_language() -> None:
    rows = [
        row(0, correct=False, error_class="carry_omitted"),
        row(1, correct=False, error_class="carry_omitted"),
        row(2, correct=False, error_class="counting_slip"),
        row(3),
    ]
    metrics = analytics.session_metrics(rows, SKILL, "medium", placement())
    assert [m["label"] for m in metrics.mistake_mix] == [
        "Forgot to carry",
        "Counting slip",
    ]
    assert [m["count"] for m in metrics.mistake_mix] == [2, 1]


def _two_version_log() -> list[analytics.AttemptRow]:
    """v1: three short sittings. v2: three full ones, same difficulty."""
    rows: list[analytics.AttemptRow] = []
    at = START
    for version, sittings, length, focus in ((1, 3, 4, 40.0), (2, 3, 10, 85.0)):
        for _ in range(sittings):
            at = at + timedelta(hours=3)
            for step in range(length):
                rows.append(
                    row(
                        step,
                        version=version,
                        focus=focus,
                        at=at + timedelta(seconds=40 * step),
                        correct=step % 4 != 3,
                    )
                )
    return rows


def test_release_impact_separates_versions_into_before_and_after() -> None:
    payload = analytics.release_impact(
        _two_version_log(), SKILL, "medium", placement(), session_length=10
    )
    versions = payload["versions"]
    assert [v["label"] for v in versions] == ["v1", "v2"]
    assert [v["sessions"] for v in versions] == [3, 3]
    assert versions[0]["completion_rate"] == 0.0
    assert versions[1]["completion_rate"] == 1.0
    assert versions[0]["questions_per_session"] < versions[1]["questions_per_session"]
    assert versions[1]["focus_share"] > versions[0]["focus_share"]


def test_release_impact_says_difficulty_did_not_move() -> None:
    payload = analytics.release_impact(
        _two_version_log(), SKILL, "medium", placement(), session_length=10
    )
    joined = " ".join(payload["caveats"])
    assert "the game is" in joined
    assert len(payload["timeline"]) == 6
    assert [t["version"] for t in payload["timeline"]] == [1, 1, 1, 2, 2, 2]


def test_one_version_refuses_to_claim_a_comparison() -> None:
    rows = [row(i, version=1) for i in range(10)]
    payload = analytics.release_impact(
        rows, SKILL, "medium", placement(), session_length=10
    )
    assert len(payload["versions"]) == 1
    assert any("nothing to compare" in note for note in payload["caveats"])


def test_a_twenty_minute_gap_starts_a_new_sitting() -> None:
    rows = [row(i, at=START + timedelta(seconds=40 * i)) for i in range(4)]
    rows += [
        row(i, at=START + timedelta(hours=2) + timedelta(seconds=40 * i))
        for i in range(4)
    ]
    payload = analytics.release_impact(
        rows, SKILL, "medium", placement(), session_length=10
    )
    assert payload["versions"][0]["sessions"] == 2


def test_a_two_question_sitting_is_not_a_sitting() -> None:
    rows = [row(i, at=START + timedelta(seconds=40 * i)) for i in range(2)]
    payload = analytics.release_impact(
        rows, SKILL, "medium", placement(), session_length=10
    )
    assert payload["versions"] == []
