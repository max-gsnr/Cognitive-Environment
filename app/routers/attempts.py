"""POST /attempts --- the real-time path. No network calls to any model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import adaptation, difficulty
from app.baseline import WINDOW, LatencySample, compute_baseline
from app.db import get_session
from app.models import Attempt, ChildProfile, SubjectMastery
from app.schemas import AttemptRequest, AttemptResponse

router = APIRouter(tags=["attempts"])


@router.post("/attempts", response_model=AttemptResponse)
def submit_attempt(
    body: AttemptRequest, session: Session = Depends(get_session)
) -> AttemptResponse:
    profile = session.get(ChildProfile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    mastery = session.get(SubjectMastery, (body.profile_id, body.skill_id))
    if mastery is None:
        raise HTTPException(404, "no mastery row for this profile and skill")

    vector = dict(mastery.difficulty_vector)
    tier = difficulty.tier_key(vector)
    baseline = _baseline_for_tier(session, body.profile_id, body.skill_id, tier)

    a, b = body.operands[0], body.operands[1]
    correct_answer = a + b if body.operator == "+" else a - b
    floor = difficulty.floor_vector(
        (profile.difficulty_floor or {}).get(body.skill_id, "single_digit")
    )

    history = _history(session, body.profile_id, body.skill_id)
    rating, attempts_seen = adaptation.replay(
        history, vector, body.skill_id, profile.leniency_band
    )

    decision = adaptation.next_vector(
        vector=vector,
        skill_id=body.skill_id,
        operands=body.operands,
        operator=body.operator,
        answer_given=body.answer_given,
        latency_ms=body.latency_to_submit_ms,
        baseline=baseline,
        floor=floor,
        leniency_band=profile.leniency_band,
        rating=rating,
        attempts_seen=attempts_seen,
        prior_errors_in_a_row=adaptation.errors_in_a_row(history),
    )
    movement = decision.movement

    session.add(
        Attempt(
            profile_id=body.profile_id,
            skill_id=body.skill_id,
            operands=body.operands,
            operator=body.operator,
            answer_given=body.answer_given,
            correct_answer=correct_answer,
            is_correct=body.answer_given == correct_answer,
            error_class=movement.error_class,
            difficulty_vector_snapshot=vector,
            tier_key=tier,
            latency_to_submit_ms=body.latency_to_submit_ms,
        )
    )
    mastery.difficulty_vector = decision.vector
    session.commit()

    return AttemptResponse(
        is_correct=body.answer_given == correct_answer,
        error_class=movement.error_class,
        updated_difficulty_vector=decision.vector,
        baseline_ms=baseline,
        movement=movement.direction,
        repeat_tier=movement.repeat_tier,
        ability_rating=round(decision.rating, 1),
        expected_success=round(decision.expected_success, 3),
    )


def _history(
    session: Session, profile_id: str, skill_id: str
) -> list[tuple[dict[str, object], str, bool]]:
    """Every prior attempt, oldest first, so the rating is a replay and not state."""
    rows = session.scalars(
        select(Attempt)
        .where(Attempt.profile_id == profile_id, Attempt.skill_id == skill_id)
        .order_by(Attempt.created_at, Attempt.id)
    ).all()
    return [
        (row.difficulty_vector_snapshot, row.error_class, row.is_correct)
        for row in rows
    ]


def _baseline_for_tier(
    session: Session, profile_id: str, skill_id: str, tier: str
) -> float | None:
    cutoff = datetime.now(UTC) - WINDOW - timedelta(seconds=1)
    rows = session.scalars(
        select(Attempt).where(
            Attempt.profile_id == profile_id,
            Attempt.skill_id == skill_id,
            Attempt.tier_key == tier,
            Attempt.is_correct.is_(True),
            Attempt.created_at >= cutoff.replace(tzinfo=None),
        )
    ).all()
    samples = [
        LatencySample(latency_ms=row.latency_to_submit_ms, created_at=row.created_at)
        for row in rows
    ]
    return compute_baseline(samples)
