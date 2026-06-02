"""API key generation, hashing, and management."""
from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKey, User

_PREFIX = "hsk_"


class KeyNotFound(Exception):
    """Raised when revoking a key that is missing or not owned by the user."""


def generate_key() -> tuple[str, str]:
    """Return (raw_key, prefix). The raw key is shown to the user only once."""
    raw = _PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:10]


def hash_key(raw: str) -> str:
    """SHA-256 hex digest — only the hash is ever stored."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_key(db: Session, user: User, name: str = "") -> tuple[ApiKey, str]:
    raw, prefix = generate_key()
    row = ApiKey(user_id=user.id, name=name, key_hash=hash_key(raw), prefix=prefix)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def list_keys(db: Session, user: User) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).where(ApiKey.user_id == user.id)))


def revoke_key(db: Session, user: User, key_id: int) -> None:
    row = db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    if row is None:
        raise KeyNotFound()
    row.revoked = True
    db.commit()


def verify_key(db: Session, raw: str) -> ApiKey | None:
    """Return the matching, non-revoked key, or None."""
    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    if row is None or row.revoked:
        return None
    return row
