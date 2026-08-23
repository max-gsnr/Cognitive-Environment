from datetime import UTC, datetime, timedelta

from app.evolution import GameRow, evolution_log

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)

PASSING_GATES = {
    "schema": "PASS - matched",
    "assertions": "PASS - 12 assertions",
    "playthrough": "PASS - finished a level",
    "render_accessibility": "PASS - contrast fine",
}

OURS_PASSED = {
    "files": "PASS",
    "shell_contract": "PASS",
    "instrumentation": "PASS",
    "no_fast_flashing": "PASS",
    "focus_visible": "PASS",
    "playthrough": "PASS",
    "passed": True,
}


def row(version: int, **overrides) -> GameRow:
    defaults = dict(
        id=f"game-{version}",
        version=version,
        status="ready",
        is_live=False,
        created_at=NOW - timedelta(hours=version),
        gate_results={**PASSING_GATES, "independent": dict(OURS_PASSED)},
    )
    return GameRow(**{**defaults, **overrides})


def test_versions_are_listed_newest_first():
    log = evolution_log([row(1), row(3), row(2)])
    assert [entry["version"] for entry in log["versions"]] == [3, 2, 1]
    assert [entry["label"] for entry in log["versions"]] == ["v3", "v2", "v1"]


def test_the_signal_that_triggered_a_version_carries_only_its_own_evidence():
    entry = evolution_log(
        [
            row(
                2,
                provenance={
                    "from_version": 1,
                    "telemetry_signals": {
                        "available": True,
                        "dominant_signal": "bored_with_the_game",
                        "change_tier": "presentation",
                        "event_count": 40,
                        "signals": {
                            "idle_ratio": 0.6,
                            "repetitive_orbit": 3,
                            "disengaged_answers": 2,
                            "fast_wrong_ratio": 0.1,
                        },
                    },
                },
                test_report={"change_tier": "presentation", "changes_made": ["a"]},
            )
        ]
    )["versions"][0]

    assert entry["from_version"] == 1
    assert entry["trigger"]["available"] is True
    assert entry["trigger"]["signal_label"] == "Disengaging from the game"
    keys = [item["key"] for item in entry["trigger"]["evidence"]]
    assert keys == ["idle_ratio", "repetitive_orbit", "disengaged_answers"]
    assert entry["permitted_change"]["allowed"] == "presentation"
    assert entry["permitted_change"]["within_scope"] is True


def test_a_version_that_changed_more_than_its_signal_allowed_is_flagged():
    entry = evolution_log(
        [
            row(
                2,
                provenance={
                    "telemetry_signals": {
                        "available": True,
                        "dominant_signal": "bored_with_the_game",
                        "change_tier": "presentation",
                        "signals": {"idle_ratio": 0.6},
                    }
                },
                test_report={"change_tier": "structural"},
            )
        ]
    )["versions"][0]
    assert entry["permitted_change"]["within_scope"] is False


def test_the_diagnosis_is_shown_as_the_whole_rule_ladder():
    """A reader has to be able to recompute it, including the rules that lost."""
    entry = evolution_log(
        [
            row(
                2,
                provenance={
                    "telemetry_signals": {
                        "available": True,
                        "dominant_signal": "bored_with_the_game",
                        "change_tier": "presentation",
                        "signals": {
                            "questions": 12,
                            "rage_clicks": 0,
                            "abandons": 0,
                            "micro_jitter": 0,
                            "after_pause_ratio": 0.5,
                            "idle_ratio": 0.69,
                            "repetitive_orbit": 4,
                            "disengaged_answers": 3,
                            "fast_wrong_ratio": 0.44,
                            "slow_correct_ratio": 0.1,
                        },
                    }
                },
            )
        ]
    )["versions"][0]

    ladder = {rule["signal"]: rule["outcome"] for rule in entry["trigger"]["ladder"]}
    assert ladder["frustration_or_bug"] == "no"
    assert ladder["inconclusive"] == "no"
    assert ladder["healthy_struggle"] == "no"
    assert ladder["bored_with_the_game"] == "fired"
    # Guessing would have held on its own -- priority is why it did not win.
    assert ladder["impulsive_guessing"] == "not_reached"
    assert ladder["working_memory_bottleneck"] == "not_reached"

    fired = [r for r in entry["trigger"]["ladder"] if r["outcome"] == "fired"][0]
    assert [(t["key"], t["met"]) for t in fired["terms"]] == [
        ("idle_ratio", True),
        ("repetitive_orbit", True),
        ("disengaged_answers", True),
    ]
    assert fired["terms"][0]["threshold"] == 0.33
    # And the raw figures are listed too, not only the ones a rule referenced.
    assert {item["key"] for item in entry["trigger"]["measured"]} >= {"questions"}


