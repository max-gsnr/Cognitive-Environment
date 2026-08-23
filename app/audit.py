"""Every change worth explaining to a teacher gets a row here."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    session: Session, actor: str, action: str, payload: dict[str, Any] | None = None
) -> AuditLog:
    entry = AuditLog(actor=actor, action=action, payload=payload or {})
    session.add(entry)
    return entry
