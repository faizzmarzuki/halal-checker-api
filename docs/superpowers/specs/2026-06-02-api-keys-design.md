# Sub-project 8: API-Key Management — Design Spec

**Date:** 2026-06-02
**Status:** Approved
**Part of:** Halal Food Scanner — Sub-project 8 (auth track: 7–10)
**Depends on:** Sub-projects 1–7 (esp. 6 Hardening, 7 Accounts Core)

## Purpose
Let logged-in users create, view, and revoke their own **API keys**, and make
those DB-backed keys the **sole** authentication for the scanning endpoints.
This replaces the environment-variable `HALAL_API_KEYS` mechanism from
Sub-project 6 entirely.

## Decisions (agreed during brainstorming)
- **Replace env-var entirely:** `HALAL_API_KEYS` is removed. Scanning endpoints
  authenticate only against DB-backed, user-owned keys.
- **Always required (secure by default):** every request to `/classify`,
  `/scan-barcode`, `/scan-image` must carry a valid `X-API-Key`, else `401`.
  This closes finding HIGH-1 for the scanning endpoints.
- **Hashed storage:** only the SHA-256 hash of a key is stored; the raw key is
  shown exactly **once**, at creation.
- **Key format:** `hsk_` + 32 bytes of URL-safe randomness. A short `prefix`
  (e.g. `hsk_a1b2c3`) is stored for display so users can identify a key.
- **Optional name/label** per key.

## Two authentication layers (kept distinct)
- **JWT Bearer** (`/auth/*`, `/keys`): a human logs in to manage their account
  and keys.
- **`X-API-Key`** (`/classify`, `/scan-barcode`, `/scan-image`): a machine/app
  uses a key to call the scanner.

## New dependencies
None — uses stdlib `secrets`/`hashlib` plus existing SQLAlchemy/FastAPI.

## Components
```
src/halal_scanner/auth/
  models.py        # MODIFY add ApiKey model
  keys.py          # NEW key generation/hashing + service (create/list/revoke/verify)
  keys_schemas.py  # NEW Pydantic: ApiKeyCreate, ApiKeyOut, ApiKeyCreated
  keys_router.py   # NEW routes mounted at /keys (JWT required)
src/halal_scanner/api/
  security.py      # REWRITE require_api_key -> DB-backed; remove env-var auth
  app.py           # MODIFY mount keys_router
```

## Data model: `api_keys`
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK -> users.id, indexed | owner |
| name | str | optional label, default "" |
| key_hash | str unique, indexed | sha256 hex of the raw key; raw never stored |
| prefix | str | e.g. `hsk_a1b2c3`, for display |
| revoked | bool, default false | |
| created_at | datetime (UTC) | |

## Key generation & verification (`keys.py`)
- `generate_key() -> (raw, prefix)`: `raw = "hsk_" + secrets.token_urlsafe(32)`;
  `prefix = raw[:10]`.
- `hash_key(raw) -> str`: `sha256(raw).hexdigest()` (reuse the same approach as
  refresh tokens).
- Service functions (take a `Session`):
  - `create_key(db, user, name) -> (ApiKey, raw)` — generate, store hash+prefix,
    return the row and the raw key (raw returned to caller only here).
  - `list_keys(db, user) -> list[ApiKey]` — the user's keys (all, incl. revoked).
  - `revoke_key(db, user, key_id) -> None` — set `revoked=True`; raises
    `KeyNotFound` if the key does not exist **or** is not owned by `user`.
  - `verify_key(db, raw) -> ApiKey | None` — look up by hash; return the row iff
    it exists and is not revoked, else `None`.
- Exception: `KeyNotFound`.

## Endpoints

### Key management (under `/keys`, JWT access token required)
| Method | Path | Body | Success | Errors |
|--------|------|------|---------|--------|
| POST | `/keys` | `{name?}` | `201` + `ApiKeyCreated` (incl. raw `api_key`) | `401` no/invalid JWT |
| GET | `/keys` | — | `200` + `list[ApiKeyOut]` (no raw) | `401` |
| DELETE | `/keys/{key_id}` | — | `204` | `401`; `404` not found / not owned |

- `ApiKeyCreate` = `{name: str = ""}` (`extra="forbid"`).
- `ApiKeyOut` = `{id, name, prefix, revoked, created_at}` (never the raw key).
- `ApiKeyCreated` = `ApiKeyOut` + `api_key: str` (the raw key, shown once).

### Scanning endpoints (use `X-API-Key`, not JWT)
- `require_api_key` is rewritten as a DB-backed dependency:
  - read `X-API-Key` header (+ a `Session` via `get_db`);
  - `verify_key` it; if header missing or key invalid/revoked → **`401`**.
  - There is no "auth off" mode anymore — a valid key is always required.
- `rate_limit` is unchanged; it keys on the `X-API-Key` value.
- `/health` stays open.

## Security details (carry over from QA_SECURITY_FINDINGS.txt)
- Keys stored as SHA-256 hashes; raw shown once.
- `DELETE /keys/{id}` for a key the caller does not own returns **`404`** (not
  `403`), so existence of other users' keys is not revealed.
- Request models use `extra="forbid"`.
- Scanning endpoints are now closed by default (no env toggle to leave them open).

## Impact on existing tests
The env-var auth is gone, so these change as part of this sub-project:
- `tests/test_security.py`: the `require_api_key`/`HALAL_API_KEYS` unit tests are
  removed/replaced with DB-backed key tests (rate-limiter tests stay).
- `tests/test_api.py`: scanning-endpoint tests must now create a user → log in →
  create a key → send `X-API-Key`. Tests that asserted "open when no keys
  configured" are replaced with "401 without a key".

## Testing (TDD, network-free)
**Unit (`tests/test_keys.py`)**
- `generate_key` returns a `hsk_`-prefixed raw and a matching `prefix`; two calls
  differ.
- `hash_key` is deterministic sha256 (64 hex chars).
- Service (in-memory SQLite): `create_key` stores a hash (not the raw) and a
  prefix; `verify_key` accepts a fresh key, rejects an unknown key, rejects a
  revoked key; `revoke_key` on someone else's / missing key raises `KeyNotFound`;
  `list_keys` returns only the caller's keys.

**Integration (`tests/test_keys_api.py`, TestClient + StaticPool SQLite)**
- login → `POST /keys` returns a raw `api_key` → that key on `POST /classify`
  → `200`.
- `GET /keys` lists the key with no raw value present.
- `DELETE /keys/{id}` → `204`; the same key on `/classify` → `401`.
- `/classify` with no `X-API-Key` → `401`; with a bogus key → `401`.
- `/keys` without a JWT → `401`.
- A second user cannot delete the first user's key → `404`.

## Out of scope (later sub-projects)
- `last_used_at` tracking (a write on every scan) — deferred (YAGNI).
- Per-user key quotas/limits.
- Email verification & password reset → #9.
- Roles/permissions (admin) & audit logging → #10.
