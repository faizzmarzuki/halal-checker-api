import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth.models import User


@pytest.fixture()
def ctx():
    """Yield (client, SessionFactory) backed by one in-memory SQLite DB."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app), TestingSession
    app.dependency_overrides.clear()


def _auth_headers(client, email="a@b.com", password="password1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_key(client, headers):
    return client.post("/keys", json={"name": "k"}, headers=headers).json()["api_key"]


def test_valid_key_authenticates_and_bad_key_401(ctx):
    client, _ = ctx
    headers = _auth_headers(client)
    raw = _make_key(client, headers)
    assert client.post("/classify", json={"ingredients": ["sugar"]},
                       headers={"X-API-Key": raw}).status_code == 200
    assert client.post("/classify", json={"ingredients": ["sugar"]},
                       headers={"X-API-Key": "hsk_bogus"}).status_code == 401
    assert client.post("/classify", json={"ingredients": ["sugar"]}).status_code == 401
