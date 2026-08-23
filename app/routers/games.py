"""Loop B: hand a Devin session the context, then read back a gated PR."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit, devin_client, prompts
from app.config import settings
from app.db import get_session
from app.models import (
    Attempt,
    ChildProfile,
    DevelopmentNote,
    Game,
    ReportedProblem,
    SubjectMastery,
)
from app.routers.demo import seed_posthog_events
from app.routers.profiles import profile_dict
from app.schemas import (
    GenerateGameRequest,
    IterateRequest,
    ReportProblemRequest,
)

router = APIRouter(tags=["games"])

REQUIRED_GATES = ("schema", "assertions", "playthrough", "render_accessibility")
PASSING = {"pass", "passed", "ok", "true", "yes"}

STRUCTURED_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "game_path": {"type": "string"},
        "pr_url": {"type": "string"},
        "commit_sha": {"type": "string"},
        "gate_results": {
            "type": "object",
            "properties": {gate: {"type": "string"} for gate in REQUIRED_GATES},
        },
        "summary": {"type": "string"},
        "diagnosis": {"type": "string"},
        "change_tier": {"type": "string"},
        "changes_made": {"type": "array", "items": {"type": "string"}},
        "before_after_diff_summary": {"type": "string"},
    },
    "required": ["game_path", "gate_results"],
}


def _with_repo(prompt: str) -> str:
    """Name the repo the session works in; the prompts themselves stay verbatim."""
    if not settings.repo_url:
        return prompt
    return f"REPOSITORY: {settings.repo_url} (base branch: main)\n\n{prompt}"


def gates_passed(gate_results: dict[str, Any] | None) -> bool:
    """Every required gate must report a pass. A missing gate is a failure."""
    if not gate_results:
        return False
    for gate in REQUIRED_GATES:
        value = gate_results.get(gate)
        if isinstance(value, bool):
            if not value:
                return False
        elif not isinstance(value, str) or value.strip().lower() not in PASSING:
            return False
    return True


@router.post("/games/generate")
async def generate_game(
    body: GenerateGameRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    profile = session.get(ChildProfile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    mastery = session.get(SubjectMastery, (body.profile_id, body.skill_id))
    if mastery is None:
        raise HTTPException(404, "no mastery row for this profile and skill")

    version = _next_version(session, body.profile_id, body.skill_id)
    game = Game(
        profile_id=body.profile_id,
        skill_id=body.skill_id,
        version=version,
        status="generating",
    )
    session.add(game)
    session.flush()

    prompt = prompts.render(
        prompts.GENERATE_GAME_PROMPT,
        profile_json=_json(profile_dict(profile)),
        skill_label=body.skill_id.capitalize(),
        skill_id=body.skill_id,
        initial_difficulty_vector_json=_json(mastery.difficulty_vector),
        profile_id=body.profile_id,
        top_interest=(profile.interests or ["outer space"])[0],
        game_id=game.id,
        posthog_project_key=settings.posthog_project_api_key,
        posthog_host=settings.posthog_host,
        session_length=profile.session_length,
    )

    created = await devin_client.create_session(
        prompt=_with_repo(prompt),
        tags=["orbit", "generate", body.skill_id],
        structured_output_schema=STRUCTURED_OUTPUT_SCHEMA,
        title=f"Orbit: generate {body.skill_id} v{version} for {profile.name}",
    )
    game.devin_session_id = created.get("session_id")
    audit.record(
        session,
        actor="system",
        action="generation_started",
        payload={"game_id": game.id, "devin_session_id": game.devin_session_id},
    )
    session.commit()
    return {
        "game_id": game.id,
        "devin_session_id": game.devin_session_id,
        "session_url": created.get("url"),
        "status": game.status,
    }


@router.get("/games/{game_id}/status")
async def game_status(
    game_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return await _poll(session, game_id, action="generation_completed")


@router.post("/games/{game_id}/iterate")
async def iterate_game(
    game_id: str, body: IterateRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    current = _require_game(session, game_id)
    profile = session.get(ChildProfile, current.profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    mastery = session.get(SubjectMastery, (current.profile_id, current.skill_id))

    if body.demo_mode:
        seed_posthog_events(session, game_id)

    since = datetime.now(UTC) - timedelta(days=3)
    breakdown = _error_class_breakdown(session, current.profile_id, current.skill_id)
    notes = session.scalars(
        select(DevelopmentNote)
        .where(DevelopmentNote.profile_id == current.profile_id)
        .order_by(DevelopmentNote.created_at.desc())
        .limit(10)
    ).all()
    problems = session.scalars(
        select(ReportedProblem)
        .where(ReportedProblem.profile_id == current.profile_id)
        .order_by(ReportedProblem.created_at.desc())
        .limit(10)
    ).all()

    # The next number in the roster, not current + 1: iterating an older ready
    # version must not collide with a version that already exists.
    new_version = _next_version(session, current.profile_id, current.skill_id)
    prompt = prompts.render(
        prompts.ITERATE_PROMPT,
        profile_json=_json(profile_dict(profile)),
        code_path=current.code_path or "",
        current_version=current.version,
        skill_label=current.skill_id.capitalize(),
        skill_id=current.skill_id,
        current_difficulty_vector_json=_json(
            mastery.difficulty_vector if mastery else {}
        ),
        n=sum(breakdown.values()),
        error_class_breakdown_json=_json(breakdown),
        development_notes_text=_notes_text(notes),
        reported_problems_text=_problems_text(problems),
        posthog_project_id=settings.posthog_project_id,
        posthog_host=settings.posthog_host,
        game_id=game_id,
        profile_id=current.profile_id,
        since_timestamp=since.isoformat(),
        new_version=new_version,
    )

    session_secrets = (
        {"POSTHOG_PERSONAL_API_KEY": settings.posthog_personal_api_key}
        if settings.posthog_personal_api_key
        else None
    )
    created = await devin_client.create_session(
        prompt=_with_repo(prompt),
        tags=["orbit", "iterate", current.skill_id],
        session_secrets=session_secrets,
        structured_output_schema=STRUCTURED_OUTPUT_SCHEMA,
        title=f"Orbit: iterate {current.skill_id} v{new_version} for {profile.name}",
    )

    successor = Game(
        profile_id=current.profile_id,
        skill_id=current.skill_id,
        version=new_version,
        status="iterating",
        devin_session_id=created.get("session_id"),
    )
    session.add(successor)
    audit.record(
        session,
        actor="system",
        action="iteration_started",
        payload={
            "from_game_id": game_id,
            "game_id": successor.id,
            "devin_session_id": successor.devin_session_id,
            "demo_mode": body.demo_mode,
        },
    )
    session.commit()
    return {
        "game_id": successor.id,
        "devin_session_id": successor.devin_session_id,
        "session_url": created.get("url"),
        "status": successor.status,
    }


@router.get("/games/{game_id}/iterate/status")
async def iterate_status(
    game_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return await _poll(session, game_id, action="iteration_completed")


@router.get("/games/{game_id}")
def get_game(game_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    game = _require_game(session, game_id)
    live = session.scalars(
        select(Game).where(
            Game.profile_id == game.profile_id,
            Game.skill_id == game.skill_id,
            Game.is_live.is_(True),
        )
    ).first()
    served = live or game
    return {
        "id": served.id,
        "version": served.version,
        "status": served.status,
        "is_live": served.is_live,
        "static_path": f"/{served.code_path}" if served.code_path else None,
        "pr_url": served.pr_url,
        "gate_results": served.gate_results,
    }


@router.post("/games/{game_id}/report-problem")
def report_problem(
    game_id: str, body: ReportProblemRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    game = _require_game(session, game_id)
    problem = ReportedProblem(
        profile_id=game.profile_id, game_id=game_id, description=body.description
    )
    session.add(problem)
    audit.record(
        session,
        actor="child",
        action="problem_reported",
        payload={"game_id": game_id, "description": body.description},
    )
    session.commit()
    return {"id": problem.id}


@router.post("/games/{game_id}/rollback")
def rollback(game_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Make the requested version the live one. Git history is never touched."""
    game = _require_game(session, game_id)
    if game.status != "ready":
        raise HTTPException(409, "only a version that passed its gates can go live")

    live = session.scalars(
        select(Game).where(
            Game.profile_id == game.profile_id,
            Game.skill_id == game.skill_id,
            Game.is_live.is_(True),
        )
    ).first()

    _set_live(session, game)
    audit.record(
        session,
        actor="teacher",
        action="rollback",
        payload={
            "from_version": live.version if live else None,
            "to_version": game.version,
        },
    )
    session.commit()
    return {"game_id": game.id, "version": game.version, "is_live": True}


