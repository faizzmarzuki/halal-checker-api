import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth import account_tokens, recovery
from halal_scanner.auth.email import emailer
from halal_scanner.auth.models import RefreshToken, User
from halal_scanner.auth.passwords import hash_password, verify_password


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    emailer.outbox.clear()
    yield session
    session.close()


def _user(db, email="a@b.com", pw="password1"):
    u = User(email=email, password_hash=hash_password(pw))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_request_verification_sends_for_real_unverified_user(db):
    _user(db)
    recovery.request_verification(db, "a@b.com")
    assert len(emailer.outbox) == 1
    assert emailer.outbox[0].to == "a@b.com"


def test_request_verification_silent_for_unknown_email(db):
    recovery.request_verification(db, "nobody@b.com")
    assert emailer.outbox == []


def test_confirm_verification_sets_is_verified(db):
    user = _user(db)
    token = account_tokens.create_token(db, user.id, "verify")
    recovery.confirm_verification(db, token)
    db.refresh(user)
    assert user.is_verified is True


def test_request_reset_sends_for_real_user(db):
    _user(db)
    recovery.request_reset(db, "a@b.com")
    assert len(emailer.outbox) == 1


def test_confirm_reset_changes_password_and_revokes_refresh(db):
    user = _user(db, pw="oldpassword")
    rt = RefreshToken(user_id=user.id, token_hash="h", expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    db.add(rt)
    db.commit()
    token = account_tokens.create_token(db, user.id, "reset")
    recovery.confirm_reset(db, token, "newpassword1")
    db.refresh(user)
    assert verify_password(user.password_hash, "newpassword1") is True
    revoked = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert revoked.revoked is True


def test_confirm_reset_bad_token_raises(db):
    with pytest.raises(account_tokens.AccountTokenError):
        recovery.confirm_reset(db, "bogus", "newpassword1")
