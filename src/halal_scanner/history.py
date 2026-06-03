"""Per-account scan history: best-effort recording, plus listing and deletion."""
from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth.models import ScanHistory, User

logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 200


class NotFound(Exception):
    """Raised when deleting a scan that is missing or not owned by the user."""


def _summarize(text: str) -> str:
    """Trim and cap the human-readable summary of a scan's input."""
    return text.strip()[:MAX_SUMMARY_LEN]


def record(db: Session, user_id: int, scan_type: str, summary: str, verdict: str) -> None:
    """Append one scan-history row and commit. Best-effort: a failure here must
    never break the scan that triggered it, so errors are swallowed."""
    try:
        db.add(
            ScanHistory(
                user_id=user_id,
                scan_type=scan_type,
                summary=_summarize(summary),
                verdict=verdict,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record scan history for user %s", user_id)


def list_for_user(
    db: Session, user: User, limit: int = 50, offset: int = 0
) -> list[ScanHistory]:
    """Return the user's scans, newest first, paginated."""
    return list(
        db.scalars(
            select(ScanHistory)
            .where(ScanHistory.user_id == user.id)
            .order_by(ScanHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def delete_one(db: Session, user: User, scan_id: int) -> None:
    """Delete one of the user's own scans, or raise NotFound."""
    row = db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id, ScanHistory.user_id == user.id
        )
    )
    if row is None:
        raise NotFound()
    db.delete(row)
    db.commit()


def delete_all(db: Session, user: User) -> int:
    """Delete all of the user's scans; return how many rows were removed."""
    # synchronize_session=False: a one-shot bulk delete in a request handler whose
    # session is discarded right after, so skip the identity-map sync (and avoid
    # leaving stale loaded rows behind in a reused session).
    stmt = delete(ScanHistory).where(ScanHistory.user_id == user.id)
    result = db.execute(stmt.execution_options(synchronize_session=False))
    db.commit()
    return result.rowcount
