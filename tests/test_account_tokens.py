import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth import account_tokens as at
from halal_scanner.auth.models import AccountToken, User


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db):
    u = User(email="a@b.com", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_create_then_consume_returns_user_id_and_marks_used(db):
    user = _user(db)
    raw = at.create_token(db, user.id, "verify")
    assert at.consume_token(db, raw, "verify") == user.id
    with pytest.raises(at.AccountTokenError):
        at.consume_token(db, raw, "verify")


def test_wrong_purpose_rejected(db):
    user = _user(db)
    raw = at.create_token(db, user.id, "verify")
    with pytest.raises(at.AccountTokenError):
        at.consume_token(db, raw, "reset")


def test_unknown_token_rejected(db):
    with pytest.raises(at.AccountTokenError):
        at.consume_token(db, "nope", "verify")


def test_expired_token_rejected(db):
    user = _user(db)
    raw = at.create_token(db, user.id, "reset")
    row = db.scalar(select(AccountToken).where(AccountToken.user_id == user.id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(at.AccountTokenError):
        at.consume_token(db, raw, "reset")
