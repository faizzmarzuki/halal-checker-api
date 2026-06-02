import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth import keys
from halal_scanner.auth.models import User


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db, email="a@b.com"):
    u = User(email=email, password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_generate_key_format_and_prefix():
    raw, prefix = keys.generate_key()
    assert raw.startswith("hsk_")
    assert prefix == raw[:10]
    raw2, _ = keys.generate_key()
    assert raw2 != raw


def test_hash_key_is_deterministic_sha256():
    assert keys.hash_key("hsk_abc") == keys.hash_key("hsk_abc")
    assert keys.hash_key("hsk_abc") != keys.hash_key("hsk_abd")
    assert len(keys.hash_key("hsk_abc")) == 64


def test_create_stores_hash_not_raw(db):
    user = _user(db)
    row, raw = keys.create_key(db, user, "laptop")
    assert raw.startswith("hsk_")
    assert row.key_hash == keys.hash_key(raw)
    assert row.key_hash != raw
    assert row.name == "laptop"
    assert row.prefix == raw[:10]


def test_verify_accepts_fresh_rejects_unknown_and_revoked(db):
    user = _user(db)
    row, raw = keys.create_key(db, user, "")
    assert keys.verify_key(db, raw).id == row.id
    assert keys.verify_key(db, "hsk_nonexistent") is None
    keys.revoke_key(db, user, row.id)
    assert keys.verify_key(db, raw) is None


def test_list_keys_only_returns_callers_keys(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    keys.create_key(db, u1, "")
    keys.create_key(db, u1, "")
    keys.create_key(db, u2, "")
    assert len(keys.list_keys(db, u1)) == 2
    assert len(keys.list_keys(db, u2)) == 1


def test_revoke_missing_or_foreign_key_raises(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    row, _ = keys.create_key(db, u1, "")
    with pytest.raises(keys.KeyNotFound):
        keys.revoke_key(db, u2, row.id)  # not u2's key
    with pytest.raises(keys.KeyNotFound):
        keys.revoke_key(db, u1, 99999)   # missing
