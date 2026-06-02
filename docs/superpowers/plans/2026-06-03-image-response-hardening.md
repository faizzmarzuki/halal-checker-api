# Image & Response Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guard `/scan-image` against decompression-bomb images, add baseline security response headers, and reject unexpected fields on the scanning request models (MED-2, L-1, L-5 from the QA pass).

**Architecture:** A pure pixel-cap guard plus a Pillow-backed open helper in `ocr.py`; one FastAPI HTTP middleware in `app.py`; and `extra="forbid"` config on the two scanning request models in `schemas.py`. Pillow is an optional dependency, so its tests are gated behind `pytest.importorskip("PIL")`.

**Tech Stack:** FastAPI middleware, Pydantic v2 (`ConfigDict`), Pillow (optional `ocr` extra), pytest + `fastapi.testclient.TestClient`. Baseline on this branch (stacked on SP11): **137 passing**.

---

## File Structure

- `src/halal_scanner/ocr.py` — add `MAX_IMAGE_PIXELS`, `_ensure_within_pixel_cap`, `_open_image`; route `_default_backend` through `_open_image`.
- `src/halal_scanner/api/app.py` — add a `@app.middleware("http")` security-headers function.
- `src/halal_scanner/api/schemas.py` — add `model_config = ConfigDict(extra="forbid")` to `ClassifyRequest` and `ScanBarcodeRequest`.
- `tests/test_ocr.py` — pure guard tests (always run) + Pillow-gated `_open_image` tests.
- `tests/test_api.py` — security-headers test + two `extra="forbid"` rejection tests.

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: Decompression-bomb guard (MED-2)

**Files:**
- Modify: `src/halal_scanner/ocr.py`
- Test: `tests/test_ocr.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_ocr.py`, add `import io` and `import pytest` at the top (the file currently starts with `from halal_scanner.ocr import OcrEngine, parse_ingredients`). Then append:

```python
def test_ensure_within_pixel_cap_accepts_within_limit():
    from halal_scanner.ocr import _ensure_within_pixel_cap

    assert _ensure_within_pixel_cap(1000, 1000, max_pixels=1_000_000) is None


def test_ensure_within_pixel_cap_rejects_oversized():
    from halal_scanner.ocr import _ensure_within_pixel_cap

    with pytest.raises(ValueError):
        _ensure_within_pixel_cap(2000, 2000, max_pixels=1_000_000)


def test_open_image_within_cap_returns_image():
    pil_image = pytest.importorskip("PIL.Image")
    from halal_scanner.ocr import _open_image

    buf = io.BytesIO()
    pil_image.new("RGB", (10, 10)).save(buf, format="PNG")
    img = _open_image(buf.getvalue())
    assert img.width == 10 and img.height == 10


def test_open_image_rejects_decompression_bomb():
    pil_image = pytest.importorskip("PIL.Image")
    from halal_scanner.ocr import _open_image

    buf = io.BytesIO()
    pil_image.new("RGB", (100, 100)).save(buf, format="PNG")
    with pytest.raises(ValueError):
        _open_image(buf.getvalue(), max_pixels=9999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ocr.py -v`
Expected: the two `_ensure_within_pixel_cap` tests FAIL with `ImportError: cannot import name '_ensure_within_pixel_cap'`. The two `_open_image` tests will SKIP if Pillow is not installed, or FAIL on the import if it is — either is acceptable for the red step.

- [ ] **Step 3: Add the guard and helper**

In `src/halal_scanner/ocr.py`, replace the existing `_default_backend` function (currently lines ~19-26) with the constant, the two helpers, and the rewired backend:

```python
# Bound the decoded pixel area to defend against decompression bombs (MED-2).
# ~40 MP is generous for a real phone photo of a label; bombs are typically
# hundreds of MP. OcrEngine.extract_text already turns any failure into "".
MAX_IMAGE_PIXELS = 40_000_000


def _ensure_within_pixel_cap(
    width: int, height: int, max_pixels: int = MAX_IMAGE_PIXELS
) -> None:
    """Raise ValueError if the decoded pixel area would exceed the cap (MED-2)."""
    if width * height > max_pixels:
        raise ValueError(f"image {width}x{height} exceeds {max_pixels}px cap")


def _open_image(image_bytes: bytes, max_pixels: int = MAX_IMAGE_PIXELS):
    """Open image bytes with Pillow, rejecting oversized (bomb) images.

    Image.open is lazy (reads the header only), so width/height are available
    before the pixels are decoded — the check rejects a bomb before any large
    allocation happens.
    """
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    _ensure_within_pixel_cap(img.width, img.height, max_pixels)
    return img


def _default_backend(image_bytes: bytes) -> str:
    """Tesseract OCR backend. Imports are lazy so deps are optional."""
    import pytesseract

    return pytesseract.image_to_string(_open_image(image_bytes))
```

