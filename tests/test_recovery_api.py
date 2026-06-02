import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
from halal_scanner.auth.email import emailer
import halal_scanner.auth.models  # noqa: F401


@pytest.fixture()
def client():
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
    emailer.outbox.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    emailer.outbox.clear()


def _register(client, email="a@b.com", password="password1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _token_from_outbox():
    return emailer.outbox[-1].body.split()[-1]


def test_email_verification_flow(client):
    _register(client)
    r = client.post("/auth/verify/request", json={"email": "a@b.com"})
    assert r.status_code == 200
    assert len(emailer.outbox) == 1
    token = _token_from_outbox()

    assert client.post("/auth/verify/confirm", json={"token": token}).status_code == 204

    login = client.post("/auth/login", json={"email": "a@b.com", "password": "password1"})
    access = login.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["is_verified"] is True


def test_verify_request_unknown_email_is_silent_200(client):
    r = client.post("/auth/verify/request", json={"email": "nobody@b.com"})
    assert r.status_code == 200
    assert emailer.outbox == []


def test_password_reset_flow_revokes_old_sessions(client):
    _register(client)
    login = client.post("/auth/login", json={"email": "a@b.com", "password": "password1"})
    old_refresh = login.json()["refresh_token"]

    assert client.post("/auth/password-reset/request", json={"email": "a@b.com"}).status_code == 200
    token = _token_from_outbox()
    assert client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "brandnewpass"},
    ).status_code == 204

    assert client.post("/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    assert client.post(
        "/auth/login", json={"email": "a@b.com", "password": "brandnewpass"}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"email": "a@b.com", "password": "password1"}
    ).status_code == 401


def test_confirm_endpoints_reject_bogus_token(client):
    assert client.post("/auth/verify/confirm", json={"token": "bogus"}).status_code == 400
    assert client.post(
        "/auth/password-reset/confirm", json={"token": "bogus", "new_password": "whatever12"}
    ).status_code == 400
