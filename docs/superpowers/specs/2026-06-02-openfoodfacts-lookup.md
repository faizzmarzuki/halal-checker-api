# Sub-project 3: OpenFoodFacts Barcode Lookup — Design Spec

**Date:** 2026-06-02
**Status:** Approved (autonomous continuation)
**Part of:** Halal Food Scanner — Sub-project 3 of 6
**Depends on:** Sub-project 1 (the `halal_scanner` engine) and Sub-project 2 (the FastAPI layer)

## Purpose
Let a caller scan a **product barcode** instead of typing ingredients. We look the
barcode up on the public OpenFoodFacts API, pull the product's `ingredients_text`,
split it into ingredient strings, and feed those into the existing `HalalClassifier`.
No new classification logic — just a new data source feeding the same engine.

## New module: `openfoodfacts.py`
```
src/halal_scanner/openfoodfacts.py
```
- `@dataclass Product { barcode: str, name: str, ingredients: list[str], raw_text: str }`
- `class OpenFoodFactsClient`
  - `__init__(host="https://world.openfoodfacts.org", timeout=10)`
  - `fetch(barcode: str) -> Product | None`
    - `GET {host}/api/v2/product/{barcode}.json`
    - On HTTP/network error, malformed JSON, `status != 1` (product not found),
      or empty/missing ingredients text → return `None`. **Never raises** (mirrors
      `GemmaClient`'s "never raise to the caller" contract).
    - On success → parse `product.ingredients_text` into a `Product`.
- `split_ingredients(text: str) -> list[str]`
  - Splits on commas, strips whitespace, drops empties. Keeps it deliberately
    simple — the engine's `normalizer` already cleans each string further.

## API change: `POST /scan-barcode`
- Request body: `{ "barcode": "3017620422003", "use_gemma": true }`
  - `barcode`: non-empty string.
  - `use_gemma`: optional, default `true` (same semantics as `/classify`).
- Behaviour:
  - Fetch the product. If `None` → **HTTP 404** `{ "detail": "Product not found or has no ingredient list." }`.
  - Otherwise classify `product.ingredients` and return the verdict **plus** the
    product context, so the client can show what was scanned.
- Response (`BarcodeVerdictOut`): the `VerdictOut` fields **plus** `barcode` and `product_name`.

The shared `OpenFoodFactsClient` is constructed once at module load, like the rulebook
and Gemma client.

## Dependencies
None new — `requests` is already a dependency.

## Testing (TDD, network-free)
`tests/test_openfoodfacts.py` (mock `requests.get`):
- success → `Product` with parsed `name` and `ingredients` list.
- `status: 0` (not found) → `None`.
- network error → `None`.
- missing/empty `ingredients_text` → `None`.
- `split_ingredients` splits, strips, and drops empties.

`tests/test_api.py` (mock the module-level client):
- `POST /scan-barcode` with a stubbed product → 200, classified verdict, echoes barcode + product_name.
- `POST /scan-barcode` when the client returns `None` → 404.
- `POST /scan-barcode` with empty barcode → 422.

No test hits the network; the client and the engine are both stubbed or rulebook-only.

## Out of scope (later sub-projects)
OCR, translation, image upload, auth, rate limiting, caching OpenFoodFacts responses.
