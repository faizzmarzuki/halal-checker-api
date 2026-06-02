"""Business logic for accounts: register, authenticate, refresh, logout."""
from __future__ import annotations

from datetime import datetime, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tokens
from .models import RefreshToken, User
from .passwords import hash_password, verify_password


class EmailTaken(Exception):
    """Raised when registering an email that already exists."""


class InvalidCredentials(Exception):
    """Raised when email/password do not match."""


class InvalidToken(Exception):
    """Raised when a refresh token is missing, revoked, or undecodable."""


def register(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise EmailTaken()
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(user.password_hash, password):
        raise InvalidCredentials()
    return user


def _store_refresh(db: Session, user_id: int, raw_token: str) -> None:
    payload = tokens.decode_token(raw_token, "refresh")
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=tokens.hash_token(raw_token),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access = tokens.create_access_token(user.id)
    refresh = tokens.create_refresh_token(user.id)
    _store_refresh(db, user.id, refresh)
    return access, refresh


def rotate_refresh(db: Session, raw_token: str) -> tuple[str, str]:
    try:
        payload = tokens.decode_token(raw_token, "refresh")
    except jwt.InvalidTokenError as exc:
        raise InvalidToken() from exc
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(raw_token))
    )
    if row is None or row.revoked:
        raise InvalidToken()
    row.revoked = True  # rotation: the old token can never be used again
    db.commit()
    user_id = int(payload["sub"])
    access = tokens.create_access_token(user_id)
    refresh = tokens.create_refresh_token(user_id)
    _store_refresh(db, user_id, refresh)
    return access, refresh


def logout(db: Session, raw_token: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(raw_token))
    )
    if row is None:
        raise InvalidToken()
    row.revoked = True
    db.commit()
