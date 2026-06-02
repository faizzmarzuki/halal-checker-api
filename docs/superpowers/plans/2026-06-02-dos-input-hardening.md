# DoS / Input Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject oversized/malformed input at the edge of the scanning endpoints and stop the barcode from being used to manipulate the outbound OpenFoodFacts URL (HIGH-2 + HIGH-3 from the QA pass).

**Architecture:** Two schema-level caps (Pydantic 422) for the ingredient list and the barcode; a streaming body-size cap (HTTP 413) for `/scan-image`; and defence-in-depth inside `OpenFoodFactsClient.fetch` (regex guard, URL-encode, no redirects).

**Tech Stack:** FastAPI, Pydantic v2 (`StringConstraints`, `Annotated`), `requests`, pytest + `fastapi.testclient.TestClient`. Baseline before this work: **122 passing**.

---

## File Structure

- `src/halal_scanner/api/schemas.py` — add list/per-string caps to `ClassifyRequest`; add `pattern` to `ScanBarcodeRequest.barcode`; module constants `MAX_INGREDIENTS`, `MAX_INGREDIENT_LEN`.
- `src/halal_scanner/api/app.py` — add `MAX_IMAGE_BYTES` constant + `read_capped_body()` helper; wire it into `scan_image`.
- `src/halal_scanner/openfoodfacts.py` — regex guard + `quote()` + `allow_redirects=False` in `fetch`.
- `tests/test_api.py` — endpoint tests for caps (422 / 413).
- `tests/test_limits.py` (new) — unit tests for `read_capped_body`.
- `tests/test_openfoodfacts.py` — tests for the URL-encoding, no-redirect, and guard behaviour.

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: Ingredient list & per-string caps

**Files:**
- Modify: `src/halal_scanner/api/schemas.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_classify_too_many_ingredients_rejected():
    resp = client.post("/classify", json={"ingredients": ["sugar"] * 201})
    assert resp.status_code == 422


def test_classify_overlong_ingredient_string_rejected():
    resp = client.post("/classify", json={"ingredients": ["x" * 201]})
    assert resp.status_code == 422


def test_classify_at_limits_accepted():
    resp = client.post(
        "/classify",
        json={"ingredients": ["x" * 200] * 200, "use_gemma": False},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_classify_too_many_ingredients_rejected tests/test_api.py::test_classify_overlong_ingredient_string_rejected -v`
Expected: FAIL — both currently return 200 (no upper bound).

- [ ] **Step 3: Add the caps**

In `src/halal_scanner/api/schemas.py`, update the imports and `ClassifyRequest`:

```python
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ..models import IngredientResult, ScanVerdict

# Request-size caps (HIGH-2): bound the list length and each item's length so a
# single request cannot exhaust memory or amplify into thousands of LLM calls.
MAX_INGREDIENTS = 200
MAX_INGREDIENT_LEN = 200


class ClassifyRequest(BaseModel):
    """Body for POST /classify."""
    # min_length=1 => an empty list is rejected with HTTP 422 automatically.
    # max_length caps the list; each item is length-bounded too.
    ingredients: list[
        Annotated[str, StringConstraints(min_length=1, max_length=MAX_INGREDIENT_LEN)]
    ] = Field(..., min_length=1, max_length=MAX_INGREDIENTS)
    use_gemma: bool = True
    # When true, translate each ingredient to English before classifying.
    translate: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS (new tests green; existing `/classify` tests still pass).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/schemas.py tests/test_api.py
git commit -m "feat(api): cap ingredient list length and per-string length (HIGH-2)"
```

---

## Task 2: Barcode edge validation

**Files:**
- Modify: `src/halal_scanner/api/schemas.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
import pytest


@pytest.mark.parametrize(
    "bad",
    ["abc", "0000/../../../admin?x=#", "@evil.com/path", "12345", "1" * 15],
)
def test_scan_barcode_invalid_rejected(bad):
    resp = client.post("/scan-barcode", json={"barcode": bad})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest "tests/test_api.py::test_scan_barcode_invalid_rejected" -v`
