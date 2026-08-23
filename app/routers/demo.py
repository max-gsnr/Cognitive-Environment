"""Demo-only: push a canned bad session into PostHog so Devin has real events."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, difficulty, error_taxonomy, prompts
from app.config import settings
from app.db import get_session
from app.models import Attempt, ChildProfile, Game, SubjectMastery
from app.schemas import SeedHistoryRequest, SeedPostHogRequest

router = APIRouter(tags=["demo"])

# A bored session, not a confused one: long idles, no jitter, an abandoned level.
CANNED_EVENTS: list[tuple[str, dict[str, Any]]] = [
    ("level_started", {}),
    ("problem_shown", {}),
    ("answer_submitted", {"correct": True, "time_to_solve_ms": 2600}),
    ("problem_shown", {}),
    *[("idle_tick", {}) for _ in range(8)],
    (
        "answer_submitted",
        {"correct": False, "time_to_solve_ms": 21000, "error_class": "unclassified"},
    ),
    ("problem_shown", {}),
    *[("idle_tick", {}) for _ in range(10)],
    ("motion_event", {"type": "repetitive_orbit"}),
    (
        "answer_submitted",
        {"correct": False, "time_to_solve_ms": 24500, "error_class": "unclassified"},
    ),
    ("level_abandoned", {"progress_pct": 30}),
]


def seed_posthog_events(session: Session, game_id: str) -> int:
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "game not found")
    if not settings.posthog_project_api_key:
        raise HTTPException(
            503, "POSTHOG_PROJECT_API_KEY is not set; cannot seed demo events."
        )

    common = {
        "game_id": game_id,
        "profile_id": game.profile_id,
        "skill_id": game.skill_id,
        "version": game.version,
        # Seeded events are indistinguishable from played ones otherwise, and the
        # signal summarizer runs over both.
        "is_synthetic": True,
    }
    batch = [
        {
            "event": name,
            "properties": {**common, **properties, "distinct_id": game.profile_id},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        for name, properties in CANNED_EVENTS
    ]

    response = httpx.post(
        f"{settings.posthog_host.rstrip('/')}/batch/",
        json={"api_key": settings.posthog_project_api_key, "batch": batch},
        timeout=30,
    )
    response.raise_for_status()

    audit.record(
        session,
        actor="system",
        action="posthog_seeded",
        payload={"game_id": game_id, "event_count": len(batch)},
    )
    return len(batch)


# Enough correct attempts at the current tier that the latency baseline is real
# (app/baseline.py needs five samples inside three days before pace can move
# anything). Without this the demo's "correct but slow" beat never fires.
HISTORY_ATTEMPTS = 30
HISTORY_LATENCY_MS = 4200
# The history is also ability evidence now, so a flawless past would hand the
# demo child a rating well above the tier intake placed them at and open the
# session two rungs up. Every fifth answer is an off-by-one instead, which is
# the target success rate the policy aims at: the rating lands where it started.
HISTORY_SLIP_EVERY = 5


@router.post("/demo/seed-history")
def seed_history(
    body: SeedHistoryRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    """Give a profile a believable at-pace past so the baseline has samples."""
    profile = session.get(ChildProfile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    mastery = session.get(SubjectMastery, (body.profile_id, body.skill_id))
    if mastery is None:
        raise HTTPException(404, "no mastery row for this profile and skill")

    vector = mastery.difficulty_vector
    tier = difficulty.tier_key(vector)
    rng = random.Random(f"{body.profile_id}:{body.skill_id}")
    now = datetime.now(UTC)

    for index in range(HISTORY_ATTEMPTS):
        question = difficulty.next_question(vector, body.skill_id, rng)
        correct_answer = question["correct_answer"]
        slipped = index % HISTORY_SLIP_EVERY == 0
        answer = correct_answer + 1 if slipped else correct_answer
        session.add(
            Attempt(
                profile_id=body.profile_id,
                skill_id=body.skill_id,
                operands=question["operands"],
                operator=question["operator"],
                answer_given=answer,
                correct_answer=correct_answer,
                is_correct=not slipped,
                error_class=error_taxonomy.classify_attempt(
                    question["operands"], question["operator"], answer
                ),
                difficulty_vector_snapshot=vector,
                tier_key=tier,
                latency_to_submit_ms=HISTORY_LATENCY_MS + rng.randint(-600, 600),
                is_synthetic=True,
                # Spread over the last two days so every row sits inside the
                # baseline's three-day window.
                created_at=now - timedelta(minutes=90 * (HISTORY_ATTEMPTS - index)),
            )
        )

    audit.record(
        session,
        actor="system",
        action="history_seeded",
        payload={
            "profile_id": body.profile_id,
            "skill_id": body.skill_id,
            "attempts": HISTORY_ATTEMPTS,
            "slips": HISTORY_ATTEMPTS // HISTORY_SLIP_EVERY,
            "tier_key": tier,
        },
    )
    session.commit()
    return {"seeded": HISTORY_ATTEMPTS}


# Two versions of the same game, played by the same child at the same difficulty:
# v1 loses them (short sittings, low focus, guessing), v2 holds them. The
# difficulty is deliberately untouched across both, because that is the control
# that makes the comparison mean anything --- if challenge fit moved too, the
# Release Impact view says so instead of taking credit for it.
# wrong_every: one answer in N is wrong, so both versions sit near the 80% the
# policy aims at and Challenge Fit stays flat. A version that suddenly answers
# everything correctly reads as "the difficulty moved", which is the confound
# this view exists to expose, so the seeded data must not fake it.
# wrong_pace: how fast the wrong answers come, as a multiple of the child's own
# pace. Under 1 they are guesses; at 1 they are mistakes.
IMPACT_BLOCKS: list[dict[str, Any]] = [
    {
        "version": 1,
        "sittings": 3,
        "questions": 4,
        "focus": 0.41,
        "wrong_every": 4,
        "wrong_pace": 0.25,
    },
    {
        "version": 2,
        "sittings": 3,
        "questions": 10,
        "focus": 0.83,
        "wrong_every": 5,
        "wrong_pace": 1.0,
    },
]


@router.post("/demo/seed-release-impact")
def seed_release_impact(
    body: SeedHistoryRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    """Seed two versions' worth of sittings so Release Impact has something to show.

    Every row is flagged synthetic, and the dashboard reports the synthetic share
    of what it draws, so a seeded demo cannot be mistaken for evidence.
    """
    profile = session.get(ChildProfile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    mastery = session.get(SubjectMastery, (body.profile_id, body.skill_id))
    if mastery is None:
        raise HTTPException(404, "no mastery row for this profile and skill")

    # Pressing the button twice used to double every sitting.
    for stale in session.scalars(
        select(Attempt).where(
            Attempt.profile_id == body.profile_id,
            Attempt.skill_id == body.skill_id,
            Attempt.is_synthetic.is_(True),
            Attempt.game_version.is_not(None),
        )
    ).all():
        session.delete(stale)

    vector = mastery.difficulty_vector
    tier = difficulty.tier_key(vector)
    rng = random.Random(f"impact:{body.profile_id}:{body.skill_id}")
    now = datetime.now(UTC)
    seeded = 0
    sitting_index = 0
    total_sittings = sum(int(block["sittings"]) for block in IMPACT_BLOCKS)

    for block in IMPACT_BLOCKS:
        focus = float(block["focus"])
        wrong_every = int(block["wrong_every"])
        wrong_pace = float(block["wrong_pace"])
        for _ in range(int(block["sittings"])):
            sitting_index += 1
            start = now - timedelta(hours=6 * (total_sittings - sitting_index + 1))
            for step in range(int(block["questions"])):
                question = difficulty.next_question(vector, body.skill_id, rng)
                correct_answer = question["correct_answer"]
                # Both versions get some answers wrong; only the guessy one gets
                # them wrong *fast*, which is what the guessing rate reads. The
                # slip is off by one so the replay counts it as evidence: an
                # unclassifiable answer teaches Loop A nothing and would let the
                # ability estimate drift away from the tier it was played at.
                wrong = step % wrong_every == wrong_every - 1
                answer = correct_answer + 1 if wrong else correct_answer
                latency = int(HISTORY_LATENCY_MS * (wrong_pace if wrong else 1.0))
                session.add(
                    Attempt(
                        profile_id=body.profile_id,
                        skill_id=body.skill_id,
                        operands=question["operands"],
                        operator=question["operator"],
                        answer_given=answer,
                        correct_answer=correct_answer,
                        is_correct=not wrong,
                        error_class=error_taxonomy.classify_attempt(
                            question["operands"], question["operator"], answer
                        ),
                        difficulty_vector_snapshot=vector,
                        tier_key=tier,
                        latency_to_submit_ms=latency + rng.randint(-300, 300),
                        # Out of 100, the scale the live game posts.
                        focus_score=round(focus * 100 + rng.uniform(-5, 5), 2),
                        idle_time_ms=int(latency * (1.4 - focus)),
                        game_version=int(block["version"]),
                        is_synthetic=True,
                        created_at=start + timedelta(seconds=40 * step),
                    )
                )
                seeded += 1

    audit.record(
        session,
        actor="system",
        action="release_impact_seeded",
        payload={
            "profile_id": body.profile_id,
            "skill_id": body.skill_id,
            "attempts": seeded,
            "versions": [block["version"] for block in IMPACT_BLOCKS],
        },
    )
    session.commit()
    return {"seeded": seeded}


# Three versions of the same game, as Loop B would have produced them without the
# API keys the live path needs: a first build with nothing to read yet, an
# iteration off a disengagement reading that passed both scoreboards, and a
# candidate that reported itself perfect and failed our own re-check. The last one
# is the point of the log --- it never reached the child.
EVOLUTION_BLOCKS: list[dict[str, Any]] = [
    {
        "version": 1,
        "status": "ready",
        "is_live": False,
        "hours_ago": 30,
        "signals": None,
        "report": {
            "summary": "First build from the intake profile: space-themed, one "
            "question per orbit.",
            "change_tier": None,
            "changes_made": [],
        },
        "gates": {
            "schema": "PASS - all 10 question objects matched the backend schema",
            "assertions": "PASS - 14 assertions, 0 failures",
            "playthrough": "PASS - completed a 10-question level",
            "render_accessibility": "PASS - contrast 7.1:1, focus ring visible",
        },
        "independent": {
            "files": "PASS - index.html and game.js present",
            "shell_contract": "PASS - calls next-question and attempts",
            "instrumentation": "PASS - all 7 events emitted",
            "no_fast_flashing": "PASS - slowest cycle 0.9s",
            "focus_visible": "PASS - :focus-visible styled",
            "playthrough": "PASS - answered 3 questions headless",
            "passed": True,
        },
        "prompt": "generate",
    },
    {
        "version": 2,
        "status": "ready",
        "is_live": True,
        "hours_ago": 12,
        "signals": {
            "dominant_signal": "bored_with_the_game",
            "change_tier": "presentation",
            "suggested_fix": "raise reward frequency and tighten pacing",
            "event_count": 148,
            "signals": {
                "questions": 12,
                "answers": 11,
                "idle_seconds": 210,
                "solve_seconds": 96.4,
                "idle_ratio": 0.686,
                "immediate_corrections": 1,
                "after_pause_corrections": 1,
                "after_pause_ratio": 0.5,
                "micro_jitter": 0,
                "repetitive_orbit": 4,
                "rage_clicks": 0,
                "abandons": 0,
                "disengaged_answers": 3,
                "fast_wrong_ratio": 0.09,
                "slow_correct_ratio": 0.18,
            },
        },
        "report": {
            "summary": "Reward every correct answer instead of every third, and cut "
            "the level from 10 questions to 6.",
            "change_tier": "presentation",
            "changes_made": [
                "Reward animation now fires on every correct answer",
                "Level length cut from 10 questions to 6",
                "Idle nudge after 8s of no input",
            ],
            "before_after_diff_summary": "game.js: reward cadence and level length; "
            "no change to question generation.",
        },
        "gates": {
            "schema": "PASS - unchanged, still backend-generated",
            "assertions": "PASS - 16 assertions, 0 failures",
            "playthrough": "PASS - completed a 6-question level",
            "render_accessibility": "PASS - reward animation 0.6s, no flashing",
        },
        "independent": {
            "files": "PASS - index.html and game.js present",
            "shell_contract": "PASS - calls next-question and attempts",
            "instrumentation": "PASS - all 7 events emitted",
            "no_fast_flashing": "PASS - slowest cycle 0.6s",
            "focus_visible": "PASS - :focus-visible styled",
            "playthrough": "PASS - answered 3 questions headless",
            "passed": True,
        },
        "prompt": "iterate",
        "from_version": 1,
    },
    {
        "version": 3,
        "status": "gates_failed",
        "is_live": False,
        "hours_ago": 2,
        "signals": {
            "dominant_signal": "impulsive_guessing",
            "change_tier": "content",
            "suggested_fix": "add a ~2.5s gentle cooldown before the next guess is "
            "accepted",
            "event_count": 96,
            "signals": {
                "questions": 9,
                "answers": 9,
                "idle_seconds": 25,
                "solve_seconds": 41.2,
                "idle_ratio": 0.378,
                "immediate_corrections": 4,
                "after_pause_corrections": 0,
                "after_pause_ratio": 0.0,
                "micro_jitter": 1,
                "repetitive_orbit": 0,
                "rage_clicks": 0,
                "abandons": 0,
                "disengaged_answers": 0,
                "fast_wrong_ratio": 0.44,
                "slow_correct_ratio": 0.11,
            },
        },
        "report": {
            "summary": "Add a 2.5s cooldown between answers so a guess cannot be "
            "fired instantly.",
            "change_tier": "content",
            "changes_made": [
                "2.5s cooldown before the next answer is accepted",
                "Answer button disabled during the cooldown",
            ],
            "before_after_diff_summary": "game.js: input gating only.",
        },
        "gates": {
            "schema": "PASS - all question objects matched the schema",
            "assertions": "PASS - 18 assertions, 0 failures",
            "playthrough": "PASS - completed a 6-question level",
            "render_accessibility": "PASS - no contrast or flashing regressions",
        },
        # The disabled button never re-enabled for keyboard play, so our own
        # headless run stalled on question two. The session's report never saw it.
        "independent": {
            "files": "PASS - index.html and game.js present",
            "shell_contract": "PASS - calls next-question and attempts",
            "instrumentation": "FAIL - idle_tick is no longer emitted during the "
            "cooldown",
            "no_fast_flashing": "PASS - slowest cycle 0.6s",
            "focus_visible": "FAIL - the disabled answer button loses its focus ring",
            "playthrough": "FAIL - stalled after 1 of 3 questions: the answer field "
            "stayed disabled",
            "passed": False,
        },
        "prompt": "iterate",
        "from_version": 2,
    },
]


@router.post("/demo/seed-evolution")
def seed_evolution(
    body: SeedHistoryRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    """Seed the version history the Loop B log reads, for a demo without API keys.

    Every row records the prompt revision it would really have used, and the
    provenance says `seeded`, so the log cannot pass a rehearsal off as a run.
    """
    profile = session.get(ChildProfile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    if session.get(SubjectMastery, (body.profile_id, body.skill_id)) is None:
        raise HTTPException(404, "no mastery row for this profile and skill")

    # This is a button on the teacher page, and the demo students already boot with
    # a seeded lineage (app/db.py). Writing a second one drew every version twice,
    # so an existing lineage is left exactly as it is rather than deleted: one of
    # those rows is the live game the play page loads.
    existing = session.scalars(
        select(Game).where(
            Game.profile_id == body.profile_id, Game.skill_id == body.skill_id
        )
    ).all()
    if any((row.provenance or {}).get("seeded") for row in existing):
        return {"seeded": 0}

    now = datetime.now(UTC)
    seeded = 0
    for block in EVOLUTION_BLOCKS:
        template = (
            prompts.ITERATE_PROMPT
            if block["prompt"] == "iterate"
            else prompts.GENERATE_GAME_PROMPT
        )
        provenance: dict[str, Any] = {
            "prompt": block["prompt"],
            "prompt_revision": prompts.revision(template),
            "agent": "devin",
            "seeded": True,
            "created_at": (
                now - timedelta(hours=int(block["hours_ago"]) + 1)
            ).isoformat(),
        }
        if block.get("from_version") is not None:
            provenance["from_version"] = block["from_version"]
        if block["signals"] is not None:
            provenance["telemetry_signals"] = {
                "available": True,
                **dict(block["signals"]),
            }

        gates = dict(block["gates"])
        gates["independent"] = dict(block["independent"])
        session.add(
            Game(
                profile_id=body.profile_id,
                skill_id=body.skill_id,
                version=int(block["version"]),
                status=str(block["status"]),
                is_live=bool(block["is_live"]),
                code_path=f"games/{body.profile_id}/v{block['version']}",
                devin_session_id=f"devin-seeded-v{block['version']}",
                pr_url=None,
                gate_results=gates,
                test_report=dict(block["report"]),
                provenance=provenance,
                created_at=now - timedelta(hours=int(block["hours_ago"])),
            )
        )
        seeded += 1

    audit.record(
        session,
        actor="system",
        action="evolution_seeded",
        payload={
            "profile_id": body.profile_id,
            "skill_id": body.skill_id,
            "versions": [block["version"] for block in EVOLUTION_BLOCKS],
        },
    )
    session.commit()
    return {"seeded": seeded}


@router.post("/demo/seed-posthog")
def seed_posthog(
    body: SeedPostHogRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    count = seed_posthog_events(session, body.game_id)
    session.commit()
    return {"seeded": count}
