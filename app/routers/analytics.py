"""Read-only endpoints behind the dashboards. The maths lives in app/analytics.py."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ability, analytics, evolution
from app.db import get_session
from app.models import Attempt, ChildProfile, Game, SubjectMastery

router = APIRouter(tags=["analytics"])


@router.get("/profiles/{profile_id}/skills/{skill_id}/session-metrics")
def session_metrics(
    profile_id: str,
    skill_id: str,
    window: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """The Session Monitor: is this child in the right place right now?"""
    profile = _profile(session, profile_id)
    rows = analytics.rows_from_attempts(_attempts(session, profile_id, skill_id))
    metrics = analytics.session_metrics(
        rows,
        skill_id,
        profile.leniency_band,
        _placement(session, profile, profile_id, skill_id),
        window=window,
    )
    payload = metrics.as_dict()
    payload["target_success"] = _target(profile.leniency_band)
    payload["session_length"] = profile.session_length
    payload["synthetic_share"] = _synthetic_share(session, profile_id, skill_id)
    return payload


@router.get("/profiles/{profile_id}/skills/{skill_id}/release-impact")
def release_impact(
    profile_id: str, skill_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Release Impact: did shipping the next version of the game actually help?"""
    profile = _profile(session, profile_id)
    attempts = _attempts(session, profile_id, skill_id)
    rows = analytics.rows_from_attempts(attempts)
    payload = analytics.release_impact(
        rows,
        skill_id,
        profile.leniency_band,
        _placement(session, profile, profile_id, skill_id),
        profile.session_length,
    )
    payload["versions"] = [
        {**version, **_provenance(session, profile_id, skill_id, version["version"])}
        for version in payload["versions"]
    ]
    payload["synthetic_share"] = _synthetic_share(session, profile_id, skill_id)
    return payload


@router.get("/profiles/{profile_id}/skills/{skill_id}/evolution")
def evolution_log(
    profile_id: str, skill_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Loop B: which versions were proposed, why, and which ones we refused."""
    _profile(session, profile_id)
    games = session.scalars(
        select(Game)
        .where(Game.profile_id == profile_id, Game.skill_id == skill_id)
        .order_by(Game.version)
    ).all()
    return evolution.evolution_log(
        [
            evolution.GameRow(
                id=game.id,
                version=game.version,
                status=game.status,
                is_live=game.is_live,
                created_at=game.created_at,
                pr_url=game.pr_url,
                devin_session_id=game.devin_session_id,
                gate_results=game.gate_results,
                test_report=game.test_report,
                provenance=game.provenance,
            )
            for game in games
        ]
    )


def _provenance(
    session: Session, profile_id: str, skill_id: str, version: int | None
) -> dict[str, Any]:
    """Why this version exists, straight off the game row --- never re-narrated."""
    if version is None:
        return {"diagnosis": None, "change_tier": None, "changes_made": []}
    game = session.scalars(
        select(Game).where(
            Game.profile_id == profile_id,
            Game.skill_id == skill_id,
            Game.version == version,
        )
    ).first()
    report = (game.test_report or {}) if game else {}
    provenance = (game.provenance or {}) if game else {}
    return {
        "game_id": game.id if game else None,
        "diagnosis": report.get("diagnosis"),
        "change_tier": report.get("change_tier"),
        "changes_made": report.get("changes_made") or [],
        "dominant_signal": (provenance.get("signals") or {}).get("dominant_signal"),
        "pr_url": game.pr_url if game else None,
    }


def _attempts(session: Session, profile_id: str, skill_id: str) -> list[Attempt]:
    return list(
        session.scalars(
            select(Attempt)
            .where(Attempt.profile_id == profile_id, Attempt.skill_id == skill_id)
            .order_by(Attempt.created_at, Attempt.id)
        ).all()
    )


def _synthetic_share(session: Session, profile_id: str, skill_id: str) -> float:
    """How much of what is plotted was seeded. A demo must say that it is one."""
    rows = session.scalars(
        select(Attempt.is_synthetic).where(
            Attempt.profile_id == profile_id, Attempt.skill_id == skill_id
        )
    ).all()
    if not rows:
        return 0.0
    return round(len([row for row in rows if row]) / len(rows), 3)


def _placement(
    session: Session, profile: ChildProfile, profile_id: str, skill_id: str
) -> dict[str, Any]:
    """The tier intake placed this child at, used as the replay's prior."""
    mastery = session.get(SubjectMastery, (profile_id, skill_id))
    if mastery is None:
        raise HTTPException(404, "no mastery row for this profile and skill")
    return analytics.floor_for(profile, skill_id)


def _target(leniency_band: str) -> float:
    return ability.TARGET_SUCCESS.get(leniency_band, ability.DEFAULT_TARGET)


def _profile(session: Session, profile_id: str) -> ChildProfile:
    profile = session.get(ChildProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "profile not found")
    return profile
