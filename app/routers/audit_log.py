"""The teacher-facing timeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AuditLog

router = APIRouter(tags=["audit"])


@router.get("/audit-log")
def read_audit_log(
    limit: int = 100, session: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    entries = session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": entry.id,
            "actor": entry.actor,
            "action": entry.action,
            "payload": entry.payload,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