Expected: FAIL — these strings currently pass schema validation (only emptiness was checked).

- [ ] **Step 3: Add the pattern**

In `src/halal_scanner/api/schemas.py`, update `ScanBarcodeRequest`:

```python
class ScanBarcodeRequest(BaseModel):
    """Body for POST /scan-barcode."""
    # A real barcode is 6-14 digits. Anything else (letters, path traversal,
    # URL tricks) is rejected with HTTP 422 before any outbound call (HIGH-3).
    barcode: str = Field(..., pattern=r"^[0-9]{6,14}$")
    use_gemma: bool = True
    # When true, translate the product's ingredients to English before classifying.
    translate: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS. Existing barcode tests still pass — `test_scan_barcode_empty_barcode_rejected` (`""` fails the pattern → 422), `test_scan_barcode_classifies_product` and `test_scan_barcode_not_found_returns_404` use 13-digit barcodes.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/schemas.py tests/test_api.py
git commit -m "feat(api): validate barcode as 6-14 digits at the edge (HIGH-3)"
```

---

## Task 3: OpenFoodFactsClient.fetch defence-in-depth

**Files:**
- Modify: `src/halal_scanner/openfoodfacts.py`
- Test: `tests/test_openfoodfacts.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_openfoodfacts.py`:

```python
@patch("halal_scanner.openfoodfacts.requests.get")
def test_fetch_encodes_barcode_and_disables_redirects(mock_get):
    mock_get.return_value = _fake_response(
        {"status": 1, "product": {"product_name": "X", "ingredients_text": "sugar"}}
    )
    OpenFoodFactsClient().fetch("3017620422003")
    args, kwargs = mock_get.call_args
    assert args[0] == (
        "https://world.openfoodfacts.org/api/v2/product/3017620422003.json"
    )
    assert kwargs["allow_redirects"] is False


@patch("halal_scanner.openfoodfacts.requests.get")
def test_fetch_invalid_barcode_returns_none_without_request(mock_get):
    assert OpenFoodFactsClient().fetch("0000/../../../admin?x=#") is None
    mock_get.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_openfoodfacts.py::test_fetch_encodes_barcode_and_disables_redirects tests/test_openfoodfacts.py::test_fetch_invalid_barcode_returns_none_without_request -v`
Expected: FAIL — `allow_redirects` not passed (KeyError) and the invalid barcode currently reaches `requests.get`.

- [ ] **Step 3: Harden `fetch`**

In `src/halal_scanner/openfoodfacts.py`, update the imports and `fetch`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import requests

