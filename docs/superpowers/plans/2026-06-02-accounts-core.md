# Accounts Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent user accounts with register/login/logout and JWT access + DB-backed refresh tokens.

**Architecture:** A new `db.py` provides a SQLAlchemy engine/session. A new `auth/` package holds ORM models (`User`, `RefreshToken`), password hashing (argon2), JWT helpers (PyJWT), business logic (`service.py`), Pydantic schemas, a `get_current_user` dependency, and a router mounted at `/auth`. The existing scanning endpoints are untouched (still env-var keys).

**Tech Stack:** FastAPI, SQLAlchemy 2.x + SQLite, PyJWT (HS256), argon2-cffi, Pydantic v2, pytest.

---

## File Structure

```
src/halal_scanner/
  db.py                  # NEW engine, SessionLocal, Base, get_db()
  auth/
    __init__.py          # NEW exports router
    models.py            # NEW User, RefreshToken
    passwords.py         # NEW hash_password / verify_password
    tokens.py            # NEW create/decode JWT, hash_token
    schemas.py           # NEW Pydantic models
    service.py           # NEW register/authenticate/refresh/logout + exceptions
    dependencies.py      # NEW get_current_user
    router.py            # NEW /auth routes
  api/app.py             # MODIFY include router, create tables, require JWT secret
tests/
  conftest.py            # NEW set test env (JWT secret, temp DB) before imports
  test_passwords.py      # NEW
  test_tokens.py         # NEW
  test_auth_service.py   # NEW
  test_auth_api.py       # NEW
pyproject.toml           # MODIFY add deps
README.md                # MODIFY document /auth + env vars
```

---

## Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml:6-11`

- [ ] **Step 1: Add the runtime deps**

In `pyproject.toml`, replace the `dependencies` list with:

```toml
dependencies = [
    "pyyaml>=6.0",
    "requests>=2.31",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "sqlalchemy>=2.0",
    "pyjwt>=2.8",
    "argon2-cffi>=23.1",
    "email-validator>=2.0",
]
```

- [ ] **Step 2: Install**

Run: `.venv/Scripts/python -m pip install -e ".[dev]"`
Expected: installs sqlalchemy, pyjwt, argon2-cffi, email-validator; ends with "Successfully installed ...".

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build(halal-scanner): add auth deps (sqlalchemy, pyjwt, argon2, email-validator)"
```

---

## Task 2: Database module

**Files:**
- Create: `src/halal_scanner/db.py`

- [ ] **Step 1: Write `db.py`**

```python
"""SQLAlchemy engine, session factory, and Base for the accounts system.

The connection string comes from HALAL_DATABASE_URL (default: local SQLite
file) so it can be pointed at PostgreSQL later without code changes.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine():
    url = os.environ.get("HALAL_DATABASE_URL", "sqlite:///./halal_scanner.db")
    # check_same_thread=False lets the SQLite connection be shared across
    # FastAPI's threadpool workers; harmless for other backends (skipped).
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/Scripts/python -c "from halal_scanner.db import Base, engine, get_db; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/halal_scanner/db.py
git commit -m "feat(halal-scanner): add SQLAlchemy db module (engine, session, Base)"
```

---

## Task 3: ORM models

**Files:**
- Create: `src/halal_scanner/auth/__init__.py`
- Create: `src/halal_scanner/auth/models.py`

- [ ] **Step 1: Create the package init (empty for now)**

`src/halal_scanner/auth/__init__.py`:

```python
"""User accounts and JWT authentication."""
```

- [ ] **Step 2: Write `models.py`**

```python
"""ORM models for users and their refresh tokens."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="tokens")
```

- [ ] **Step 3: Verify tables can be created**

Run:
```bash
.venv/Scripts/python -c "from sqlalchemy import create_engine; from halal_scanner.db import Base; import halal_scanner.auth.models; e=create_engine('sqlite://'); Base.metadata.create_all(e); print(sorted(Base.metadata.tables))"
```
Expected: prints `['refresh_tokens', 'users']`.

- [ ] **Step 4: Commit**

```bash
git add src/halal_scanner/auth/__init__.py src/halal_scanner/auth/models.py
git commit -m "feat(halal-scanner): add User and RefreshToken ORM models"
```

---

## Task 4: Password hashing (TDD)

**Files:**
- Create: `src/halal_scanner/auth/passwords.py`
- Test: `tests/test_passwords.py`

- [ ] **Step 1: Write the failing test**

`tests/test_passwords.py`:

```python
from halal_scanner.auth.passwords import hash_password, verify_password


