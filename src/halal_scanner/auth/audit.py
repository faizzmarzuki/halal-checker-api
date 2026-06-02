"""Append-only audit log of security-relevant events."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog

logger = logging.getLogger(__name__)


def record(db: Session, action: str, user_id: int | None = None, detail: str = "") -> None:
    """Append one audit entry and commit. Best-effort: a logging failure must
    never break the request that triggered it, so errors are swallowed."""
    try:
        db.add(AuditLog(action=action, user_id=user_id, detail=detail))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record audit event %s", action)


def list_recent(db: Session, limit: int = 100) -> list[AuditLog]:
    """Return up to ``limit`` audit entries, newest first."""
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))
