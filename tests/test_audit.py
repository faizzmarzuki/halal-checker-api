import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth import audit


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_record_inserts_row(db):
    audit.record(db, "auth.login", user_id=1, detail="a@b.com")
    rows = audit.list_recent(db)
    assert len(rows) == 1
    assert rows[0].action == "auth.login"
    assert rows[0].user_id == 1
    assert rows[0].detail == "a@b.com"


def test_record_allows_null_user(db):
    audit.record(db, "auth.login_failed", detail="x@y.com")
    rows = audit.list_recent(db)
    assert rows[0].user_id is None


def test_list_recent_is_newest_first_and_respects_limit(db):
    for i in range(5):
        audit.record(db, f"action.{i}")
    rows = audit.list_recent(db, limit=3)
    assert len(rows) == 3
    assert rows[0].action == "action.4"  # newest first
    assert rows[2].action == "action.2"