def test_hash_is_not_plaintext_and_verifies():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert verify_password(h, "correct horse") is True


def test_verify_rejects_wrong_password():
    h = hash_password("correct horse")
    assert verify_password(h, "wrong") is False


def test_hashes_are_salted_so_two_differ():
    assert hash_password("same") != hash_password("same")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_passwords.py -v`
Expected: FAIL — `ModuleNotFoundError: halal_scanner.auth.passwords`.

- [ ] **Step 3: Write `passwords.py`**

```python
"""Argon2 password hashing."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

_ph = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Return an argon2 hash (includes a random salt)."""
    return _ph.hash(plaintext)


def verify_password(password_hash: str, plaintext: str) -> bool:
    """Return True iff plaintext matches the hash; never raises."""
    try:
        return _ph.verify(password_hash, plaintext)
    except Argon2Error:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_passwords.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_passwords.py src/halal_scanner/auth/passwords.py
git commit -m "feat(halal-scanner): add argon2 password hashing"
```

---

## Task 5: JWT token helpers (TDD)

**Files:**
- Create: `src/halal_scanner/auth/tokens.py`
- Test: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tokens.py`:

```python
import os

import jwt
import pytest

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

from halal_scanner.auth import tokens


def test_access_token_round_trips():
    tok = tokens.create_access_token(42)
    payload = tokens.decode_token(tok, "access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_refresh_token_round_trips_and_has_jti():
    tok = tokens.create_refresh_token(7)
    payload = tokens.decode_token(tok, "refresh")
    assert payload["sub"] == "7"
    assert payload["type"] == "refresh"
    assert payload["jti"]


def test_wrong_type_is_rejected():
    access = tokens.create_access_token(1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(access, "refresh")


def test_tampered_token_is_rejected():
    tok = tokens.create_access_token(1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(tok + "x", "access")


def test_expired_token_is_rejected():
    tok = tokens.create_access_token(1, ttl_seconds=-1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(tok, "access")


def test_hash_token_is_deterministic_sha256():
    assert tokens.hash_token("abc") == tokens.hash_token("abc")
    assert tokens.hash_token("abc") != tokens.hash_token("abd")
    assert len(tokens.hash_token("abc")) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_tokens.py -v`
Expected: FAIL — `ModuleNotFoundError: halal_scanner.auth.tokens`.

- [ ] **Step 3: Write `tokens.py`**

```python
"""JWT access/refresh token creation and decoding (HS256)."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
_ACCESS_DEFAULT = 900       # 15 minutes
_REFRESH_DEFAULT = 604800   # 7 days


def _secret() -> str:
    secret = os.environ.get("HALAL_JWT_SECRET")
    if not secret:
        raise RuntimeError("HALAL_JWT_SECRET must be set.")
    return secret


def _ttl(env_name: str, default: int) -> int:
    return int(os.environ.get(env_name, str(default)) or str(default))


def _encode(user_id: int, token_type: str, ttl_seconds: int, extra: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        **extra,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def create_access_token(user_id: int, ttl_seconds: int | None = None) -> str:
    ttl = _ttl("HALAL_ACCESS_TTL", _ACCESS_DEFAULT) if ttl_seconds is None else ttl_seconds
    return _encode(user_id, "access", ttl, {})


def create_refresh_token(user_id: int, ttl_seconds: int | None = None) -> str:
    ttl = _ttl("HALAL_REFRESH_TTL", _REFRESH_DEFAULT) if ttl_seconds is None else ttl_seconds
    return _encode(user_id, "refresh", ttl, {"jti": uuid.uuid4().hex})


def decode_token(token: str, expected_type: str) -> dict:
    """Decode and validate a token; raise jwt.InvalidTokenError on any problem."""
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type.")
    return payload


def hash_token(token: str) -> str:
    """SHA-256 hex digest — what we store, so a raw token never hits the DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_tokens.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tokens.py src/halal_scanner/auth/tokens.py
git commit -m "feat(halal-scanner): add JWT token helpers"
```

---

## Task 6: Pydantic schemas

**Files:**
- Create: `src/halal_scanner/auth/schemas.py`

- [ ] **Step 1: Write `schemas.py`**

```python
"""Pydantic request/response models for the auth endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_FORBID = ConfigDict(extra="forbid")


class RegisterRequest(BaseModel):
    model_config = _FORBID
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = _FORBID
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    model_config = _FORBID
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    is_active: bool
    created_at: datetime
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/Scripts/python -c "from halal_scanner.auth.schemas import RegisterRequest, TokenPair, UserOut; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/halal_scanner/auth/schemas.py
git commit -m "feat(halal-scanner): add auth Pydantic schemas"
```