Leave the rest of the file (`OcrBackend` type alias, `OcrEngine`, `parse_ingredients`) unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ocr.py -v`
Expected: the two `_ensure_within_pixel_cap` tests PASS; the two `_open_image` tests PASS (if Pillow installed) or SKIP (if not). No failures.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/ocr.py tests/test_ocr.py
git commit -m "feat(ocr): cap decoded image pixels to block decompression bombs (MED-2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Security response headers (L-1)

**Files:**
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_security_headers_present():
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_security_headers_present -v`
Expected: FAIL with `KeyError: 'x-content-type-options'` (headers not set yet).

- [ ] **Step 3: Add the middleware**

In `src/halal_scanner/api/app.py`, add the middleware immediately after the `app = FastAPI(...)` block (which ends at the line with `)` around line 41), before the `HALAL_JWT_SECRET` check:

```python
@app.middleware("http")
async def _security_headers(request, call_next):
    """Set baseline security headers on every response (L-1)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

(HSTS is intentionally omitted — it belongs at the HTTPS reverse proxy, not in the app.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — the new header test green, all existing endpoint tests still pass (the middleware only adds headers, it does not alter bodies or status codes).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_api.py
git commit -m "feat(api): set nosniff / X-Frame-Options / Referrer-Policy headers (L-1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Reject unexpected request fields (L-5)

**Files:**
- Modify: `src/halal_scanner/api/schemas.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api.py`:

```python
def test_classify_rejects_unexpected_field():
    resp = client.post("/classify", json={"ingredients": ["sugar"], "foo": 1})
    assert resp.status_code == 422


def test_scan_barcode_rejects_unexpected_field():
    resp = client.post("/scan-barcode", json={"barcode": "0123456789", "foo": 1})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_classify_rejects_unexpected_field tests/test_api.py::test_scan_barcode_rejects_unexpected_field -v`
Expected: FAIL — extra fields are currently ignored, so `/classify` returns 200 and `/scan-barcode` proceeds to the lookup (404/200), not 422.

- [ ] **Step 3: Add `extra="forbid"` to the two scanning models**

In `src/halal_scanner/api/schemas.py`, add `ConfigDict` to the pydantic import (currently `from pydantic import BaseModel, Field, StringConstraints` after SP11):

```python
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
```

Add `model_config` as the first line inside `ClassifyRequest`:

```python
class ClassifyRequest(BaseModel):
    """Body for POST /classify."""
    # Reject unexpected JSON fields (e.g. is_admin/role) instead of ignoring
    # them silently (L-5).
    model_config = ConfigDict(extra="forbid")
    # min_length=1 => an empty list is rejected with HTTP 422 automatically.
    # max_length caps the list; each item is length-bounded too.
    ingredients: list[
        Annotated[str, StringConstraints(min_length=1, max_length=MAX_INGREDIENT_LEN)]
    ] = Field(..., min_length=1, max_length=MAX_INGREDIENTS)
    use_gemma: bool = True
    # When true, translate each ingredient to English before classifying.
    translate: bool = False
```

And as the first line inside `ScanBarcodeRequest`:

```python
class ScanBarcodeRequest(BaseModel):
    """Body for POST /scan-barcode."""
    # Reject unexpected JSON fields instead of ignoring them silently (L-5).
    model_config = ConfigDict(extra="forbid")
    # A real barcode is 6-14 digits. Anything else (letters, path traversal,
    # URL tricks) is rejected with HTTP 422 before any outbound call (HIGH-3).
    barcode: str = Field(..., pattern=r"^[0-9]{6,14}$")
    use_gemma: bool = True
    # When true, translate the product's ingredients to English before classifying.
    translate: bool = False
```

Leave the response models (`VerdictOut`, `BarcodeVerdictOut`, etc.) and `HealthOut` unchanged — `extra="forbid"` is only for inbound request bodies.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — the two new rejection tests green; all existing `/classify` and `/scan-barcode` tests still pass (they send only defined fields).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/schemas.py tests/test_api.py
git commit -m "feat(api): forbid unexpected fields on scanning request models (L-5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Full-suite verification & checkpoint

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (137 baseline + new tests; the two Pillow-gated tests pass or skip depending on whether the `ocr` extra is installed). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`:
- Update the test count.
- Add an SP12 entry under "What's built".
- Under "Already fixed", add MED-2 (decompression-bomb guard, via SP12), L-1 (security headers, via SP12), L-5 (extra="forbid" on scanning models, via SP12); note MED-4 was already mitigated by SP8's hash-based key lookup (no change needed).
- Update "Suggested next step" (e.g. MED-1 proxy-aware rate limiting, disable `/docs` in prod, `extra="forbid"` on auth models).

- [ ] **Step 3: Commit the checkpoint**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-image-response-hardening.md
git commit -m "docs(halal-scanner): SP12 done — MED-2, L-1, L-5 hardened

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `MAX_IMAGE_PIXELS = 40_000_000` (~40 MP) per the spec — generous for real photos, well below typical bomb sizes.
- Pillow is the optional `ocr` extra; never make a test hard-require it — gate Pillow tests with `pytest.importorskip("PIL")`. The pure `_ensure_within_pixel_cap` tests must run everywhere.
- Do NOT touch rate limiting (MED-1), auth-model configs, or `/docs` exposure — out of scope for SP12.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is stacked on SP11; final `--no-ff` merge to `main` happens after SP11 merges (handled after review, not in this plan).
