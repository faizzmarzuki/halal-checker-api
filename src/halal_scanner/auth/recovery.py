"""Email verification and password reset orchestration."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import account_tokens
from .email import emailer
from .models import RefreshToken, User
from .passwords import hash_password


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def request_verification(db: Session, email: str) -> None:
    """Email a verification token. Silent if the user is unknown/already verified."""
    user = _user_by_email(db, email)
    if user is None or user.is_verified:
        return
    token = account_tokens.create_token(db, user.id, "verify")
    emailer.send(email, "Verify your email", f"Your verification token: {token}")


def confirm_verification(db: Session, raw: str) -> None:
    user_id = account_tokens.consume_token(db, raw, "verify")
    user = db.get(User, user_id)
    user.is_verified = True
    db.commit()


def request_reset(db: Session, email: str) -> None:
    """Email a reset token. Silent if the user is unknown (no enumeration)."""
    user = _user_by_email(db, email)
    if user is None:
        return
    token = account_tokens.create_token(db, user.id, "reset")
    emailer.send(email, "Reset your password", f"Your reset token: {token}")


def confirm_reset(db: Session, raw: str, new_password: str) -> None:
    user_id = account_tokens.consume_token(db, raw, "reset")
    user = db.get(User, user_id)
    user.password_hash = hash_password(new_password)
    # Force re-login everywhere: revoke all of the user's refresh tokens.
    for rt in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id)):
        rt.revoked = True
    db.commit()