async def _poll(session: Session, game_id: str, action: str) -> dict[str, Any]:
    game = _require_game(session, game_id)
    if game.status in {"ready", "gates_failed"} or not game.devin_session_id:
        return _game_state(game)

    remote = await devin_client.get_session(game.devin_session_id)
    output = devin_client.extract_structured_output(remote)
    if not devin_client.is_finished(remote) or output is None:
        return _game_state(game, devin_status=remote.get("status_enum"))

    game.gate_results = output.get("gate_results")
    game.code_path = output.get("game_path") or game.code_path
    game.pr_url = output.get("pr_url") or devin_client.pull_request_url(remote)
    game.test_report = {
        key: output[key]
        for key in (
            "summary",
            "diagnosis",
            "change_tier",
            "changes_made",
            "before_after_diff_summary",
        )
        if key in output
    } or None

    if gates_passed(game.gate_results):
        game.status = "ready"
        _set_live(session, game)
    else:
        # No silent retries: the failure stays visible and nothing goes live.
        game.status = "gates_failed"

    audit.record(
        session,
        actor="devin",
        action=action,
        payload={
            "game_id": game.id,
            "status": game.status,
            "gate_results": game.gate_results,
            "pr_url": game.pr_url,
        },
    )
    session.commit()
    return _game_state(game, devin_status=remote.get("status_enum"))


