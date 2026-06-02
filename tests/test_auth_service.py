import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401  (register tables)
from halal_scanner.auth import service


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_register_creates_user(db):
    user = service.register(db, "a@b.com", "password1")
    assert user.id is not None
    assert user.email == "a@b.com"
    assert user.password_hash != "password1"


def test_register_duplicate_email_raises(db):
    service.register(db, "a@b.com", "password1")
    with pytest.raises(service.EmailTaken):
        service.register(db, "a@b.com", "password2")


def test_authenticate_success_and_failure(db):
    service.register(db, "a@b.com", "password1")
    assert service.authenticate(db, "a@b.com", "password1").email == "a@b.com"
    with pytest.raises(service.InvalidCredentials):
        service.authenticate(db, "a@b.com", "wrongpass")
    with pytest.raises(service.InvalidCredentials):
        service.authenticate(db, "nobody@b.com", "password1")


def test_issue_and_rotate_refresh(db):
    user = service.register(db, "a@b.com", "password1")
    _, refresh = service.issue_tokens(db, user)
    access2, refresh2 = service.rotate_refresh(db, refresh)
    assert access2 and refresh2 != refresh
    # old refresh token is now revoked -> reuse fails
    with pytest.raises(service.InvalidToken):
        service.rotate_refresh(db, refresh)


def test_logout_revokes_refresh(db):
    user = service.register(db, "a@b.com", "password1")
    _, refresh = service.issue_tokens(db, user)
    service.logout(db, refresh)
    with pytest.raises(service.InvalidToken):
        service.rotate_refresh(db, refresh)


def test_logout_unknown_token_raises(db):
    with pytest.raises(service.InvalidToken):
        service.logout(db, "not-a-real-token")
