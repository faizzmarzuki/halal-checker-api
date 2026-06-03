# Sub-project 16 — Scan History (Design)

Date: 2026-06-03

First product feature after the security-hardening track: record every scan
against the account that made it, and let that account list and delete its
history. Branched from `main`. A web frontend will consume this later.

## Scope (decided)

- **Lightweight storage:** scan type, a short input summary, the overall verdict,
  a timestamp. No per-ingredient breakdown, no image bytes.
- **Endpoints:** `GET /history` (paginated), `DELETE /history/{id}`,
  `DELETE /history` (clear all).
- **Recording:** automatic on every scan, attributed to the API key's owner.

Out of scope: retention / auto-purge, export, full result JSON, and the frontend.

## Data model

Add to `src/halal_scanner/auth/models.py` (all ORM models live there; the table
auto-creates via `Base.metadata.create_all`). It is product data, not auth, but
co-located for consistency with the existing models.

```python
class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scan_type: Mapped[str] = mapped_column(String)          # classify | barcode | image
    summary: Mapped[str] = mapped_column(String, default="")
    verdict: Mapped[str] = mapped_column(String)            # halal | haram | shubhah
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
```

## Attribution — resolve the user from the API key

Today `require_api_key` only validates and returns `None`, so the scanning
endpoints can't attribute a scan. Replace it with a dependency that returns the
authenticated key row:

```python
# src/halal_scanner/api/security.py
def current_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Dependency: require a valid, non-revoked DB API key and return its row."""
    key = verify_key(db, x_api_key) if x_api_key else None
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return key
```

- `require_api_key` is removed; `current_api_key` is the single source of truth
  (no double `verify_key` lookup).
- `_PROTECTED` becomes `[Depends(rate_limit)]`. Each scanning endpoint gains
  `key: ApiKey = Depends(current_api_key)` (enforces 401 + yields the user) and
  `db: Session = Depends(get_db)`.
- The test fixture in `tests/test_api.py` that overrides `require_api_key` is
  updated to override `current_api_key`, returning a fake `ApiKey` with a
  `user_id` so the scanning tests stay auth-free but still attribute a user.

## Recording — best-effort, in the scanning endpoints

New service `src/halal_scanner/history.py`, mirroring `auth/audit.py` (insert +
commit; on failure roll back, log, and swallow — a history write must never break
the scan):

```python
def record(db, user_id, scan_type, summary, verdict) -> None: ...
def list_for_user(db, user, limit, offset) -> list[ScanHistory]: ...
def delete_one(db, user, scan_id) -> None:   # raises NotFound
def delete_all(db, user) -> int:             # returns rows deleted
```

`_summarize` truncates the input to `MAX_SUMMARY_LEN = 200`. Each scanning
endpoint records after computing the verdict:

- `/classify` → `scan_type="classify"`, summary = the (translated) ingredients
  joined with `", "`, truncated.
- `/scan-barcode` → `scan_type="barcode"`, summary = `f"{barcode} ({product_name})"`,
  truncated.
- `/scan-image` → `scan_type="image"`, summary = the OCR text, truncated.

`verdict` is `verdict.verdict.value`.

## Retrieval / delete endpoints

New router `src/halal_scanner/api/history_router.py`, mounted at `/history`,
JWT-authenticated via `get_current_user` (consistent with `/keys`):

- `GET /history?limit=<1-200, default 50>&offset=<>=0, default 0>` → the caller's
  scans, newest first, as `list[ScanHistoryOut]`. `limit`/`offset` validated with
  FastAPI `Query` bounds.
- `DELETE /history/{scan_id}` → delete one own row; 204 on success, 404 if the
  row is missing or owned by another user.
- `DELETE /history` → delete all the caller's rows; 204.

Registered in `app.py` with `app.include_router(history_router)`.

## Schemas

`src/halal_scanner/api/schemas.py`:

```python
class ScanHistoryOut(BaseModel):
    id: int
    scan_type: str
    summary: str
    verdict: str
    created_at: datetime
```

(Read model — `extra="forbid"` is for request bodies, so it is not applied here.)

## Testing (TDD, red → green)

Service / model (`tests/test_history.py`, using the test DB session):
- `record` inserts a row with the right fields.
- `list_for_user` returns the user's rows newest-first and honours limit/offset,
  and never returns another user's rows.
- `delete_one` removes an own row; raises `NotFound` for a missing row or one
  owned by someone else.
- `delete_all` removes only the caller's rows and returns the count.

`current_api_key` (`tests/test_security.py` or `tests/test_keys.py`):
- a valid key → returns the `ApiKey`; missing/invalid/revoked → 401.

Integration (`tests/test_api.py`):
- a scan via `X-API-Key` records exactly one row with the correct `user_id`,
  `scan_type`, `summary`, and `verdict`, for each of the three endpoints.
- if `history.record` raises, the scan still returns its verdict (best-effort).

History endpoints (`tests/test_history_api.py`):
- `GET /history` (JWT) returns the user's rows newest-first; `limit`/`offset`
  paginate; out-of-range `limit` → 422.
- `DELETE /history/{id}` deletes own (204); another user's row → 404.
- `DELETE /history` clears all the caller's rows (204) and a subsequent `GET`
  is empty.

Run: `.venv/Scripts/python -m pytest -q` (baseline on this branch: 159 passing,
2 skipped).

## Conventions

Branch `sub-project-16-scan-history` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD; `--no-ff` merge to `main`; delete the branch.
Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
