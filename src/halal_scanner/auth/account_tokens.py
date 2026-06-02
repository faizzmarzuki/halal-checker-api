"""Single-use, hashed, expiring tokens for verification and password reset."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AccountToken

_TTL = {"verify": 86400, "reset": 3600}  # seconds: 24h verify, 1h reset


class AccountTokenError(Exception):
    """Raised when a token is missing, wrong-purpose, already used, or expired."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_token(db: Session, user_id: int, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(
        AccountToken(
            user_id=user_id,
            token_hash=_hash(raw),
            purpose=purpose,
            expires_at=now + timedelta(seconds=_TTL[purpose]),
        )
    )
    db.commit()
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> int:
    """Validate and mark a token used; return its user_id, or raise."""
    row = db.scalar(select(AccountToken).where(AccountToken.token_hash == _hash(raw)))
    if row is None or row.used or row.purpose != purpose:
        raise AccountTokenError()
    # SQLite returns naive datetimes; normalize to aware UTC before comparing.
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise AccountTokenError()
    row.used = True
    db.commit()
    return row.user_id
