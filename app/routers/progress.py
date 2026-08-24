"""The island-map view: a tangible picture of the journey through the topics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import progress
from app.db import get_session
from app.models import Attempt, ChildProfile, Skill, SubjectMastery
from app.routers.profiles import describe

router = APIRouter(tags=["progress"])

RECENT_ATTEMPTS = 20


@router.get("/profiles/{profile_id}/progress-map")
def progress_map(
    profile_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Islands in journey order, with how far across each one the child is."""
    profile = session.get(ChildProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")

    playable = {skill.id for skill in session.scalars(select(Skill)).all()}
    per_skill: dict[str, dict[str, Any]] = {}
    for topic in progress.TOPIC_PATH:
        skill_id = topic["skill_id"]
        mastery = session.get(SubjectMastery, (profile_id, skill_id))
        recent = session.scalars(
            select(Attempt)
            .where(
                Attempt.profile_id == profile_id,
                Attempt.skill_id == skill_id,
            )
            .order_by(Attempt.created_at.desc(), Attempt.id.desc())
            .limit(RECENT_ATTEMPTS)
        ).all()
        streak = 0
        for attempt in recent:  # newest first: the streak is the leading run
            if not attempt.is_correct:
                break
            streak += 1
        per_skill[skill_id] = {
            "vector": mastery.difficulty_vector if mastery else None,
            "recent_accuracy": (
                round(sum(1 for a in recent if a.is_correct) / len(recent), 3)
                if recent
                else None
            ),
            "streak": streak,
            "attempts": len(recent),
            "playable": skill_id in playable,
            "tier_label": (
                describe(mastery.difficulty_vector, skill_id) if mastery else None
            ),
        }

    return {
        "profile_id": profile_id,
        "profile_name": profile.name,
        **progress.build_map(per_skill),
    }