def test_missing_telemetry_says_so_instead_of_showing_zeroes():
    entry = evolution_log(
        [
            row(
                1,
                provenance={
                    "telemetry_signals": {
                        "available": False,
                        "reason": "POSTHOG_PROJECT_ID is not set",
                    }
                },
            )
        ]
    )["versions"][0]
    assert entry["trigger"]["available"] is False
    assert entry["trigger"]["reason"] == "POSTHOG_PROJECT_ID is not set"
    assert entry["trigger"]["evidence"] == []


def test_a_gate_the_agent_never_reported_counts_as_a_failure():
    gates = {key: value for key, value in PASSING_GATES.items() if key != "playthrough"}
    entry = evolution_log(
        [row(1, gate_results={**gates, "independent": dict(OURS_PASSED)})]
    )["versions"][0]
    missing = [c for c in entry["checks"] if c["name"] == "playthrough"][0]
    assert missing["verdict"] == "fail"
    assert entry["checks_passed"] is False


def test_our_own_check_can_block_a_version_its_author_reported_as_perfect():
    ours = {**OURS_PASSED, "playthrough": "FAIL - stalled on question two"}
    log = evolution_log(
        [
            row(1, is_live=True),
            row(
                2,
                status="gates_failed",
                gate_results={**PASSING_GATES, "independent": ours},
            ),
        ]
    )
    blocked = log["versions"][0]
    assert blocked["state"] == "blocked"
    assert blocked["state_label"] == "Blocked by our checks"
    assert blocked["blocked_by"] == [
        "We played it headless and it answered three questions"
    ]
    assert log["summary"] == {
        "proposed": 2,
        "shipped": 1,
        "blocked": 1,
        "in_progress": 0,
        "live_version": 1,
        "no_change_needed": 0,
        "checked": 2,
        "disagreements": 1,
    }


def test_a_skipped_check_is_neither_a_pass_nor_a_failure():
    ours = {**OURS_PASSED, "playthrough": "SKIP - no browser available"}
    entry = evolution_log(
        [row(1, gate_results={**PASSING_GATES, "independent": ours})]
    )["versions"][0]
    skipped = [c for c in entry["checks"] if c["source"] == "ours" and c["verdict"]]
    assert any(check["verdict"] == "skipped" for check in skipped)
    assert entry["checks_passed"] is True


def test_a_version_still_being_built_is_not_reported_as_shipped():
    log = evolution_log([row(2, status="iterating", gate_results=None)])
    assert log["versions"][0]["state"] == "in_progress"
    assert log["summary"]["shipped"] == 0
    assert log["summary"]["checked"] == 0


def test_healthy_struggle_is_recorded_as_a_deliberate_refusal_to_change():
    log = evolution_log(
        [
            row(
                2,
                provenance={
                    "telemetry_signals": {
                        "available": True,
                        "dominant_signal": "healthy_struggle",
                        "change_tier": "none",
                        "signals": {"micro_jitter": 5, "after_pause_ratio": 0.8},
                    }
                },
            )
        ]
    )
    assert log["summary"]["no_change_needed"] == 1
    assert log["versions"][0]["permitted_change"]["allowed_label"] == (
        "No change permitted"
    )
