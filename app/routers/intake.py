"""The branching interview. The only place OpenAI is used."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import audit, difficulty, openai_client, prompts
from app.db import get_session
from app.models import ChildProfile, IntakeSession, SubjectMastery
from app.schemas import IntakeAnswerRequest, IntakeFinalizeRequest, IntakeStartResponse

router = APIRouter(tags=["intake"])

MINIMUM_QUESTIONS = 10

DEFAULT_CONSTRAINTS: dict[str, Any] = {
    "visual": {
        "color_palette": "high_contrast_calm",
        "animations": "minimal_no_screen_shake",
        "particle_effects": False,
    },
    "audio": {"music": False, "sfx": "ui_only"},
    "cognitive": {
        "timer": "disabled",
        "ui_clutter": "single_focal_point",
        "level_length": "micro",
        "reward_frequency": "instant_per_action",
    },
    "emotional": {
        "error_feedback": "gentle_no_red_x",
        "fail_state": "impossible_to_lose",
    },
}


async def _next_question(transcript: list[dict[str, str]]) -> dict[str, Any]:
    prompt = prompts.render(
        prompts.INTAKE_QUESTION_PROMPT,
        conversation_history_json=json.dumps(transcript, indent=2),
    )
    reply = await openai_client.complete_json(prompt)
    if reply.get("complete") and len(transcript) < MINIMUM_QUESTIONS:
        # There is no fallback profile: hold the interview open until it has
        # actually covered enough ground.
        reply = {"complete": False, **reply}
        reply["question"] = reply.get("question") or (
            "What else should I know about how this child works?"
        )
        reply["complete"] = False
    return reply


@router.post("/intake/start", response_model=IntakeStartResponse)
async def start_intake(session: Session = Depends(get_session)) -> IntakeStartResponse:
    intake = IntakeSession(transcript=[], status="in_progress")
    session.add(intake)
    session.commit()

    reply = await _next_question([])
    intake.transcript = [{"question": reply.get("question", "")}]
    session.commit()
    return IntakeStartResponse(
        intake_id=intake.id,
        question=reply.get("question", ""),
        input_type=reply.get("input_type", "text"),
        choices=reply.get("choices"),
    )


@router.post("/intake/{intake_id}/answer", response_model=IntakeStartResponse)
async def answer_intake(
    intake_id: str,
    body: IntakeAnswerRequest,
    session: Session = Depends(get_session),
) -> IntakeStartResponse:
    intake = session.get(IntakeSession, intake_id)
    if intake is None:
        raise HTTPException(404, "intake session not found")

    transcript = list(intake.transcript or [])
    if not transcript or "answer" in transcript[-1]:
        raise HTTPException(409, "no question is waiting for an answer")
    transcript[-1] = {**transcript[-1], "answer": body.answer}

    reply = await _next_question(transcript)
    if reply.get("complete"):
        intake.transcript = transcript
        intake.status = "complete"
        session.commit()
        return IntakeStartResponse(
            intake_id=intake.id, question="", complete=True
        )

    transcript.append({"question": reply.get("question", "")})
    intake.transcript = transcript
    session.commit()
    return IntakeStartResponse(
        intake_id=intake.id,
        question=reply.get("question", ""),
        input_type=reply.get("input_type", "text"),
        choices=reply.get("choices"),
    )


@router.post("/intake/{intake_id}/finalize")
async def finalize_intake(
    intake_id: str,
    body: IntakeFinalizeRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    intake = session.get(IntakeSession, intake_id)
    if intake is None:
        raise HTTPException(404, "intake session not found")

    transcript = [turn for turn in (intake.transcript or []) if "answer" in turn]
    if len(transcript) < MINIMUM_QUESTIONS:
        raise HTTPException(
            409,
            f"the interview needs at least {MINIMUM_QUESTIONS} answered questions; "
            f"it has {len(transcript)}",
        )

    resolved = await openai_client.complete_json(
        prompts.render(
            prompts.INTAKE_RESOLVE_PROMPT,
            conversation_history_json=json.dumps(transcript, indent=2),
        )
    )

    profile = _profile_from_resolved(resolved, body)
    session.add(profile)
    _seed_mastery(session, profile)
    audit.record(
        session,
        actor="system",
        action="profile_created",
        payload={"profile_id": profile.id, "name": profile.name},
    )
    intake.status = "resolved"
    session.commit()
    return {"profile_id": profile.id}


def _profile_from_resolved(
    resolved: dict[str, Any], body: IntakeFinalizeRequest
) -> ChildProfile:
    floor = resolved.get("difficulty_floor") or {}
    return ChildProfile(
        name=body.name,
        age=body.age,
        interests=resolved.get("interests") or [],
        leniency_band=resolved.get("leniency_band") or "medium",
        # "unknown" resolves to "distraction" here, in the backend, rather than
        # being guessed by the model.
        restlessness_interpretation=_restlessness(
            resolved.get("restlessness_interpretation")
        ),
        difficulty_floor={
            "addition": floor.get("addition", "single_digit"),
            "subtraction": floor.get("subtraction", "single_digit"),
        },
        session_length=int(resolved.get("session_length") or 10),
        constraints=resolved.get("constraints") or DEFAULT_CONSTRAINTS,
    )


def _restlessness(value: str | None) -> str:
    return value if value in {"distraction", "self_regulation"} else "distraction"


def _seed_mastery(session: Session, profile: ChildProfile) -> None:
    for skill_id in (difficulty.ADDITION, difficulty.SUBTRACTION):
        floor = difficulty.floor_vector(
            profile.difficulty_floor.get(skill_id, "single_digit")
        )
        session.add(
            SubjectMastery(
                profile_id=profile.id,
                skill_id=skill_id,
                difficulty_vector=floor,
                decrement_credit=0.0,
            )
        )
