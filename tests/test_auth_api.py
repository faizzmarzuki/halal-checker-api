import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
import halal_scanner.auth.models  # noqa: F401


@pytest.fixture()
def client():
    # StaticPool keeps a single shared connection so the in-memory schema
    # created below is visible to every session (incl. TestClient's worker thread).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def _register(client, email="a@b.com", password="password1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_then_login_me_refresh_logout(client):
    assert _register(client).status_code == 201

    r = client.post("/auth/login", json={"email": "a@b.com", "password": "password1"})
    assert r.status_code == 200
    tokens = r.json()
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"

    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != refresh

    # old refresh now revoked
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401

    assert client.post("/auth/logout", json={"refresh_token": new_refresh}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401


def test_register_duplicate_email_409(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_login_wrong_password_and_unknown_email_both_401(client):
    _register(client)
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "wrongpass"}).status_code == 401
    assert client.post("/auth/login", json={"email": "x@b.com", "password": "password1"}).status_code == 401


def test_me_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_register_rejects_short_password_and_bad_email(client):
    assert client.post("/auth/register", json={"email": "a@b.com", "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={"email": "notanemail", "password": "password1"}).status_code == 422


def test_register_rejects_extra_fields(client):
    r = client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "password1", "is_admin": True},
    )
    assert r.status_code == 422
