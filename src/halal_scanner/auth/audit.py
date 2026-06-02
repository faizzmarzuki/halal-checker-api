"""Append-only audit log of security-relevant events."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog


def record(db: Session, action: str, user_id: int | None = None, detail: str = "") -> None:
    """Append one audit entry and commit."""
    db.add(AuditLog(action=action, user_id=user_id, detail=detail))
    db.commit()


def list_recent(db: Session, limit: int = 100) -> list[AuditLog]:
    """Return up to ``limit`` audit entries, newest first."""
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))
