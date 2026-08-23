"""The branching Akinator intake interview powered by OpenAI."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import audit, difficulty, openai_client, prompts
from app.db import get_session
from app.models import ChildProfile, DevelopmentNote, IntakeSession, SubjectMastery
from app.schemas import (
    IntakeAnswerRequest,
    IntakeFinalizeRequest,
    IntakeStartRequest,
    IntakeStartResponse,
)

router = APIRouter(tags=["intake"])

MINIMUM_QUESTIONS = 4

DEFAULT_CONSTRAINTS: dict[str, Any] = {
    "visual": {
        "color_palette": "high_contrast_calm",
        "animations": "standard",
        "particle_effects": True,
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
        reply = {"complete": False, **reply}
        reply["question"] = reply.get("question") or (
            "What visual or sensory accommodations help them focus best during learning?"
        )
        reply["choices"] = [
            "Calm, muted colors with subtle sounds",
            "High contrast visuals with instant feedback",
            "Minimal animation with no screen shake"
        ]
        reply["complete"] = False
    return reply


@router.post("/intake/start", response_model=IntakeStartResponse)
async def start_intake(
    body: IntakeStartRequest | None = None,
    session: Session = Depends(get_session)
) -> IntakeStartResponse:
    initial_transcript: list[dict[str, str]] = []
    
    if body:
        if body.name and body.age:
            initial_transcript.append({
                "question": "What is the child's name and age?",
                "answer": f"Name: {body.name}, Age: {body.age}"
            })
        if body.neurodivergence:
            initial_transcript.append({
                "question": "What is their learning profile / neurodivergence type?",
                "answer": body.neurodivergence
            })
        if body.interests:
            initial_transcript.append({
                "question": "What are the child's top interests and passions?",
                "answer": body.interests
            })

    intake = IntakeSession(transcript=initial_transcript, status="in_progress")
    session.add(intake)
    session.commit()

    reply = await _next_question(initial_transcript)
    intake.transcript = initial_transcript + [{"question": reply.get("question", "")}]
    session.commit()

    return IntakeStartResponse(
        intake_id=intake.id,
        question=reply.get("question", ""),
        input_type=reply.get("input_type", "choice" if reply.get("choices") else "text"),
        choices=reply.get("choices"),
        complete=reply.get("complete", False),
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
    if reply.get("complete") or len(transcript) >= 4:
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
        input_type=reply.get("input_type", "choice" if reply.get("choices") else "text"),
        choices=reply.get("choices"),
        complete=False,
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

    resolved = await openai_client.complete_json(
        prompts.render(
            prompts.INTAKE_RESOLVE_PROMPT,
            conversation_history_json=json.dumps(transcript, indent=2),
        )
    )

    profile = _profile_from_resolved(resolved, body, transcript)
    session.add(profile)
    session.flush()
    _seed_mastery(session, profile)

    # Add initial teacher intake note
    summary_note = f"Initial Intake via AI Akinator: Profile configured for {profile.name} (Age {profile.age}). Interests: {', '.join(profile.interests)}. Leniency: {profile.leniency_band}."
    if body.neurodivergence:
        summary_note += f" Neurodivergence profile: {body.neurodivergence}."
    
    note = DevelopmentNote(profile_id=profile.id, author="teacher", note=summary_note)
    session.add(note)

    audit.record(
        session,
        actor="teacher",
        action="profile_created",
        payload={"profile_id": profile.id, "name": profile.name},
    )
    intake.status = "resolved"
    session.commit()
    return {"profile_id": profile.id}


def _profile_from_resolved(
    resolved: dict[str, Any],
    body: IntakeFinalizeRequest,
    transcript: list[dict[str, str]]
) -> ChildProfile:
    floor = resolved.get("difficulty_floor") or {}
    
    # Extract interests from body or resolved or transcript
    interests = []
    if isinstance(body.interests, list) and body.interests:
        interests = body.interests
    elif isinstance(body.interests, str) and body.interests:
        interests = [i.strip() for i in body.interests.split(",") if i.strip()]
    elif resolved.get("interests"):
        interests = resolved.get("interests")

    if not interests:
        interests = ["outer space", "dinosaurs", "tennis"]

    # Constraints customization
    constraints = resolved.get("constraints") or DEFAULT_CONSTRAINTS

    return ChildProfile(
        name=body.name,
        age=body.age,
        interests=interests[:3],
        leniency_band=resolved.get("leniency_band") or "high",
        restlessness_interpretation=_restlessness(
            resolved.get("restlessness_interpretation")
        ),
        difficulty_floor={
            "addition": floor.get("addition", "single_digit"),
            "subtraction": floor.get("subtraction", "single_digit"),
        },
        session_length=int(resolved.get("session_length") or 10),
        constraints=constraints,
    )


def _restlessness(value: str | None) -> str:
    if value in {"focus", "self_regulation"}:
        return "self_regulation"
    return "distraction"


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
