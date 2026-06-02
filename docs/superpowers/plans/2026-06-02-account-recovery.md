# Account Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email verification and password reset via single-use, hashed, expiring tokens delivered through a pluggable (default console) email backend.

**Architecture:** A new `AccountToken` model plus `email.py` (Emailer), `account_tokens.py` (token create/consume), `recovery.py` (service) under `auth/`, exposed via a `recovery_router` under `/auth`. `User` gains `is_verified`; password reset revokes the user's refresh tokens.

**Tech Stack:** FastAPI, SQLAlchemy 2.x + SQLite, stdlib `secrets`/`hashlib`/`logging`, Pydantic v2, pytest.

---

## File Structure
```
src/halal_scanner/auth/
  models.py            # MODIFY add User.is_verified; add AccountToken
  schemas.py           # MODIFY add is_verified to UserOut
  email.py             # NEW Emailer + default console backend + module emailer
  account_tokens.py    # NEW create_token/consume_token + AccountTokenError
  recovery.py          # NEW request/confirm verify + request/confirm reset
  recovery_schemas.py  # NEW EmailRequest, TokenConfirm, ResetConfirm
  recovery_router.py   # NEW /auth recovery routes
src/halal_scanner/api/app.py   # MODIFY mount recovery_router
tests/                 # test_email.py, test_account_tokens.py, test_recovery.py, test_recovery_api.py
README.md              # MODIFY document recovery endpoints
```
Tasks 1–5 are additive; Task 6 adds integration tests; Task 7 docs. Suite stays green throughout.

---

## Task 1: Model + schema changes

**Files:**
- Modify: `src/halal_scanner/auth/models.py`
- Modify: `src/halal_scanner/auth/schemas.py`

- [ ] **Step 1: Add `is_verified` to the `User` model**

In `src/halal_scanner/auth/models.py`, inside `class User`, add this column right
after the existing `is_active` line:

```python
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: Add the `AccountToken` model**

Append to the END of `src/halal_scanner/auth/models.py`:

```python
class AccountToken(Base):
    __tablename__ = "account_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String)  # "verify" | "reset"
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
```

- [ ] **Step 3: Add `is_verified` to `UserOut`**

In `src/halal_scanner/auth/schemas.py`, inside `class UserOut`, add right after
the `is_active: bool` line:

```python
    is_verified: bool
```

- [ ] **Step 4: Verify tables + schema**

Run:
```bash
.venv/Scripts/python.exe -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from sqlalchemy import create_engine; from halal_scanner.db import Base; import halal_scanner.auth.models; e=create_engine('sqlite://'); Base.metadata.create_all(e); print(sorted(Base.metadata.tables)); from halal_scanner.auth.schemas import UserOut; print('is_verified' in UserOut.model_fields)"
```
Expected: prints `['account_tokens', 'api_keys', 'refresh_tokens', 'users']` then `True`.

- [ ] **Step 5: Run the full suite (additive — should stay green)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (94), 0 failures.

- [ ] **Step 6: Commit**

```bash
git add src/halal_scanner/auth/models.py src/halal_scanner/auth/schemas.py
git commit -m "feat(halal-scanner): add is_verified + AccountToken model"
```

---

## Task 2: Email backend (TDD)

**Files:**
- Create: `src/halal_scanner/auth/email.py`
- Test: `tests/test_email.py`

- [ ] **Step 1: Write the failing test** — `tests/test_email.py`:

```python
from halal_scanner.auth.email import Emailer, EmailMessage


def test_send_appends_to_outbox():
    em = Emailer()
    em.send("a@b.com", "Hi", "Body")
    assert len(em.outbox) == 1
    msg = em.outbox[0]
    assert isinstance(msg, EmailMessage)
    assert msg.to == "a@b.com"
    assert msg.subject == "Hi"
    assert msg.body == "Body"


def test_injected_backend_receives_message():
    seen = []
    em = Emailer(backend=seen.append)
    em.send("x@y.com", "S", "B")
    assert len(seen) == 1
    assert seen[0].to == "x@y.com"