# A real barcode is 6-14 digits. Guard here too (defence in depth): this client
# is reusable and not guaranteed to sit behind the API's schema validation.
_BARCODE_RE = re.compile(r"^[0-9]{6,14}$")
```

Then the method body:

```python
    def fetch(self, barcode: str) -> Product | None:
        """Return a Product for the barcode, or None on any failure."""
        if not _BARCODE_RE.match(barcode):
            return None
        try:
            resp = requests.get(
                f"{self.host}/api/v2/product/{quote(barcode, safe='')}.json",
                timeout=self.timeout,
                allow_redirects=False,
            )
            resp.raise_for_status()
            payload = resp.json()
            # status == 1 means "product found"; 0 means not found.
            if payload.get("status") != 1:
                return None
            product = payload.get("product") or {}
            raw_text = str(product.get("ingredients_text", "")).strip()
            ingredients = split_ingredients(raw_text)
            if not ingredients:
                return None
        except Exception:
            return None
        return Product(
            barcode=barcode,
            name=str(product.get("product_name", "")).strip(),
            ingredients=ingredients,
            raw_text=raw_text,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_openfoodfacts.py -v`
Expected: PASS — existing tests use valid digit barcodes so the guard does not affect them.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/openfoodfacts.py tests/test_openfoodfacts.py
git commit -m "feat(off): guard, url-encode barcode and disable redirects (HIGH-3)"
```

---

## Task 4: Image body cap helper

**Files:**
- Create: `tests/test_limits.py`
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing unit tests for the helper**

Create `tests/test_limits.py`:

```python
import asyncio

import pytest
from fastapi import HTTPException

from halal_scanner.api.app import read_capped_body


class _FakeRequest:
    """Minimal stand-in for starlette Request: .headers + async .stream()."""

    def __init__(self, chunks, headers=None):
        self.headers = headers or {}
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def test_read_capped_body_under_limit_returns_bytes():
    req = _FakeRequest([b"abc", b"def"])
    body = asyncio.run(read_capped_body(req, max_bytes=1024))
    assert body == b"abcdef"


def test_read_capped_body_stream_exceeds_raises_413():
    # No Content-Length header -> the streaming cap is what catches it.
    req = _FakeRequest([b"x" * 600, b"x" * 600])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_capped_body(req, max_bytes=1000))
    assert exc.value.status_code == 413


def test_read_capped_body_content_length_fast_path_413():
    # Header alone trips the fast-path reject before any chunk is read.
    req = _FakeRequest([], headers={"content-length": "9999"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_capped_body(req, max_bytes=1000))
    assert exc.value.status_code == 413
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_limits.py -v`
Expected: FAIL — `ImportError: cannot import name 'read_capped_body'`.

- [ ] **Step 3: Add the helper and constant**

In `src/halal_scanner/api/app.py`, add the import near the top (with the other `fastapi` imports already present: `Depends, FastAPI, HTTPException, Request`) and define the constant + helper just after the clients are constructed (after line ~62):

```python
# Cap the raw image body to bound memory use on /scan-image (HIGH-2). 5 MB is
# generous for a phone photo of an ingredient label.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def read_capped_body(request: Request, max_bytes: int) -> bytes:
    """Read the request body, rejecting anything larger than max_bytes (HTTP 413).

    Content-Length is only trusted to reject early (it can be absent or wrong);
    the cap enforced while streaming is authoritative.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > max_bytes:
                raise HTTPException(status_code=413, detail="Image too large.")
        except ValueError:
            pass  # Unparseable header: ignore and rely on the streaming cap.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Image too large.")
    return bytes(body)
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_limits.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Wire the helper into `scan_image`**

In `src/halal_scanner/api/app.py`, replace the body-read line in `scan_image`:

```python
    image_bytes = await read_capped_body(request, MAX_IMAGE_BYTES)
```

(was `image_bytes = await request.body()`)

- [ ] **Step 6: Write the failing endpoint test**

Add to `tests/test_api.py`:

```python
def test_scan_image_too_large_returns_413():
    big = b"x" * (5 * 1024 * 1024 + 1)
    resp = client.post("/scan-image", content=big)
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — new 413 test green; existing small-body image tests (`test_scan_image_classifies_label`, `test_scan_image_no_text_returns_422`) still pass.

- [ ] **Step 8: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_limits.py tests/test_api.py
git commit -m "feat(api): cap /scan-image body size at 5MB (HIGH-2)"
```

---

## Task 5: Full-suite verification

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (122 baseline + new tests, ~133 total). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: under "Already fixed" add HIGH-2 and HIGH-3 (via SP11); remove them from "Still open"; update the test count.

- [ ] **Step 3: Commit the checkpoint**

```bash
git add docs/CHECKPOINT.md
git commit -m "docs(halal-scanner): SP11 done — HIGH-2 & HIGH-3 hardened"
```

---

## Notes for the implementer

- Limits follow the QA findings' recommended defaults: 200 ingredients, 200 chars each, 5 MB image, barcode `^[0-9]{6,14}$`.
- Do **not** add fixes for HIGH-1, MED-1, MED-2, MED-4, or the LOW items — they are explicitly out of scope and stay recorded for later sub-projects.
- All commit messages should carry the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Final integration: `--no-ff` merge `sub-project-11-dos-input-hardening` into `main` and delete the branch (done after review, not in this plan).
