"""Demo-only: push a canned bad session into PostHog so Devin has real events."""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import get_session
from app.models import Game
from app.schemas import SeedPostHogRequest

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
        action="demo_events_seeded",
        payload={"game_id": game_id, "event_count": len(batch)},
    )
    return len(batch)


@router.post("/demo/seed-posthog")
def seed_posthog(
    body: SeedPostHogRequest, session: Session = Depends(get_session)
) -> dict[str, int]:
    count = seed_posthog_events(session, body.game_id)
    session.commit()
    return {"seeded": count}