def _game_state(game: Game, devin_status: str | None = None) -> dict[str, Any]:
    return {
        "game_id": game.id,
        "status": game.status,
        "devin_status": devin_status,
        "devin_session_id": game.devin_session_id,
        "version": game.version,
        "is_live": game.is_live,
        "pr_url": game.pr_url,
        "code_path": game.code_path,
        "gate_results": game.gate_results,
        "test_report": game.test_report,
    }


def _set_live(session: Session, game: Game) -> None:
    siblings = session.scalars(
        select(Game).where(
            Game.profile_id == game.profile_id, Game.skill_id == game.skill_id
        )
    ).all()
    for sibling in siblings:
        sibling.is_live = sibling.id == game.id
    game.is_live = True


def _next_version(session: Session, profile_id: str, skill_id: str) -> int:
    highest = session.scalar(
        select(func.max(Game.version)).where(
            Game.profile_id == profile_id, Game.skill_id == skill_id
        )
    )
    return (highest or 0) + 1


def _error_class_breakdown(
    session: Session, profile_id: str, skill_id: str, limit: int = 50
) -> dict[str, int]:
    rows = session.scalars(
        select(Attempt)
        .where(Attempt.profile_id == profile_id, Attempt.skill_id == skill_id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    ).all()
    breakdown: dict[str, int] = {}
    for row in rows:
        breakdown[row.error_class] = breakdown.get(row.error_class, 0) + 1
    return breakdown


def _notes_text(notes: list[DevelopmentNote]) -> str:
    if not notes:
        return "(none)"
    return "\n".join(f"[{note.author}] {note.note}" for note in notes)


def _problems_text(problems: list[ReportedProblem]) -> str:
    if not problems:
        return "(none)"
    return "\n".join(f"- {problem.description}" for problem in problems)


def _require_game(session: Session, game_id: str) -> Game:
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "game not found")
    return game


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)
