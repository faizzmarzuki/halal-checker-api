# Sub-project 11 — DoS / Input Hardening (Design)

Date: 2026-06-02

Closes two HIGH findings from the QA/security pass (`QA_SECURITY_FINDINGS.txt`):
HIGH-2 (no request-size limits → DoS / backend amplification) and HIGH-3
(unvalidated barcode interpolated into an outbound URL → path / SSRF risk).

## Goal

Make the scanning endpoints reject oversized and malformed input at the edge,
and ensure the only externally controlled URL segment (the barcode) cannot be
used to manipulate the outbound OpenFoodFacts request.

All limit values follow the QA findings' recommended defaults.

## HIGH-2 — Request-size limits

### 1. Ingredient list & per-string caps (schema-level, HTTP 422)

`ClassifyRequest.ingredients` in `api/schemas.py` gains an upper bound on both
the list length and each item's length:

```python
MAX_INGREDIENTS = 200
MAX_INGREDIENT_LEN = 200

ingredients: list[
    Annotated[str, StringConstraints(min_length=1, max_length=MAX_INGREDIENT_LEN)]
] = Field(..., min_length=1, max_length=MAX_INGREDIENTS)
```

- List capped at 200 items; each string 1–200 chars.
- Pydantic rejects violations with HTTP 422 automatically.
- Limits live as named module constants so they are easy to find and tune.

This also caps the LLM/translate fan-out amplification: at most 200 outbound
calls per request instead of an unbounded number.

### 2. Image body cap (`/scan-image`, HTTP 413)

Replace the uncapped `image_bytes = await request.body()` with a stream-and-cap
read:

- Iterate `request.stream()` chunk by chunk, accumulating up to
  `MAX_IMAGE_BYTES = 5 * 1024 * 1024` (5 MB). Exceeding the cap raises
  `HTTPException(413, "Image too large")`.
- The cap enforced while reading is authoritative — `Content-Length` is not
  trusted (it can be absent or spoofed).
- Fast path: if a `Content-Length` header is present **and** already exceeds the
  cap, reject with 413 before reading the body at all.

A small helper (e.g. `read_capped_body(request, max_bytes)`) keeps the streaming
logic out of the endpoint and unit-testable.

## HIGH-3 — Barcode validation / SSRF guard

### 3. Edge validation (schema-level, HTTP 422)

`ScanBarcodeRequest.barcode` gains a strict pattern:

```python
barcode: str = Field(..., pattern=r"^[0-9]{6,14}$")
```

A real barcode is 6–14 digits. Anything else (`abc`, `0000/../`, `@evil.com`,
too short/long) is rejected with 422 before any network call.

### 4. Defence-in-depth in `OpenFoodFactsClient.fetch`

The client is reusable and not guaranteed to be called only behind the schema,
so it hardens itself independently:

- Guard: if `barcode` does not match `^[0-9]{6,14}$`, return `None` immediately
  without making any request.
- URL-encode the path segment with `urllib.parse.quote(barcode, safe="")` when
  building the URL (belt-and-braces even though the guard already restricts it
  to digits).
- Pass `allow_redirects=False` to `requests.get` so a redirect response can
  never send the client to an attacker-chosen location.

## Out of scope (remain open for later sub-projects)

HIGH-1 (fail-closed in production), MED-1 (proxy-aware / shared rate limiting),
MED-2 (Pillow decompression-bomb guard), MED-4 (constant-time API-key compare),
and all LOW/INFO items. These stay recorded in `QA_SECURITY_FINDINGS.txt` and the
checkpoint.

## Testing (TDD, red → green)

`ClassifyRequest` / `/classify`:
- list of 201 items → 422; a 201-char ingredient string → 422.
- list of 200 valid items and a 200-char string → accepted.

`/scan-image`:
- body > 5 MB → 413 via the stream cap.
- `Content-Length` header > 5 MB → 413 fast-path reject.
- small valid body → processed normally.

`ScanBarcodeRequest` / `/scan-barcode`:
- `abc`, `0000/../../../admin?x=#`, `@evil.com/path`, `12345` (too short),
  16-digit (too long) → 422.
- valid digits (e.g. `0123456789`) → accepted.

`OpenFoodFactsClient.fetch` (mocked `requests`):
- valid barcode → URL is `.../api/v2/product/<quoted>.json` and the call passes
  `allow_redirects=False`.
- invalid barcode → returns `None` and `requests.get` is never called.

Run: `.venv/Scripts/python -m pytest -q` (baseline before this work: 122 passing).

## Conventions

Branch `sub-project-11-dos-input-hardening`; spec here; plan in
`docs/superpowers/plans/`; TDD; `--no-ff` merge to `main`; delete the branch.
Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