def test_backend_failure_does_not_raise():
    def boom(msg):
        raise RuntimeError("smtp down")

    em = Emailer(backend=boom)
    em.send("a@b.com", "S", "B")  # must not raise
    assert len(em.outbox) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email.py -v`
Expected: FAIL — `ModuleNotFoundError: halal_scanner.auth.email`.

- [ ] **Step 3: Write `src/halal_scanner/auth/email.py`:**

```python
"""Pluggable email delivery with a default no-network console backend.

Mirrors the OCR/Gemma backends: the default never touches the network — it just
records and logs messages — so the app and tests work with no email provider.
A real backend (SMTP, Resend, ...) can be injected later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


EmailBackend = Callable[[EmailMessage], None]


def _console_backend(msg: EmailMessage) -> None:
    logger.info("EMAIL to=%s subject=%s body=%s", msg.to, msg.subject, msg.body)


class Emailer:
    """Sends email via a backend; keeps an in-memory outbox. Never raises."""

    def __init__(self, backend: EmailBackend | None = None):
        self._backend = backend or _console_backend
        self.outbox: list[EmailMessage] = []

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage(to=to, subject=subject, body=body)
        self.outbox.append(msg)
        try:
            self._backend(msg)
        except Exception:
            logger.exception("Email backend failed for %s", to)


# One shared instance the recovery service uses; tests may read its outbox.
emailer = Emailer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_email.py src/halal_scanner/auth/email.py
git commit -m "feat(halal-scanner): add pluggable Emailer with console backend"
```

---

## Task 3: Account token service (TDD)

**Files:**
- Create: `src/halal_scanner/auth/account_tokens.py`
- Test: `tests/test_account_tokens.py`

- [ ] **Step 1: Write the failing test** — `tests/test_account_tokens.py`:

```python
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
    # second use fails (single-use)
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
    # force expiry into the past
    row = db.scalar(select(AccountToken).where(AccountToken.user_id == user.id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(at.AccountTokenError):
        at.consume_token(db, raw, "reset")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_account_tokens.py -v`
Expected: FAIL — `ModuleNotFoundError: halal_scanner.auth.account_tokens`.

- [ ] **Step 3: Write `src/halal_scanner/auth/account_tokens.py`:**

```python
"""Single-use, hashed, expiring tokens for verification and password reset."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AccountToken

_TTL = {"verify": 86400, "reset": 3600}  # seconds: 24h verify, 1h reset


class AccountTokenError(Exception):
    """Raised when a token is missing, wrong-purpose, already used, or expired."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_token(db: Session, user_id: int, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(
        AccountToken(
            user_id=user_id,
            token_hash=_hash(raw),
            purpose=purpose,
            expires_at=now + timedelta(seconds=_TTL[purpose]),
        )
    )
    db.commit()
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> int:
    """Validate and mark a token used; return its user_id, or raise."""
    row = db.scalar(select(AccountToken).where(AccountToken.token_hash == _hash(raw)))
    if row is None or row.used or row.purpose != purpose:
        raise AccountTokenError()
    # SQLite returns naive datetimes; normalize to aware UTC before comparing.
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise AccountTokenError()
    row.used = True
    db.commit()
    return row.user_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_account_tokens.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_account_tokens.py src/halal_scanner/auth/account_tokens.py
git commit -m "feat(halal-scanner): add single-use account token service"
```

---

## Task 4: Recovery service (TDD)

**Files:**
- Create: `src/halal_scanner/auth/recovery.py`
- Test: `tests/test_recovery.py`

- [ ] **Step 1: Write the failing test** — `tests/test_recovery.py`:

```python
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
    # an existing refresh token that should get revoked
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recovery.py -v`
Expected: FAIL — `ImportError`/`ModuleNotFoundError` for `halal_scanner.auth.recovery`.

- [ ] **Step 3: Write `src/halal_scanner/auth/recovery.py`:**

```python
"""Email verification and password reset orchestration."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import account_tokens
from .email import emailer
from .models import RefreshToken, User
from .passwords import hash_password


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def request_verification(db: Session, email: str) -> None:
    """Email a verification token. Silent if the user is unknown/already verified."""
    user = _user_by_email(db, email)
    if user is None or user.is_verified:
        return
    token = account_tokens.create_token(db, user.id, "verify")
    emailer.send(email, "Verify your email", f"Your verification token: {token}")


