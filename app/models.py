"""Tables. JSON columns keep the same shape on SQLite and Postgres."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String)


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    age: Mapped[int] = mapped_column(Integer)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    leniency_band: Mapped[str] = mapped_column(String, default="medium")
    restlessness_interpretation: Mapped[str] = mapped_column(String, default="unknown")
    difficulty_floor: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    session_length: Mapped[int] = mapped_column(Integer, default=10)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class IntakeSession(Base):
    __tablename__ = "intake_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SubjectMastery(Base):
    __tablename__ = "subject_mastery"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("child_profiles.id"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String, ForeignKey("skills.id"), primary_key=True
    )
    # The tier the next question comes from. Loop A's ability estimate is not
    # stored: it is replayed from the attempt log (see app/adaptation.py) so the
    # difficulty a child saw is always reproducible from the audit trail.
    difficulty_vector: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decrement_credit: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("child_profiles.id"))
    skill_id: Mapped[str] = mapped_column(String, ForeignKey("skills.id"))
    operands: Mapped[list[int]] = mapped_column(JSON)
    operator: Mapped[str] = mapped_column(String)
    answer_given: Mapped[int] = mapped_column(Integer)
    correct_answer: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    error_class: Mapped[str] = mapped_column(String)
    difficulty_vector_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    tier_key: Mapped[str] = mapped_column(String, index=True)
    latency_to_submit_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class DevelopmentNote(Base):
    __tablename__ = "development_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("child_profiles.id"))
    author: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReportedProblem(Base):
    __tablename__ = "reported_problems"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("child_profiles.id"))
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("child_profiles.id"))
    skill_id: Mapped[str] = mapped_column(String, ForeignKey("skills.id"))
    version: Mapped[int] = mapped_column(Integer)
    code_path: Mapped[str | None] = mapped_column(String, nullable=True)
    devin_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="generating")
    test_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    gate_results: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
