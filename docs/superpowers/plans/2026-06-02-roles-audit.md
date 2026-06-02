# Roles & Audit Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user/admin role with an admin-only `/admin` area, and an audit log that records key auth and API-key events.

**Architecture:** A `role` column on `User` (set from `HALAL_ADMIN_EMAILS` at registration) plus a `require_admin` dependency; an `AuditLog` model with an `audit.record()` helper wired into the existing auth/keys routers; an `admin_router` exposing `/admin/users` and `/admin/audit`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x + SQLite, stdlib `os`, Pydantic v2, pytest.

---

## File Structure
```
src/halal_scanner/auth/
  models.py          # MODIFY add User.role; add AuditLog
  schemas.py         # MODIFY add role to UserOut
  audit.py           # NEW record(), list_recent()
  roles.py           # NEW resolve_role(), is_admin(), require_admin
  admin_schemas.py   # NEW AuditEntryOut
  admin_router.py    # NEW /admin/users, /admin/audit
  service.py         # MODIFY register() sets role
  router.py          # MODIFY audit on register/login/logout
  keys_router.py     # MODIFY audit on key create/revoke
src/halal_scanner/api/app.py   # MODIFY mount admin_router
tests/               # test_audit.py, test_roles.py, test_admin_api.py
README.md            # MODIFY document /admin + roles
```
Tasks 1–4 additive; Task 5 wires audit into existing routers (behavior preserved); Task 6 integration; Task 7 docs. Suite stays green throughout.

---

## Task 1: Model + schema changes

**Files:**
- Modify: `src/halal_scanner/auth/models.py`
- Modify: `src/halal_scanner/auth/schemas.py`

- [ ] **Step 1: Add `role` to `User`**

In `src/halal_scanner/auth/models.py`, inside `class User`, add immediately AFTER
the `is_verified` line:

```python
    role: Mapped[str] = mapped_column(String, default="user")  # "user" | "admin"
```

- [ ] **Step 2: Add the `AuditLog` model**

Append to the END of `src/halal_scanner/auth/models.py`:

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[int | None] = mapped_column(nullable=True)
    detail: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
```

- [ ] **Step 3: Add `role` to `UserOut`**

In `src/halal_scanner/auth/schemas.py`, inside `class UserOut`, add immediately
AFTER the `is_verified: bool` line:

```python
    role: str
```

- [ ] **Step 4: Verify**

Run:
```bash
.venv/Scripts/python.exe -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from sqlalchemy import create_engine; from halal_scanner.db import Base; import halal_scanner.auth.models; e=create_engine('sqlite://'); Base.metadata.create_all(e); print(sorted(Base.metadata.tables)); from halal_scanner.auth.schemas import UserOut; print('role' in UserOut.model_fields)"
```
Expected: prints `['account_tokens', 'api_keys', 'audit_logs', 'refresh_tokens', 'users']` then `True`.

- [ ] **Step 5: Full suite (additive — stays green)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (111), 0 failures.

- [ ] **Step 6: Commit**

```bash
git add src/halal_scanner/auth/models.py src/halal_scanner/auth/schemas.py
git commit -m "feat(halal-scanner): add User.role + AuditLog model"
```

---

## Task 2: Audit service (TDD)

**Files:**
- Create: `src/halal_scanner/auth/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test** — `tests/test_audit.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_audit.py -v`
Expected: FAIL — `ImportError`/`ModuleNotFoundError` for `halal_scanner.auth.audit`.

- [ ] **Step 3: Write `src/halal_scanner/auth/audit.py`:**

```python
"""Append-only audit log of security-relevant events."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog


def record(db: Session, action: str, user_id: int | None = None, detail: str = "") -> None:
    """Append one audit entry and commit."""
    db.add(AuditLog(action=action, user_id=user_id, detail=detail))
    db.commit()


def list_recent(db: Session, limit: int = 100) -> list[AuditLog]:
    """Return up to ``limit`` audit entries, newest first."""
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_audit.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_audit.py src/halal_scanner/auth/audit.py
git commit -m "feat(halal-scanner): add audit log service"
```

---

## Task 3: Roles + require_admin (TDD)

**Files:**
- Create: `src/halal_scanner/auth/roles.py`
- Test: `tests/test_roles.py`

- [ ] **Step 1: Write the failing test** — `tests/test_roles.py`:

```python
import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from halal_scanner.auth import roles
from halal_scanner.auth.models import User


def test_resolve_role_admin_for_listed_email():
    with patch.dict(os.environ, {"HALAL_ADMIN_EMAILS": "boss@x.com, admin@x.com"}):
        assert roles.resolve_role("admin@x.com") == "admin"
        assert roles.resolve_role("boss@x.com") == "admin"
        assert roles.resolve_role("nobody@x.com") == "user"


def test_resolve_role_user_when_env_unset():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HALAL_ADMIN_EMAILS", None)
        assert roles.resolve_role("a@b.com") == "user"


def test_is_admin_reflects_role():
    assert roles.is_admin(User(email="a", password_hash="x", role="admin")) is True
    assert roles.is_admin(User(email="a", password_hash="x", role="user")) is False


def test_require_admin_allows_admin_blocks_user():
    admin = User(email="a", password_hash="x", role="admin")
    normal = User(email="b", password_hash="x", role="user")
    assert roles.require_admin(user=admin) is admin
    with pytest.raises(HTTPException) as exc:
        roles.require_admin(user=normal)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roles.py -v`