def confirm_verification(db: Session, raw: str) -> None:
    user_id = account_tokens.consume_token(db, raw, "verify")
    user = db.get(User, user_id)
    user.is_verified = True
    db.commit()


def request_reset(db: Session, email: str) -> None:
    """Email a reset token. Silent if the user is unknown (no enumeration)."""
    user = _user_by_email(db, email)
    if user is None:
        return
    token = account_tokens.create_token(db, user.id, "reset")
    emailer.send(email, "Reset your password", f"Your reset token: {token}")


def confirm_reset(db: Session, raw: str, new_password: str) -> None:
    user_id = account_tokens.consume_token(db, raw, "reset")
    user = db.get(User, user_id)
    user.password_hash = hash_password(new_password)
    # Force re-login everywhere: revoke all of the user's refresh tokens.
    for rt in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id)):
        rt.revoked = True
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recovery.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_recovery.py src/halal_scanner/auth/recovery.py
git commit -m "feat(halal-scanner): add recovery service (verify + reset)"
```

---

## Task 5: Recovery schemas + router + mount

**Files:**
- Create: `src/halal_scanner/auth/recovery_schemas.py`
- Create: `src/halal_scanner/auth/recovery_router.py`
- Modify: `src/halal_scanner/api/app.py`

- [ ] **Step 1: Write `src/halal_scanner/auth/recovery_schemas.py`:**

```python
"""Pydantic request models for the account-recovery endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_FORBID = ConfigDict(extra="forbid")


class EmailRequest(BaseModel):
    model_config = _FORBID
    email: EmailStr


class TokenConfirm(BaseModel):
    model_config = _FORBID
    token: str = Field(min_length=1)


class ResetConfirm(BaseModel):
    model_config = _FORBID
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 2: Write `src/halal_scanner/auth/recovery_router.py`:**

```python
"""Account-recovery routes (no JWT — these are pre-auth recovery flows)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from . import recovery
from .account_tokens import AccountTokenError
from .recovery_schemas import EmailRequest, ResetConfirm, TokenConfirm

router = APIRouter(prefix="/auth", tags=["recovery"])


@router.post("/verify/request")
def verify_request(req: EmailRequest, db: Session = Depends(get_db)) -> dict:
    recovery.request_verification(db, req.email)
    return {"status": "ok"}


@router.post("/verify/confirm", status_code=204)
def verify_confirm(req: TokenConfirm, db: Session = Depends(get_db)) -> None:
    try:
        recovery.confirm_verification(db, req.token)
    except AccountTokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")


@router.post("/password-reset/request")
def reset_request(req: EmailRequest, db: Session = Depends(get_db)) -> dict:
    recovery.request_reset(db, req.email)
    return {"status": "ok"}


@router.post("/password-reset/confirm", status_code=204)
def reset_confirm(req: ResetConfirm, db: Session = Depends(get_db)) -> None:
    try:
        recovery.confirm_reset(db, req.token, req.new_password)
    except AccountTokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
```

- [ ] **Step 3: Mount it in `src/halal_scanner/api/app.py`**

Find the line `from ..auth.keys_router import router as keys_router` and add after it:

```python
from ..auth.recovery_router import router as recovery_router
```

Find `app.include_router(keys_router)` and add after it:

```python
app.include_router(recovery_router)
```

- [ ] **Step 4: Verify routes registered + run full suite**

Run:
```bash
.venv/Scripts/python.exe -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from halal_scanner.api.app import app; print(sorted(r.path for r in app.routes if 'verify' in r.path or 'password-reset' in r.path))"
```
Expected: `['/auth/password-reset/confirm', '/auth/password-reset/request', '/auth/verify/confirm', '/auth/verify/request']`.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/auth/recovery_schemas.py src/halal_scanner/auth/recovery_router.py src/halal_scanner/api/app.py
git commit -m "feat(halal-scanner): add recovery schemas, router, and mount"
```

