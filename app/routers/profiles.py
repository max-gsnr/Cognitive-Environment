"""Roster, profile detail, teacher edits, notes, and the next question."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, difficulty
from app.db import get_session
from app.models import (
    ChildProfile,
    DevelopmentNote,
    Game,
    ReportedProblem,
    Skill,
    SubjectMastery,
)
from app.schemas import NoteRequest, ProfilePatch, QuestionResponse

router = APIRouter(tags=["profiles"])

PLAIN_LANGUAGE = {
    "single": "numbers up to 9",
    "low_double": "numbers in the teens and twenties",
    "mid_double": "numbers in the thirties to sixties",
    "high_double": "numbers in the seventies to nineties",
    "low_triple": "numbers just over a hundred",
    "mid_triple": "numbers in the hundreds",
    "high_triple": "numbers close to a thousand",
}


def describe(vector: dict[str, Any], skill_id: str) -> str:
    parts = [PLAIN_LANGUAGE.get(vector.get("magnitude", ""), "")]
    if skill_id == difficulty.ADDITION:
        parts.append("with carrying" if vector.get("carries") else "without carrying")
    else:
        parts.append("with borrowing" if vector.get("borrows") else "without borrowing")
        if vector.get("zero_in_minuend"):
            parts.append("including borrowing across a zero")
    return ", ".join(part for part in parts if part)


def profile_dict(profile: ChildProfile) -> dict[str, Any]:
    raw_interests = profile.interests
    if isinstance(raw_interests, str):
        interests_list = [i.strip() for i in raw_interests.split(",") if i.strip()]
    elif isinstance(raw_interests, list):
        interests_list = [str(i).strip() for i in raw_interests if str(i).strip()]
    else:
        interests_list = []

    return {
        "id": profile.id,
        "name": profile.name,
        "age": profile.age,
        "interests": interests_list if interests_list else ["general games"],
        "leniency_band": profile.leniency_band,
        "restlessness_interpretation": profile.restlessness_interpretation,
        "difficulty_floor": profile.difficulty_floor,
        "session_length": profile.session_length,
        "constraints": profile.constraints,
    }


@router.get("/skills")
def list_skills(session: Session = Depends(get_session)) -> list[dict[str, str]]:
    skills = session.scalars(select(Skill)).all()
    return [{"id": skill.id, "label": skill.label} for skill in skills]


@router.get("/profiles")
def list_profiles(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    profiles = session.scalars(select(ChildProfile)).all()
    return [profile_dict(profile) for profile in profiles]


@router.get("/profiles/{profile_id}")
def get_profile(
    profile_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    profile = _require_profile(session, profile_id)

    mastery = session.scalars(
        select(SubjectMastery).where(SubjectMastery.profile_id == profile_id)
    ).all()
    notes = session.scalars(
        select(DevelopmentNote)
        .where(DevelopmentNote.profile_id == profile_id)
        .order_by(DevelopmentNote.created_at.desc())
    ).all()
    problems = session.scalars(
        select(ReportedProblem)
        .where(ReportedProblem.profile_id == profile_id)
        .order_by(ReportedProblem.created_at.desc())
    ).all()
    games = session.scalars(
        select(Game).where(Game.profile_id == profile_id).order_by(Game.version.desc())
    ).all()

    return {
        "profile": profile_dict(profile),
        "mastery": [
            {
                "skill_id": row.skill_id,
                "difficulty_vector": row.difficulty_vector,
                "plain_language": describe(row.difficulty_vector, row.skill_id),
                "updated_at": row.updated_at,
            }
            for row in mastery
        ],
        "development_notes": [
            {
                "id": note.id,
                "author": note.author,
                "note": note.note,
                "created_at": note.created_at,
            }
            for note in notes
        ],
        "reported_problems": [
            {
                "id": problem.id,
                "game_id": problem.game_id,
                "description": problem.description,
                "created_at": problem.created_at,
            }
            for problem in problems
        ],
        "games": [
            {
                "id": game.id,
                "skill_id": game.skill_id,
                "version": game.version,
                "status": game.status,
                "is_live": game.is_live,
                "pr_url": game.pr_url,
                "code_path": game.code_path,
                "gate_results": game.gate_results,
                "test_report": game.test_report,
                "created_at": game.created_at,
            }
            for game in games
        ],
    }


@router.patch("/profiles/{profile_id}")
def patch_profile(
    profile_id: str, body: ProfilePatch, session: Session = Depends(get_session)
) -> dict[str, Any]:
    profile = _require_profile(session, profile_id)

    patch = body.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for field, value in patch.items():
        before = profile_dict(profile)[field]
        if before != value:
            diff[field] = {"before": before, "after": value}

    if "name" in patch:
        profile.name = patch["name"]
    if "age" in patch:
        profile.age = patch["age"]
    if "interests" in patch:
        profile.interests = patch["interests"]
    if "leniency_band" in patch:
        profile.leniency_band = patch["leniency_band"]
    if "restlessness_interpretation" in patch:
        profile.restlessness_interpretation = patch["restlessness_interpretation"]
    if "difficulty_floor" in patch:
        profile.difficulty_floor = patch["difficulty_floor"]
    if "session_length" in patch:
        profile.session_length = patch["session_length"]
    if "constraints" in patch:
        profile.constraints = patch["constraints"]

    if diff:
        audit.record(
            session,
            actor="teacher",
            action="profile_updated",
            payload={"profile_id": profile_id, "diff": diff},
        )
    session.commit()
    return profile_dict(profile)


@router.post("/profiles/{profile_id}/notes")
def add_note(
    profile_id: str, body: NoteRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    _require_profile(session, profile_id)
    note = DevelopmentNote(profile_id=profile_id, author=body.author, note=body.note)
    session.add(note)
    audit.record(
        session,
        actor=body.author,
        action="note_added",
        payload={"profile_id": profile_id, "note": body.note},
    )
    session.commit()
    return {"id": note.id, "created_at": note.created_at}


@router.get(
    "/profiles/{profile_id}/skills/{skill_id}/next-question",
    response_model=QuestionResponse,
)
def next_question(
    profile_id: str, skill_id: str, session: Session = Depends(get_session)
) -> QuestionResponse:
    mastery = session.get(SubjectMastery, (profile_id, skill_id))
    if mastery is None:
        default_vector = {
            "digits": 2 if skill_id == difficulty.ADDITION else 1,
            "magnitude": "low_double" if skill_id == difficulty.ADDITION else "single",
            "carries": False,
            "borrows": False,
            "zero_in_minuend": False,
        }
        mastery = SubjectMastery(
            profile_id=profile_id,
            skill_id=skill_id,
            difficulty_vector=default_vector,
        )
        session.add(mastery)
        session.commit()
    question = difficulty.next_question(mastery.difficulty_vector, skill_id)
    return QuestionResponse(**question)


def _require_profile(session: Session, profile_id: str) -> ChildProfile:
    profile = session.get(ChildProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    return profile