---

## Task 7: Auth service (TDD)

**Files:**
- Create: `src/halal_scanner/auth/service.py`
- Test: `tests/test_auth_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_auth_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_auth_service.py -v`
Expected: FAIL — `ModuleNotFoundError: halal_scanner.auth.service`.

- [ ] **Step 3: Write `service.py`**

```python
"""Business logic for accounts: register, authenticate, refresh, logout."""
from __future__ import annotations

from datetime import datetime, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tokens
from .models import RefreshToken, User
from .passwords import hash_password, verify_password


class EmailTaken(Exception):
    """Raised when registering an email that already exists."""


class InvalidCredentials(Exception):
    """Raised when email/password do not match."""


class InvalidToken(Exception):
    """Raised when a refresh token is missing, revoked, or undecodable."""


def register(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise EmailTaken()
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(user.password_hash, password):
        raise InvalidCredentials()
    return user


def _store_refresh(db: Session, user_id: int, raw_token: str) -> None:
    payload = tokens.decode_token(raw_token, "refresh")
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=tokens.hash_token(raw_token),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access = tokens.create_access_token(user.id)
    refresh = tokens.create_refresh_token(user.id)
    _store_refresh(db, user.id, refresh)
    return access, refresh


def rotate_refresh(db: Session, raw_token: str) -> tuple[str, str]:
    try:
        payload = tokens.decode_token(raw_token, "refresh")
    except jwt.InvalidTokenError as exc:
        raise InvalidToken() from exc
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(raw_token))
    )
    if row is None or row.revoked:
        raise InvalidToken()
    row.revoked = True  # rotation: the old token can never be used again
    db.commit()
    user_id = int(payload["sub"])
    access = tokens.create_access_token(user_id)
    refresh = tokens.create_refresh_token(user_id)
    _store_refresh(db, user_id, refresh)
    return access, refresh


def logout(db: Session, raw_token: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_token(raw_token))
    )
    if row is None:
        raise InvalidToken()
    row.revoked = True
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_auth_service.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_auth_service.py src/halal_scanner/auth/service.py
git commit -m "feat(halal-scanner): add auth service (register/login/refresh/logout)"
```

---

## Task 8: Current-user dependency

**Files:**
- Create: `src/halal_scanner/auth/dependencies.py`

- [ ] **Step 1: Write `dependencies.py`**

```python
"""FastAPI dependency that resolves the current user from a Bearer token."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from . import tokens
from .models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    try:
        payload = tokens.decode_token(creds.credentials, "access")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return user
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/Scripts/python -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from halal_scanner.auth.dependencies import get_current_user; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/halal_scanner/auth/dependencies.py
git commit -m "feat(halal-scanner): add get_current_user dependency"
```

---

## Task 9: Auth router

**Files:**
- Create: `src/halal_scanner/auth/router.py`
- Modify: `src/halal_scanner/auth/__init__.py`

- [ ] **Step 1: Write `router.py`**

```python
"""HTTP routes for accounts, mounted at /auth."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .dependencies import get_current_user
from .models import User
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    try:
        return service.register(db, req.email, req.password)
    except service.EmailTaken:
        raise HTTPException(status_code=409, detail="Email already registered.")


@router.post("/login", response_model=TokenPair)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = service.authenticate(db, req.email, req.password)
    except service.InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    access, refresh = service.issue_tokens(db, user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        access, refresh_token = service.rotate_refresh(db, req.refresh_token)
    except service.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
def logout(req: RefreshRequest, db: Session = Depends(get_db)) -> None:
    try:
        service.logout(db, req.refresh_token)
    except service.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
```

- [ ] **Step 2: Re-export the router from the package**

Replace `src/halal_scanner/auth/__init__.py` with:

```python
"""User accounts and JWT authentication."""
from .router import router

__all__ = ["router"]
```

- [ ] **Step 3: Verify it imports**

Run: `.venv/Scripts/python -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from halal_scanner.auth import router; print(router.prefix)"`
Expected: prints `/auth`.

- [ ] **Step 4: Commit**

```bash
git add src/halal_scanner/auth/router.py src/halal_scanner/auth/__init__.py
git commit -m "feat(halal-scanner): add /auth router"
```

---

## Task 10: Wire into the app + test bootstrap