---

## Task 6: Integration tests (TDD)

**Files:**
- Test: `tests/test_recovery_api.py`

- [ ] **Step 1: Write `tests/test_recovery_api.py`:**

```python
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
    # body is "...token: <token>"
    return emailer.outbox[-1].body.split()[-1]


def test_email_verification_flow(client):
    _register(client)
    r = client.post("/auth/verify/request", json={"email": "a@b.com"})
    assert r.status_code == 200
    assert len(emailer.outbox) == 1
    token = _token_from_outbox()

    assert client.post("/auth/verify/confirm", json={"token": token}).status_code == 204

    # /auth/me now shows verified
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

    # old refresh token no longer works
    assert client.post("/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    # new password works
    assert client.post(
        "/auth/login", json={"email": "a@b.com", "password": "brandnewpass"}
    ).status_code == 200
    # old password no longer works
    assert client.post(
        "/auth/login", json={"email": "a@b.com", "password": "password1"}
    ).status_code == 401


def test_confirm_endpoints_reject_bogus_token(client):
    assert client.post("/auth/verify/confirm", json={"token": "bogus"}).status_code == 400
    assert client.post(
        "/auth/password-reset/confirm", json={"token": "bogus", "new_password": "whatever12"}
    ).status_code == 400
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recovery_api.py -v`
Expected: 4 passed.

- [ ] **Step 3: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_recovery_api.py
git commit -m "test(halal-scanner): add account-recovery integration tests"
```

---

## Task 7: Docs + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the recovery endpoints in `README.md`**

After the API-keys section table, add:

```markdown
### Account recovery (Sub-project 9)

Email is delivered via a pluggable backend that defaults to logging (no provider
needed locally). `/request` endpoints always return `200` (no account
enumeration); the raw token is in the email body.

| Method | Path                            | Body                       | Notes |
|--------|---------------------------------|----------------------------|-------|
| POST   | `/auth/verify/request`          | `{email}`                  | `200`; sends a verification token. |
| POST   | `/auth/verify/confirm`          | `{token}`                  | `204`; marks the user verified. `400` if bad. |
| POST   | `/auth/password-reset/request`  | `{email}`                  | `200`; sends a reset token. |
| POST   | `/auth/password-reset/confirm`  | `{token, new_password}`    | `204`; resets the password and revokes all refresh tokens. `400` if bad. |
```

- [ ] **Step 2: Full suite + coverage**

Run: `.venv/Scripts/python.exe -m pytest -q --cov=halal_scanner --cov-report=term-missing`
Expected: all pass, 0 failures.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(halal-scanner): document account-recovery endpoints"
```

---

## Self-Review Notes
- **Spec coverage:** is_verified + AccountToken (T1); Emailer + console backend (T2);
  single-use/expiring/hashed tokens with wrong-purpose + expiry checks (T3);
  request/confirm verify + request/confirm reset incl. refresh-token revocation
  and no-enumeration (T4); schemas (extra=forbid) + 4 routes + mount (T5);
  integration verify flow, reset flow with session revocation, bogus-token 400,
  silent-200 (T6); docs (T7).
- **Deferred (per spec):** roles/audit (#10), real SMTP provider, recovery rate
  limiting.
- **Type consistency:** `create_token(db,user_id,purpose)->raw`,
  `consume_token(db,raw,purpose)->user_id`, `AccountTokenError`, `Emailer.send`,
  `emailer.outbox`, recovery `request_verification/confirm_verification/
  request_reset/confirm_reset`, schemas `EmailRequest/TokenConfirm/ResetConfirm`
  used consistently. The SQLite naive-datetime comparison is handled in
  `consume_token` (tz-normalized) — the expired-token test guards it.
```
