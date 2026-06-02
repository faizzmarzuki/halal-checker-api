# Sub-project 9: Account Recovery (Email Verification + Password Reset) — Design Spec

**Date:** 2026-06-02
**Status:** Approved (standing authorization: "teruskan sampai semua sub-project siap")
**Part of:** Halal Food Scanner — Sub-project 9 (auth track: 7–10)
**Depends on:** Sub-projects 1–8

## Purpose
Add **email verification** and **password reset** flows. Both rely on
single-use, hashed, expiring tokens delivered through a pluggable email backend
that defaults to a no-network console/log "outbox" — mirroring how the OCR,
Gemma, and translation backends degrade gracefully without external services.

## Decisions
- **Email delivery:** an `Emailer` with an injectable backend. The default
  backend appends each message to an in-memory outbox and logs it (no SMTP, no
  credentials). A real provider can be plugged in later. Tests read the outbox.
- **Tokens:** opaque `secrets.token_urlsafe(32)` values, stored as SHA-256
  hashes in a new `account_tokens` table, single-use (a `used` flag) with an
  expiry. A `purpose` column distinguishes `verify` from `reset`.
- **User model:** add `is_verified: bool` (default `False`). Verification does
  **not** gate login or key creation in this sub-project (kept shippable; a
  future toggle can enforce it). `is_verified` is surfaced in `UserOut`.
- **Password reset side effect:** on a successful reset, **all** of the user's
  refresh tokens are revoked (force re-login everywhere).
- **No user enumeration:** the two `/request` endpoints always return `200`
  regardless of whether the email exists.

## New dependencies
None — stdlib `secrets`/`hashlib`/`logging` plus existing SQLAlchemy/FastAPI.

## Components
```
src/halal_scanner/auth/
  models.py            # MODIFY add is_verified to User; add AccountToken model
  schemas.py           # MODIFY add is_verified to UserOut
  email.py             # NEW Emailer + default console/outbox backend
  account_tokens.py    # NEW token create/verify/consume + AccountTokenError
  recovery.py          # NEW service: request/confirm verify + request/confirm reset
  recovery_schemas.py  # NEW Pydantic request models
  recovery_router.py   # NEW routes under /auth
src/halal_scanner/api/
  app.py               # MODIFY mount recovery_router
```

## Data model
**users** (add one column)
| column | type | notes |
|--------|------|-------|
| is_verified | bool, default False | set True after email verification |

**account_tokens** (new)
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK -> users.id, indexed | |
| token_hash | str unique, indexed | sha256 of the raw token; raw never stored |
| purpose | str | `verify` or `reset` |
| expires_at | datetime (UTC) | |
| used | bool, default False | single-use |
| created_at | datetime (UTC) | |

## Email backend (`email.py`)
- `EmailMessage` dataclass: `to: str`, `subject: str`, `body: str`.
- `EmailBackend = Callable[[EmailMessage], None]`.
- `class Emailer`: holds a backend (default `_console_backend`) and an `outbox`
  list. `send(to, subject, body)` builds an `EmailMessage`, appends it to
  `outbox`, and calls the backend. Never raises to the caller.
- `_console_backend(msg)` logs the message via the stdlib `logging` module.
- A module-level `emailer = Emailer()` is created once and imported by the
  recovery service (tests can read `emailer.outbox` or inject a backend).

## Token service (`account_tokens.py`)
- `_TTL_VERIFY = 86400` (24h), `_TTL_RESET = 3600` (1h).
- `create_token(db, user_id, purpose) -> str`: generate raw token, store its
  hash + purpose + expiry, return the raw token.
- `consume_token(db, raw, purpose) -> int`: look up by hash; raise
  `AccountTokenError` if missing, wrong purpose, used, or expired; otherwise mark
  `used=True`, commit, and return the `user_id`.
- Exception: `AccountTokenError`.

## Recovery service (`recovery.py`)
- `request_verification(db, email) -> None`: if a user with `email` exists and is
  not verified, create a `verify` token and `emailer.send(...)` a link
  containing it. Always silent (no return, no enumeration).
- `confirm_verification(db, raw) -> None`: `consume_token(db, raw, "verify")`,
  set the user's `is_verified=True`. Raise `AccountTokenError` on bad token.
- `request_reset(db, email) -> None`: if a user with `email` exists, create a
  `reset` token and `emailer.send(...)`. Always silent.
- `confirm_reset(db, raw, new_password) -> None`: `consume_token(db, raw,
  "reset")`, set the user's `password_hash` (argon2), and revoke all of that
  user's refresh tokens. Raise `AccountTokenError` on bad token.

## Endpoints (under `/auth`, no JWT required — these are recovery flows)
| Method | Path | Body | Success | Errors |
|--------|------|------|---------|--------|
| POST | `/auth/verify/request` | `{email}` | `200` (always) | `422` invalid body |
| POST | `/auth/verify/confirm` | `{token}` | `204` | `400` bad/expired/used token |
| POST | `/auth/password-reset/request` | `{email}` | `200` (always) | `422` |
| POST | `/auth/password-reset/confirm` | `{token, new_password}` | `204` | `400` bad token; `422` weak password |

Request models use `extra="forbid"`; `new_password` has `min_length=8`.
`AccountTokenError` maps to `400`.

## Security details (carry over from QA_SECURITY_FINDINGS.txt)
- Tokens stored hashed, single-use, expiring.
- `/request` endpoints never reveal whether an email exists (always `200`).
- Password reset revokes all refresh tokens (limits stolen-session lifetime).
- Reset password re-hashed with argon2; never logged.

## Testing (TDD, network-free)
**Unit**
- `email.py`: `send` appends to `outbox` and invokes the backend; an injected
  backend receives the message.
- `account_tokens.py`: create→consume round-trip returns the user_id and marks
  used; second consume of the same token raises; wrong purpose raises; expired
  token raises.
- `recovery.py` (in-memory SQLite): request_verification sends exactly one email
  for a real unverified user and none for an unknown email; confirm_verification
  sets `is_verified`; request_reset sends for a real user; confirm_reset changes
  the password hash and revokes existing refresh tokens; bad tokens raise.

**Integration (`tests/test_recovery_api.py`, TestClient + StaticPool SQLite)**
- register → `/auth/verify/request` (200, outbox has 1) → extract token from
  outbox → `/auth/verify/confirm` (204) → `/auth/me` shows `is_verified: true`.
- `/auth/verify/request` for an unknown email → `200` and outbox unchanged.
- password reset: register → login → `/auth/password-reset/request` (200) →
  confirm with the token + new password (204) → old refresh token now `401` at
  `/auth/refresh` → login with the new password works.
- `/auth/verify/confirm` and `/auth/password-reset/confirm` with a bogus token →
  `400`.

## Out of scope (Sub-project 10)
- Roles/permissions (admin) and audit logging.
- Real SMTP/provider integration, HTML email templates, rate-limiting the
  recovery endpoints.
