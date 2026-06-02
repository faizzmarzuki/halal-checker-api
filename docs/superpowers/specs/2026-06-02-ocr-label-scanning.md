# Sub-project 4: OCR Label Scanning — Design Spec

**Date:** 2026-06-02
**Status:** Approved (autonomous continuation)
**Part of:** Halal Food Scanner — Sub-project 4 of 6
**Depends on:** Sub-projects 1–2 (engine + FastAPI layer)

## Purpose
Photograph an ingredient label and classify it: extract the text with OCR,
split it into ingredient strings, and feed them into the existing
`HalalClassifier`. No new classification logic.

## New module: `ocr.py`
```
src/halal_scanner/ocr.py
```
- `OcrBackend = Callable[[bytes], str]` — the pluggable OCR function type.
- `class OcrEngine`
  - `__init__(backend: OcrBackend | None = None)` — defaults to a Tesseract
    backend that is **lazily imported**, so the heavy OCR dependencies
    (`pytesseract`, `Pillow`) are only needed when actually running OCR, never
    for import or tests.
  - `extract_text(image_bytes: bytes) -> str` — returns the OCR'd text,
    stripped. **Never raises** (mirrors `GemmaClient`); returns `""` on any
    failure (bad image, OCR engine missing, etc.).
- `parse_ingredients(text: str) -> list[str]` — split OCR'd label text into
  ingredient strings on both newlines and commas/semicolons; strip; drop empties.

Keeping the backend injectable means tests pass a trivial fake function and need
**no** OCR binary or image library installed. The default backend is exercised
only in real use.

## API change: `POST /scan-image`
- Body: the **raw image bytes** (e.g. `Content-Type: image/jpeg`). Using the raw
  request body avoids a `python-multipart` dependency and is trivially testable.
- Query param: `use_gemma` (optional, default `true`).
- Behaviour:
  - OCR the bytes. If no text is found → **HTTP 422**
    `{ "detail": "Could not read any text from the image." }`.
  - Otherwise classify the parsed ingredients and return the verdict **plus**
    the `extracted_text`, so the caller can see what was read.
- Response (`ImageVerdictOut`): the `VerdictOut` fields **plus** `extracted_text`.

The shared `OcrEngine` is constructed once at module load.

## Dependencies
- No new **required** runtime deps (raw-body upload, lazy OCR import).
- New **optional** extra in pyproject for real OCR: `ocr = ["pytesseract", "Pillow"]`
  (the system `tesseract` binary must also be installed by the operator).

## Testing (TDD, binary-free)
`tests/test_ocr.py`:
- `OcrEngine(backend=fake).extract_text(b"x")` → stripped fake text.
- backend that raises → `extract_text` returns `""`.
- `parse_ingredients` splits newlines + commas, strips, drops empties.

`tests/test_api.py` (patch the module-level `_ocr_engine.extract_text`):
- `POST /scan-image` with stubbed text `"sugar\nlard"` → 200, `verdict == "haram"`,
  `extracted_text` echoed.
- `POST /scan-image` when OCR returns `""` → 422.

No test runs Tesseract or loads an image; the OCR engine is stubbed.

## Out of scope (later sub-projects)
Translation of the OCR'd text, auth, rate limiting.