Expected: FAIL — `ImportError`/`ModuleNotFoundError` for `halal_scanner.auth.roles`.

- [ ] **Step 3: Write `src/halal_scanner/auth/roles.py`:**

```python
"""Role assignment and the admin-only access dependency."""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException

from .dependencies import get_current_user
from .models import User


def _admin_emails() -> set[str]:
    """Parse HALAL_ADMIN_EMAILS (comma-separated) live on each call."""
    raw = os.environ.get("HALAL_ADMIN_EMAILS", "")
    return {e.strip() for e in raw.split(",") if e.strip()}


def resolve_role(email: str) -> str:
    """admin if the email is allow-listed, else user."""
    return "admin" if email in _admin_emails() else "user"


def is_admin(user: User) -> bool:
    return user.role == "admin"


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency: pass through admins, else 403."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roles.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_roles.py src/halal_scanner/auth/roles.py
git commit -m "feat(halal-scanner): add roles + require_admin dependency"
```

---

## Task 4: Admin schemas + router + mount

**Files:**
- Create: `src/halal_scanner/auth/admin_schemas.py`
- Create: `src/halal_scanner/auth/admin_router.py`
- Modify: `src/halal_scanner/api/app.py`

- [ ] **Step 1: Write `src/halal_scanner/auth/admin_schemas.py`:**

```python
"""Pydantic response model for audit entries."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    user_id: int | None
    detail: str
    created_at: datetime
```

- [ ] **Step 2: Write `src/halal_scanner/auth/admin_router.py`:**

```python
"""Admin-only routes (JWT + admin role), mounted at /admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from . import audit
from .admin_schemas import AuditEntryOut
from .models import User
from .roles import require_admin
from .schemas import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User)))


@router.get("/audit", response_model=list[AuditEntryOut])
def list_audit(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    return audit.list_recent(db)
```

- [ ] **Step 3: Mount in `src/halal_scanner/api/app.py`**

Find `from ..auth.recovery_router import router as recovery_router` and add after it:

```python
from ..auth.admin_router import router as admin_router
```

Find `app.include_router(recovery_router)` and add after it:

```python
app.include_router(admin_router)
```

- [ ] **Step 4: Verify routes + full suite**

Run:
```bash
.venv/Scripts/python.exe -c "import os; os.environ.setdefault('HALAL_JWT_SECRET','x'); from halal_scanner.api.app import app; print(sorted(r.path for r in app.routes if r.path.startswith('/admin')))"
```
Expected: `['/admin/audit', '/admin/users']`.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/auth/admin_schemas.py src/halal_scanner/auth/admin_router.py src/halal_scanner/api/app.py
git commit -m "feat(halal-scanner): add /admin router (users + audit), admin-gated"
```

---

## Task 5: Wire role-at-register + audit events

**Files:**
- Modify: `src/halal_scanner/auth/service.py`
- Modify: `src/halal_scanner/auth/router.py`
- Modify: `src/halal_scanner/auth/keys_router.py`

READ each file first, then apply the changes below.

- [ ] **Step 1: `service.py` — set role at registration**

Add an import near the other `from . import ...` lines:

```python
from . import roles
```

In `register`, change the line that constructs the user from:

```python
    user = User(email=email, password_hash=hash_password(password))
```
to:
```python
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=roles.resolve_role(email),
    )
```

- [ ] **Step 2: `router.py` — record auth audit events**

Add an import near the other `from . import ...` lines:

```python
from . import audit
```

Replace the `register`, `login`, and `logout` functions with these versions
(same behavior, plus audit calls):

```python
@router.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    try:
        user = service.register(db, req.email, req.password)
    except service.EmailTaken:
        raise HTTPException(status_code=409, detail="Email already registered.")
    audit.record(db, "user.register", user.id, req.email)
    return user


@router.post("/login", response_model=TokenPair)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = service.authenticate(db, req.email, req.password)
    except service.InvalidCredentials:
        audit.record(db, "auth.login_failed", None, req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    access, refresh = service.issue_tokens(db, user)
    audit.record(db, "auth.login", user.id, req.email)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=204)
def logout(req: RefreshRequest, db: Session = Depends(get_db)) -> None:
    try:
        service.logout(db, req.refresh_token)
    except service.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    audit.record(db, "auth.logout", None, "")
