# Sub-project 7: Accounts Core (Users + JWT Auth) — Design Spec

**Date:** 2026-06-02
**Status:** Approved
**Part of:** Halal Food Scanner — Sub-project 7 (first of the auth track: 7–10)
**Depends on:** Sub-projects 1–6

## Purpose
Add the project's first **persistent user accounts** with register / login /
logout, backed by a real database. Authentication uses short-lived **JWT access
tokens** plus longer-lived **refresh tokens** stored (hashed) in the database so
they can be revoked on logout. This sub-project is self-contained: it does **not**
yet change how the scanning endpoints (`/classify`, etc.) authenticate — those
keep the env-var API keys from Sub-project 6 until Sub-project 8 (API-key
management) ties keys to users.

## Decisions (agreed during brainstorming)
- **Database:** SQLAlchemy 2.x ORM + SQLite file, connection string from env so
  it is swappable to PostgreSQL later without code changes.
- **Tokens:** JWT (HS256) via `PyJWT`. Access token ~15 min, refresh token ~7
  days. Refresh-token **rotation** on every `/auth/refresh`.
- **Logout / revocation:** refresh tokens are stored in the DB; logout marks the
  presented refresh token `revoked`. Access tokens are short-lived and expire
  naturally (no per-request denylist).
- **Password hashing:** `argon2-cffi` (memory-hard; avoids passlib/bcrypt version
  issues).

## New dependencies
- `sqlalchemy>=2.0`
- `pyjwt>=2.8`
- `argon2-cffi>=23.1`

(All added to `[project].dependencies` in `pyproject.toml`.)

## New modules
```
src/halal_scanner/
  db.py                  # engine, SessionLocal, Base, get_db() FastAPI dependency
  auth/
    __init__.py
    models.py            # User, RefreshToken ORM models
    passwords.py         # hash_password(), verify_password()  (argon2)
    tokens.py            # create_access_token, create_refresh_token, decode_token
    schemas.py           # Pydantic request/response models (extra="forbid")
    service.py           # register / authenticate / refresh / logout logic
    dependencies.py      # get_current_user() — validate Bearer access token
    router.py            # APIRouter mounted at /auth
```
`app.py` calls `app.include_router(auth_router)` and creates tables on startup
(`Base.metadata.create_all(engine)`).

## Data model
**users**
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| email | str unique, indexed | login identifier |
| password_hash | str | argon2 hash, never returned |
| is_active | bool, default true | |
| created_at | datetime (UTC) | |

**refresh_tokens**
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK -> users.id | |
| token_hash | str, indexed | SHA-256 of the raw token; raw never stored |
| expires_at | datetime (UTC) | |
| revoked | bool, default false | set true on logout / rotation |
| created_at | datetime (UTC) | |

## Endpoints (mounted under `/auth`)
| Method | Path | Body | Success | Errors |
|--------|------|------|---------|--------|
| POST | `/auth/register` | `{email, password}` | `201` + `UserOut` | `409` email taken; `422` invalid |
| POST | `/auth/login` | `{email, password}` | `200` + `TokenPair` | `401` bad credentials |
| POST | `/auth/refresh` | `{refresh_token}` | `200` + `TokenPair` (rotated) | `401` invalid/expired/revoked |
| POST | `/auth/logout` | `{refresh_token}` | `204` | `401` invalid token |
| GET | `/auth/me` | Bearer access token | `200` + `UserOut` | `401` missing/invalid token |

`TokenPair` = `{access_token, refresh_token, token_type: "bearer"}`.
`UserOut` = `{id, email, is_active, created_at}` (never includes the hash).

## Token flow
- **Access token:** JWT claims `sub=user_id`, `type=access`, `exp` (~15 min).
  Sent as `Authorization: Bearer <token>`; validated by `get_current_user()`.
- **Refresh token:** JWT claims `sub=user_id`, `type=refresh`, `jti` (unique id),
  `exp` (~7 days). On issue, store `sha256(token)` in `refresh_tokens`.
- **`/auth/refresh`:** decode the refresh token, confirm its hash exists and is
  not revoked/expired, then **rotate**: revoke the old row, issue+store a new
  refresh token, and return a new access token. (Reuse of a revoked refresh
  token → `401`.)
- **`/auth/logout`:** decode the refresh token and mark its row `revoked`.

## Security details (carry over from QA_SECURITY_FINDINGS.txt)
- Passwords: argon2, min length 8 enforced by Pydantic; never logged or returned.
- Email uniqueness enforced at the DB (`unique`) and pre-checked in the service
  for a clean `409`.
- Login returns an identical `401` for unknown email vs. wrong password (no user
  enumeration).
- `HALAL_JWT_SECRET` is required: the app refuses to start if it is unset (fail
  closed). Token lifetimes configurable via `HALAL_ACCESS_TTL` /
  `HALAL_REFRESH_TTL` (sane defaults).
- All Pydantic request models set `model_config = ConfigDict(extra="forbid")`
  (closes mass-assignment note L-5).
- Refresh tokens stored as SHA-256 hashes, so a DB leak yields no usable tokens.

## Configuration (env vars)
| Var | Default | Effect |
|-----|---------|--------|
| `HALAL_DATABASE_URL` | `sqlite:///./halal_scanner.db` | SQLAlchemy connection string |
| `HALAL_JWT_SECRET` | _(required)_ | HS256 signing secret; app won't start unset |
| `HALAL_ACCESS_TTL` | `900` | Access-token lifetime, seconds |
| `HALAL_REFRESH_TTL` | `604800` | Refresh-token lifetime, seconds |

For the existing test suite, a default test secret is set so unrelated tests
that import `app` keep working without configuring the environment.

## Testing (TDD, network-free)
**Unit**
- `passwords.py`: hash != plaintext; `verify_password` true for correct, false
  for wrong; each hash is salted (two hashes of same password differ).
- `tokens.py`: round-trip create/decode; expired token rejected; wrong-type
  token (access used where refresh expected) rejected; tampered token rejected.
- `service.py` (in-memory SQLite session): register creates a user; duplicate
  email raises the conflict; authenticate succeeds/fails correctly; refresh
  rotates and revokes the old token; reusing a revoked token fails; logout
  revokes.

**Integration** (`TestClient`, temporary SQLite via dependency override)
- Full happy path: register → login → `GET /auth/me` with access token →
  `/auth/refresh` → `/auth/logout`.
- `register` duplicate email → `409`.
- `login` wrong password / unknown email → `401` (identical response).
- `/auth/me` without/with-bad token → `401`.
- `/auth/refresh` with revoked/expired token → `401`.

## Out of scope (later sub-projects)
- API-key create / view / delete and wiring keys into the scanning endpoints → **#8**.
- Email verification and password reset → **#9**.
- Roles/permissions (admin) and audit logging → **#10**.
- Distributed/Redis token storage, OAuth social login, DB migrations (Alembic).
