# Sub-project 12 — Image & Response Hardening (Design)

Date: 2026-06-03

Closes one MEDIUM and two LOW findings from the QA/security pass
(`QA_SECURITY_FINDINGS.txt`): MED-2 (image decompression-bomb DoS), L-1 (missing
security headers), and L-5 (request models silently ignore unexpected fields).

Branched from the SP11 tip (`sub-project-11-dos-input-hardening`), so it is
stacked on SP11 and shares its CHECKPOINT/docs. Merge SP11 first, then SP12.

## Context: why MED-4 is NOT in this sub-project

The original QA finding MED-4 (non-constant-time API-key compare) pointed at
`x_api_key not in keys` — a plaintext set-membership test that existed before the
auth track. SP8 removed that code. The API key is now SHA-256 hashed and looked
up by `key_hash` in the database (`auth/keys.py:verify_key`). There is no
plaintext comparison left, and timing on a hash lookup does not leak a usable
signal (an attacker cannot incrementally guess a hash to recover the raw key).
MED-4 is therefore already mitigated by design and needs no code change.

## MED-2 — Image decompression-bomb guard

### Problem

`src/halal_scanner/ocr.py:_default_backend` opens untrusted image bytes with
Pillow and hands them straight to Tesseract. SP11 caps the request body at 5 MB,
but a small compressed file can still decode to an enormous pixel area
(a "decompression bomb"), exhausting memory.

### Fix

Split the guard (pure, Pillow-free) from the Pillow open so the guard logic is
testable in every environment, and the Pillow integration is testable only when
the optional `ocr` extra is installed:

```python
# Bound the decoded pixel area to defend against decompression bombs (MED-2).
# ~40 MP is generous for a real phone photo of a label; bombs are typically
# hundreds of MP.
MAX_IMAGE_PIXELS = 40_000_000


def _ensure_within_pixel_cap(
    width: int, height: int, max_pixels: int = MAX_IMAGE_PIXELS
) -> None:
    """Raise ValueError if the decoded pixel area would exceed the cap (MED-2)."""
    if width * height > max_pixels:
        raise ValueError(f"image {width}x{height} exceeds {max_pixels}px cap")


def _open_image(image_bytes: bytes, max_pixels: int = MAX_IMAGE_PIXELS):
    """Open image bytes with Pillow, rejecting oversized (bomb) images.

    Image.open is lazy (header only), so width/height are available before the
    pixels are decoded — the check rejects a bomb before any large allocation.
    """
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    _ensure_within_pixel_cap(img.width, img.height, max_pixels)
    return img
```

`_default_backend` then becomes:

```python
def _default_backend(image_bytes: bytes) -> str:
    """Tesseract OCR backend. Imports are lazy so deps are optional."""
    import pytesseract

    return pytesseract.image_to_string(_open_image(image_bytes))
```

`OcrEngine.extract_text` already wraps the backend in `except Exception: return ""`,
so a rejected bomb collapses to `""`, and `/scan-image` returns its existing
422 "Could not read any text from the image." No new error path is needed.

### Testability

Pillow is an OPTIONAL dependency (the `ocr` extra); the default `dev` test
environment does not install it. So the tests must not require Pillow to import:

- `_ensure_within_pixel_cap` is pure (ints in, raises or not) and is unit-tested
  in EVERY environment — this guarantees the guard logic is covered.
- `_open_image` (the Pillow integration) is tested behind
  `pytest.importorskip("PIL")`, so it runs only when the `ocr` extra is
  installed and is skipped otherwise. It needs Pillow but NOT the `tesseract`
  binary.

## L-1 — Security headers

Add one HTTP middleware in `src/halal_scanner/api/app.py` that sets, on every
response:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`

```python
@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

HSTS (`Strict-Transport-Security`) is intentionally NOT set in the app: it only
matters over HTTPS and is best applied at the reverse proxy; setting it here
could break local HTTP development. Recorded as a proxy-level note.

## L-5 — Reject unexpected request fields

`ClassifyRequest` and `ScanBarcodeRequest` in `src/halal_scanner/api/schemas.py`
gain `model_config = ConfigDict(extra="forbid")`, so unknown JSON fields (e.g.
`is_admin`, `role`) are rejected with HTTP 422 instead of silently ignored.

```python
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

class ClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

class ScanBarcodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
```

Scope is limited to the two scanning request models. The auth/account request
models (register, login, etc.) are left for a later focused pass.

## Out of scope (remain open)

MED-1 (proxy-aware / Redis-backed rate limiting), MED-4 (already mitigated — see
above), MED-3 (LLM prompt-injection note — accepted risk, mitigations already in
place), HSTS-in-app, `extra="forbid"` on auth models, and disabling public
`/docs` in production. All stay recorded in `QA_SECURITY_FINDINGS.txt`.

## Testing (TDD, red → green)

`_ensure_within_pixel_cap` (new `tests/test_ocr.py` cases, no Pillow needed):
- dimensions within `max_pixels` → returns None (no raise).
- dimensions whose product exceeds a low `max_pixels` → raises `ValueError`.

`_open_image` (new `tests/test_ocr.py` cases, behind `pytest.importorskip("PIL")`):
- a small valid PNG (e.g. 10x10) within the cap → returns an image, no raise.
- a real 100x100 PNG with `max_pixels=9999` → raises `ValueError`.

Security headers (`tests/test_api.py`):
- `GET /health` response carries all three headers with the expected values.

`extra="forbid"` (`tests/test_api.py`):
- `POST /classify` with `{"ingredients": ["sugar"], "foo": 1}` → 422.
- `POST /scan-barcode` with `{"barcode": "0123456789", "foo": 1}` → 422.

Run: `.venv/Scripts/python -m pytest -q` (baseline on this branch: 137 passing).

## Conventions

Branch `sub-project-12-image-response-hardening` (stacked on SP11); spec here;
plan in `docs/superpowers/plans/`; TDD; `--no-ff` merge to `main` (after SP11);
delete the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