```

- [ ] **Step 3: `keys_router.py` — record key audit events**

Add an import near the other `from . import ...` lines:

```python
from . import audit
```

In `create_key`, change:

```python
    row, raw = keys_service.create_key(db, user, req.name)
    return ApiKeyCreated(
```
to:
```python
    row, raw = keys_service.create_key(db, user, req.name)
    audit.record(db, "key.create", user.id, row.prefix)
    return ApiKeyCreated(
```

In `delete_key`, change:

```python
    try:
        keys_service.revoke_key(db, user, key_id)
    except keys_service.KeyNotFound:
        raise HTTPException(status_code=404, detail="API key not found.")
```
to:
```python
    try:
        keys_service.revoke_key(db, user, key_id)
    except keys_service.KeyNotFound:
        raise HTTPException(status_code=404, detail="API key not found.")
    audit.record(db, "key.revoke", user.id, str(key_id))
```

- [ ] **Step 4: Full suite (behavior preserved — stays green)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/auth/service.py src/halal_scanner/auth/router.py src/halal_scanner/auth/keys_router.py
git commit -m "feat(halal-scanner): set role at register and record audit events"
```

---

## Task 6: Integration tests (TDD)

**Files:**
- Test: `tests/test_admin_api.py`

- [ ] **Step 1: Write `tests/test_admin_api.py`:**

```python
import os

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
    yield TestClient(app)
    app.dependency_overrides.clear()


def _register_login(client, email, password="password1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_normal_user_forbidden_no_jwt_unauthorized(client):
    assert client.get("/admin/users").status_code == 401
    headers = _register_login(client, "user@x.com")
    assert client.get("/admin/users", headers=headers).status_code == 403


def test_admin_can_list_users_and_me_shows_role(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    # me shows admin role
    me = client.get("/auth/me", headers=headers)
    assert me.json()["role"] == "admin"
    # admin can list users
    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 200
    assert any(u["email"] == "admin@x.com" for u in r.json())


def test_audit_log_captures_events(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    # a failed login for another (non-existent) account
    client.post("/auth/login", json={"email": "ghost@x.com", "password": "whatever1"})
    r = client.get("/admin/audit", headers=headers)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "user.register" in actions
    assert "auth.login" in actions
    assert "auth.login_failed" in actions


def test_audit_log_captures_key_events(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    created = client.post("/keys", json={"name": "k"}, headers=headers).json()
    client.delete(f"/keys/{created['id']}", headers=headers)
    actions = [e["action"] for e in client.get("/admin/audit", headers=headers).json()]
    assert "key.create" in actions
    assert "key.revoke" in actions


# --- helper: set HALAL_ADMIN_EMAILS for the duration of a registration ---
import contextlib


@contextlib.contextmanager
def patch_admin(email: str):
    prev = os.environ.get("HALAL_ADMIN_EMAILS")
    os.environ["HALAL_ADMIN_EMAILS"] = email
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("HALAL_ADMIN_EMAILS", None)
        else:
            os.environ["HALAL_ADMIN_EMAILS"] = prev
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_admin_api.py -v`
Expected: 4 passed.

If a test fails, read the relevant source and report a real defect rather than
weakening the test.

- [ ] **Step 3: Full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_admin_api.py
git commit -m "test(halal-scanner): add admin + audit integration tests"
```

---

## Task 7: Docs + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document `/admin` + roles in `README.md`**

After the account-recovery section, add:

```markdown
### Admin & audit (Sub-project 10)

Users whose email is in `HALAL_ADMIN_EMAILS` (comma-separated) are created with
the `admin` role. Admin endpoints need a JWT for an admin user.

| Method | Path            | Notes |
|--------|-----------------|-------|
| GET    | `/admin/users`  | List all users. `403` for non-admins. |
| GET    | `/admin/audit`  | Recent audit entries (newest first). `403` for non-admins. |

Audit entries are recorded for `user.register`, `auth.login`,
`auth.login_failed`, `auth.logout`, `key.create`, and `key.revoke`.
```

Then add a row to the env-var table:

```markdown
| `HALAL_ADMIN_EMAILS` | _(unset)_ | Comma-separated emails that register as `admin`. |
```

- [ ] **Step 2: Full suite + coverage**

Run: `.venv/Scripts/python.exe -m pytest -q --cov=halal_scanner --cov-report=term-missing`
Expected: all pass, 0 failures.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(halal-scanner): document /admin endpoints and roles"
```

---

## Self-Review Notes
- **Spec coverage:** role + AuditLog model (T1); audit record/list_recent (T2);
  resolve_role/is_admin/require_admin (T3); admin schemas + /admin/users +
  /admin/audit + mount (T4); role-at-register + audit wiring across auth/keys
  routers (T5); integration access-control + audit-trail tests (T6); docs (T7).
- **Type consistency:** `record(db, action, user_id=None, detail="")`,
  `list_recent(db, limit=100)`, `resolve_role(email)->str`, `is_admin(user)`,
  `require_admin`, `AuditEntryOut`, action strings (`user.register`/`auth.login`/
  `auth.login_failed`/`auth.logout`/`key.create`/`key.revoke`) used consistently.
- The integration test sets `HALAL_ADMIN_EMAILS` only around registration (role is
  persisted at register), so it does not depend on env at request time.
```
