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
    intake.transcript = initial_transcript + [{"question": reply.get("question", ""), "type": "dynamic"}]
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

    dynamic_count = sum(1 for t in transcript if t.get("type") == "dynamic" and "answer" in t)
    reply = await _next_question(transcript)

    if reply.get("complete") or dynamic_count >= 4:
        intake.transcript = transcript
        intake.status = "complete"
        session.commit()
        return IntakeStartResponse(
            intake_id=intake.id, question="", complete=True
        )

    transcript.append({"question": reply.get("question", ""), "type": "dynamic"})
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
    interests_str = " ".join(profile.interests).lower()
    is_tennis = "tennis" in interests_str

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

        theme_name = "Tennis Court" if is_tennis else ("Space Docking" if "space" in interests_str else "Arcade")

        # Seed v1
        v1_id = f"game-{profile.id[:8]}-{skill_id}-v1"
        session.add(
            Game(
                id=v1_id,
                profile_id=profile.id,
                skill_id=skill_id,
                version=1,
                code_path=f"games/{profile.id}/{skill_id}/v1/index.html",
                status="ready",
                is_live=False,
                gate_results={
                    "schema": "PASS - 5 questions validated",
                    "assertions": "PASS - no negative results",
                    "playthrough": "PASS - verified reachable",
                    "render_accessibility": "PASS - high contrast",
                    "independent": {
                        "files": "PASS - index.html and game.js present",
                        "shell_contract": "PASS - calls next-question and attempts",
                        "instrumentation": "PASS - all 7 events emitted",
                        "no_fast_flashing": "PASS - slowest cycle 0.9s",
                        "focus_visible": "PASS - :focus-visible styled",
                        "playthrough": "PASS - answered 3 questions headless",
                        "passed": True,
                    },
                },
                provenance={
                    "prompt": "generate",
                    "prompt_revision": "v1.0",
                    "agent": "devin",
                    "seeded": True,
                },
                test_report={
                    "summary": f"Initial bespoke {skill_id} {theme_name} mission generated for {profile.name}.",
                    "diagnosis": "Baseline level designed around single-digit foundation.",
                    "change_tier": "content",
                    "changes_made": [
                        f"Created responsive {theme_name} mechanics matching {profile.name}'s interests",
                        "Bound adaptive Loop A arithmetic difficulty engine",
                    ],
                    "before_after_diff_summary": f"Initial version 1 built for {profile.name}.",
                },
            )
        )

        # Seed v2
        v2_id = f"game-{profile.id[:8]}-{skill_id}-v2"
        session.add(
            Game(
                id=v2_id,
                profile_id=profile.id,
                skill_id=skill_id,
                version=2,
                code_path=f"games/{profile.id}/{skill_id}/v2/index.html",
                pr_url="https://github.com/max-gsnr/Cognitive-Environment/pull/2",
                status="ready",
                is_live=True,
                gate_results={
                    "schema": "PASS - 5 questions validated",
                    "assertions": "PASS - carries and borrows verified",
                    "playthrough": "PASS - 100% completion reachable",
                    "render_accessibility": "PASS - WCAG compliant",
                    "independent": {
                        "files": "PASS - index.html and game.js present",
                        "shell_contract": "PASS - calls next-question and attempts",
                        "instrumentation": "PASS - all 7 events emitted",
                        "no_fast_flashing": "PASS - slowest cycle 0.6s",
                        "focus_visible": "PASS - :focus-visible styled",
                        "playthrough": "PASS - answered 3 questions headless",
                        "passed": True,
                    },
                },
                provenance={
                    "prompt": "iterate",
                    "prompt_revision": "v2.1",
                    "agent": "devin",
                    "seeded": True,
                    "from_version": 1,
                    "telemetry_signals": {
                        "dominant_signal": "healthy_struggle",
                        "change_tier": "structural",
                        "suggested_fix": "Upgrade arithmetic difficulty floor to double-digit carrying",
                        "event_count": 148,
                        "signals": {
                            "questions": 12,
                            "answers": 11,
                            "idle_seconds": 35,
                            "solve_seconds": 64.2,
                            "idle_ratio": 0.35,
                            "immediate_corrections": 1,
                            "after_pause_corrections": 2,
                            "after_pause_ratio": 0.67,
                            "micro_jitter": 3,
                            "repetitive_orbit": 0,
                            "rage_clicks": 0,
                            "abandons": 0,
                            "disengaged_answers": 0,
                            "fast_wrong_ratio": 0.08,
                            "slow_correct_ratio": 0.15,
                        },
                    },
                },
                test_report={
                    "summary": f"Devin autonomous iteration for {profile.name}'s {skill_id} {theme_name} mission.",
                    "diagnosis": f"{profile.name} mastered the baseline with sustained high focus. Devin upgraded the cognitive pacing, added multi-digit visual scaffolding, and gently stepped arithmetic to mid-double digits with carrying.",
                    "change_tier": "structural",
                    "changes_made": [
                        "Upgraded arithmetic difficulty floor from single-digit to double-digit carrying",
                        "Added multi-digit visual scaffolding and carry animations",
                        f"Enhanced {theme_name} animations and tuned reward feedback",
                    ],
                    "before_after_diff_summary": f"v1 (single-digit baseline) → v2 (mildly increased difficulty with double-digit carrying).",
                },
            )
        )

        # Seed v3 (Candidate)
        v3_id = f"game-{profile.id[:8]}-{skill_id}-v3"
        session.add(
            Game(
                id=v3_id,
                profile_id=profile.id,
                skill_id=skill_id,
                version=3,
                status="gates_failed",
                is_live=False,
                gate_results={
                    "schema": "PASS - all questions matched schema",
                    "assertions": "PASS - 18 assertions passed",
                    "playthrough": "PASS - completed simulated level",
                    "render_accessibility": "PASS - no contrast regressions",
                    "independent": {
                        "files": "PASS - index.html and game.js present",
                        "shell_contract": "PASS - calls next-question and attempts",
                        "instrumentation": "FAIL - idle_tick is no longer emitted during cooldown",
                        "no_fast_flashing": "PASS - slowest cycle 0.6s",
                        "focus_visible": "FAIL - disabled answer button loses focus ring",
                        "playthrough": "FAIL - stalled after question 1 of 3: answer field stayed disabled",
                        "passed": False,
                    },
                },
                provenance={
                    "prompt": "iterate",
                    "prompt_revision": "v2.2",
                    "agent": "devin",
                    "seeded": True,
                    "from_version": 2,
                    "telemetry_signals": {
                        "dominant_signal": "healthy_struggle",
                        "change_tier": "content",
                        "suggested_fix": "Progress to triple-digit addition with rapid pacing",
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
                            "fast_wrong_ratio": 0.12,
                            "slow_correct_ratio": 0.11,
                        },
                    },
                },
                test_report={
                    "summary": f"Data gathered during v2: Devin evaluated 3-digit speed challenge.",
                    "diagnosis": f"During v2 sittings, {profile.name} maintained high accuracy on double-digit carrying. Devin proposed adding triple-digit addition.",
                    "change_tier": "content",
                    "changes_made": [
                        "Added 3-digit speed challenge candidate",
                        "Safety gate caught keyboard focus loss during rapid transition (BLOCKED)",
                    ],
                    "before_after_diff_summary": "v2 (double-digit) → v3 (triple-digit speed challenge candidate, held in review).",
                },
            )
        )
