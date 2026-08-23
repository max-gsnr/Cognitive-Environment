"""Demo-only: push a canned bad session into PostHog so Devin has real events."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import audit, difficulty
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
        answer = question["correct_answer"]
        session.add(
            Attempt(
                profile_id=body.profile_id,
                skill_id=body.skill_id,
                operands=question["operands"],
                operator=question["operator"],
                answer_given=answer,
                correct_answer=answer,
                is_correct=True,
                error_class="correct",
                difficulty_vector_snapshot=vector,
                tier_key=tier,
                latency_to_submit_ms=HISTORY_LATENCY_MS + rng.randint(-600, 600),
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
            "tier_key": tier,
        },
    )
    session.commit()
    return {"seeded": HISTORY_ATTEMPTS}


@router.post("/demo/seed-posthog")
def seed_posthog(
    body: SeedPostHogRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    count = seed_posthog_events(session, body.game_id)
    session.commit()
    return {"seeded": count}
