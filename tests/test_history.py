import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth.models import ScanHistory, User
from halal_scanner import history


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db, email):
    u = User(email=email, password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_record_inserts_row(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "classify", "sugar, lard", "haram")
    rows = db.scalars(select(ScanHistory)).all()
    assert len(rows) == 1
    assert rows[0].user_id == u.id
    assert rows[0].scan_type == "classify"
    assert rows[0].summary == "sugar, lard"
    assert rows[0].verdict == "haram"


def test_record_truncates_summary(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "image", "x" * 500, "halal")
    row = db.scalars(select(ScanHistory)).one()
    assert len(row.summary) == history.MAX_SUMMARY_LEN


def test_list_for_user_is_newest_first_and_scoped(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    for v in ("halal", "haram", "shubhah"):
        history.record(db, u1.id, "classify", v, v)
    history.record(db, u2.id, "classify", "other", "halal")
    rows = history.list_for_user(db, u1)
    assert [r.summary for r in rows] == ["shubhah", "haram", "halal"]  # newest first
    assert all(r.user_id == u1.id for r in rows)  # never another user's rows


def test_list_for_user_paginates(db):
    u = _user(db, "a@b.com")
    for i in range(5):
        history.record(db, u.id, "classify", str(i), "halal")
    page = history.list_for_user(db, u, limit=2, offset=1)
    assert [r.summary for r in page] == ["3", "2"]


def test_delete_one_removes_own_row(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "classify", "sugar", "halal")
    row_id = db.scalars(select(ScanHistory)).one().id
    history.delete_one(db, u, row_id)
    assert db.scalars(select(ScanHistory)).all() == []


def test_delete_one_other_user_raises_notfound(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    history.record(db, u1.id, "classify", "sugar", "halal")
    row_id = db.scalars(select(ScanHistory)).one().id
    with pytest.raises(history.NotFound):
        history.delete_one(db, u2, row_id)
    with pytest.raises(history.NotFound):
        history.delete_one(db, u1, 9999)  # missing


def test_delete_all_scopes_to_user(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    for _ in range(3):
        history.record(db, u1.id, "classify", "x", "halal")
    history.record(db, u2.id, "classify", "y", "halal")
    n = history.delete_all(db, u1)
    assert n == 3
    remaining = db.scalars(select(ScanHistory)).all()
    assert len(remaining) == 1 and remaining[0].user_id == u2.id