**Files:**
- Create: `tests/conftest.py`
- Modify: `src/halal_scanner/api/app.py:8-46`

- [ ] **Step 1: Create `tests/conftest.py`**

This sets a JWT secret and an isolated temp DB **before** any test imports `app`,
so the existing suite keeps passing and the app's startup secret-check is satisfied.

```python
"""Test-wide environment setup. Runs before test modules are imported."""
import os
import tempfile

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")
# Each test run gets its own throwaway SQLite file.
_db_path = os.path.join(tempfile.gettempdir(), "halal_test.db")
os.environ.setdefault("HALAL_DATABASE_URL", f"sqlite:///{_db_path}")
```

- [ ] **Step 2: Modify `app.py` — add imports near the top**

After the existing imports block in `src/halal_scanner/api/app.py` (after line 27,
the schemas import), add:

```python
import os

from ..auth import router as auth_router
from ..db import Base, engine
from .. import auth as _auth_pkg  # noqa: F401  ensures models are registered
```

- [ ] **Step 3: Modify `app.py` — require the JWT secret and create tables**

Immediately after `app = FastAPI(...)` is constructed (after line 33), add:

```python
# Fail closed: refuse to start without a signing secret (see security spec).
if not os.environ.get("HALAL_JWT_SECRET"):
    raise RuntimeError("HALAL_JWT_SECRET must be set to start the API.")

# Create the accounts tables on startup (no-op if they already exist).
Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
```

- [ ] **Step 4: Run the FULL existing suite to confirm nothing broke**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all previous tests still pass (64) plus the new unit tests; 0 failures.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py src/halal_scanner/api/app.py
git commit -m "feat(halal-scanner): mount /auth, create tables, require JWT secret"
```

---

## Task 11: API integration tests (TDD)

**Files:**
- Test: `tests/test_auth_api.py`

- [ ] **Step 1: Write the integration test**

`tests/test_auth_api.py` (uses a fresh in-memory DB via dependency override):

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
import halal_scanner.auth.models  # noqa: F401


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
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
```

- [ ] **Step 2: Run the integration tests**

Run: `.venv/Scripts/python -m pytest tests/test_auth_api.py -v`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth_api.py
git commit -m "test(halal-scanner): add /auth integration tests"
```

---

## Task 12: Docs + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the new endpoints and env vars in `README.md`**

Add a row group to the API table and a new env-var section:

```markdown
### Accounts (Sub-project 7)

| Method | Path             | Body                          | Notes |
|--------|------------------|-------------------------------|-------|
| POST   | `/auth/register` | `{"email","password"}`        | 201; 409 if email taken. |
| POST   | `/auth/login`    | `{"email","password"}`        | Returns access + refresh tokens. |
| POST   | `/auth/refresh`  | `{"refresh_token"}`           | Rotates tokens; old refresh revoked. |
| POST   | `/auth/logout`   | `{"refresh_token"}`           | 204; revokes the refresh token. |
| GET    | `/auth/me`       | `Authorization: Bearer <jwt>` | Current user. |

| Var | Default | Effect |
|-----|---------|--------|
| `HALAL_DATABASE_URL` | `sqlite:///./halal_scanner.db` | SQLAlchemy connection string. |
| `HALAL_JWT_SECRET`   | _(required)_ | HS256 signing secret; the API will not start without it. |
| `HALAL_ACCESS_TTL`   | `900`    | Access-token lifetime (seconds). |
| `HALAL_REFRESH_TTL`  | `604800` | Refresh-token lifetime (seconds). |
```

- [ ] **Step 2: Run the full suite + coverage**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (previous 64 + ~21 new), 0 failures.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(halal-scanner): document /auth endpoints and env vars"
```

---

## Self-Review Notes
- **Spec coverage:** DB (T2), models (T3), passwords (T4), tokens+rotation+hash (T5,T7),
  schemas/extra-forbid (T6), service incl. revocation (T7), get_current_user (T8),
  all 5 endpoints (T9), JWT-secret fail-closed + table creation + wiring (T10),
  no-enumeration login + 409 + 422 + integration happy path (T11), docs (T12).
- **Deferred (per spec):** API-key endpoints (#8), email verify/reset (#9), roles/audit (#10).
- **Type consistency:** `decode_token(token, expected_type)`, `hash_token`,
  service exceptions `EmailTaken/InvalidCredentials/InvalidToken`, `TokenPair`
  fields `access_token/refresh_token/token_type` are used identically across tasks.
```
