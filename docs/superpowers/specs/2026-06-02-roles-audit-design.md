# Sub-project 10: Roles & Audit Log — Design Spec

**Date:** 2026-06-02
**Status:** Approved (standing authorization: "teruskan sampai semua sub-project siap")
**Part of:** Halal Food Scanner — Sub-project 10 (final of the auth track: 7–10)
**Depends on:** Sub-projects 1–9

## Purpose
Add **role-based access** (a `user` / `admin` distinction with admin-only
endpoints) and an **audit log** that records security-relevant events. This is
the final hardening sub-project and directly addresses finding L-4 (no audit
logging) from `QA_SECURITY_FINDINGS.txt`.

## Decisions
- **Roles:** a `role` column on `User` (`"user"` default, `"admin"`). A user is
  created as `admin` when their email is listed in the env var
  `HALAL_ADMIN_EMAILS` (comma-separated) at registration time. `role` is surfaced
  in `UserOut`.
- **Admin gate:** a `require_admin` FastAPI dependency built on
  `get_current_user`; returns `403` for non-admins, `401` if unauthenticated.
- **Admin endpoints** under `/admin` (JWT + admin): list all users, list recent
  audit entries.
- **Audit log:** an `audit_logs` table plus a tiny `record()` helper. Events are
  recorded at the router layer (where request context is available) for:
  `user.register`, `auth.login`, `auth.login_failed`, `auth.logout`,
  `key.create`, `key.revoke`.

## New dependencies
None — stdlib + existing SQLAlchemy/FastAPI.

## Components
```
src/halal_scanner/auth/
  models.py          # MODIFY add User.role; add AuditLog model
  schemas.py         # MODIFY add role to UserOut
  roles.py           # NEW resolve_role(email), is_admin(user), require_admin dep
  audit.py           # NEW record(db, action, user_id?, detail?) + list_recent(db, limit)
  service.py         # MODIFY register() sets role via roles.resolve_role
  router.py          # MODIFY record audit on register/login(success+fail)/logout
  keys_router.py     # MODIFY record audit on key create/revoke
  admin_schemas.py   # NEW AuditEntryOut
  admin_router.py    # NEW /admin/users, /admin/audit (require_admin)
src/halal_scanner/api/app.py   # MODIFY mount admin_router
```

## Data model
**users** (add one column)
| column | type | notes |
|--------|------|-------|
| role | str, default "user" | "user" or "admin" |

**audit_logs** (new)
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| action | str, indexed | e.g. `auth.login` |
| user_id | int nullable | actor, when known |
| detail | str, default "" | small context (email, key prefix, ...) |
| created_at | datetime (UTC), indexed | |

## Roles (`roles.py`)
- `_admin_emails() -> set[str]`: parse `HALAL_ADMIN_EMAILS` live (comma-separated).
- `resolve_role(email) -> str`: `"admin"` if `email` in `_admin_emails()` else
  `"user"`.
- `is_admin(user) -> bool`: `user.role == "admin"`.
- `require_admin(user: User = Depends(get_current_user)) -> User`: return the
  user if `is_admin(user)`, else raise `HTTPException(403)`.

## Audit (`audit.py`)
- `record(db, action, user_id=None, detail="") -> None`: insert an `AuditLog`
  row and commit.
- `list_recent(db, limit=100) -> list[AuditLog]`: newest first
  (`order_by(AuditLog.id.desc())`), capped at `limit`.

## Wiring audit into existing routers
- `auth/router.py`:
  - `register`: after success → `record(db, "user.register", user.id, email)`.
  - `login`: on success → `record(db, "auth.login", user.id, email)`; in the
    `InvalidCredentials` handler → `record(db, "auth.login_failed", None, email)`
    then raise `401`.
  - `logout`: after success → `record(db, "auth.logout", None, "")`.
- `keys_router.py`:
  - `create_key`: after success → `record(db, "key.create", user.id, row.prefix)`.
  - `delete_key`: after success → `record(db, "key.revoke", user.id, str(key_id))`.
- `service.register` sets `role=roles.resolve_role(email)` on the new `User`.

## Endpoints (under `/admin`, JWT + admin required)
| Method | Path | Returns | Errors |
|--------|------|---------|--------|
| GET | `/admin/users` | `200` + `list[UserOut]` (all users) | `401` no JWT; `403` not admin |
| GET | `/admin/audit` | `200` + `list[AuditEntryOut]` (recent, newest first) | `401`; `403` |

- `AuditEntryOut` = `{id, action, user_id, detail, created_at}` (`from_attributes`).

## Security details (carry over from QA_SECURITY_FINDINGS.txt)
- L-4 fix: auth + key events are now recorded (incl. failed logins for
  brute-force visibility).
- Admin endpoints fail closed (`require_admin` → 403); non-admins cannot list
  users or read the audit log.
- Audit `detail` stores only non-sensitive context (email, key prefix, key id) —
  never passwords or raw keys/tokens.

## Impact on existing tests
Additive. Existing SP7–SP9 tests keep passing: `role` defaults to `"user"`,
`UserOut` gains a field, and audit `record()` calls are best-effort additions in
the routers. The integration-test fixtures already isolate the DB per test.

## Testing (TDD, network-free)
**Unit**
- `roles.py`: `resolve_role` returns `admin` for an env-listed email, `user`
  otherwise (patch `HALAL_ADMIN_EMAILS`); `is_admin` reflects `user.role`.
- `audit.py`: `record` inserts a row; `list_recent` returns newest-first and
  respects `limit`.

**Integration (`tests/test_admin_api.py`, TestClient + StaticPool SQLite)**
- A normal user → `GET /admin/users` returns `403`; no JWT → `401`.
- An admin user (registered with `HALAL_ADMIN_EMAILS` set) → `GET /admin/users`
  returns `200` with the users; `/auth/me` shows `role: "admin"`.
- After register + a successful login + a failed login, `GET /admin/audit`
  (as admin) contains `user.register`, `auth.login`, and `auth.login_failed`
  entries, newest first.
- Creating then deleting a key produces `key.create` and `key.revoke` audit
  entries.

## Out of scope
- Fine-grained permissions/scopes beyond user/admin, admin user management
  (promote/suspend/delete), audit log retention/rotation, exporting audit logs.
- This completes the auth track (7–10).
