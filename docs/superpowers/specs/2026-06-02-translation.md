# Sub-project 5: Translation — Design Spec

**Date:** 2026-06-02
**Status:** Approved (autonomous continuation)
**Part of:** Halal Food Scanner — Sub-project 5 of 6
**Depends on:** Sub-projects 1–4 (engine, API, barcode, OCR)

## Purpose
Handle labels written in another language (Arabic, Malay, Spanish, …). Translate
each ingredient string to English **before** classification, so the rulebook —
which is keyed in English — can match it. No new classification logic.

## New module: `translator.py`
Reuses the already-running local Ollama/Gemma server (no new dependency).
- `class Translator`
  - `__init__(host="http://localhost:11434", model="gemma4:latest", timeout=30)`
    (same server defaults as `GemmaClient`).
  - `to_english(text: str) -> str` — translate to English. **Never raises**
    (mirrors `GemmaClient`); on any failure it returns the **original** text, so
    the pipeline degrades gracefully (worst case: classify the untranslated
    string). Empty/whitespace input returns unchanged.

## API change: opt-in `translate` flag
Translation is **off by default** (default `false`), keeping existing behaviour
deterministic and network-free unless explicitly requested.
- `POST /classify`: add `translate: bool = false` to the body.
- `POST /scan-barcode`: add `translate: bool = false` to the body.
- `POST /scan-image`: add `translate` query param (default `false`).

When `translate` is true, each parsed ingredient string is run through
`Translator.to_english` before being handed to the classifier.

A shared `Translator` is constructed once at module load. A small helper
`_translate_all(ingredients, enabled)` maps the list (identity when disabled).

## Dependencies
None new — `requests` and the Ollama server are already used by `GemmaClient`.

## Testing (TDD, network-free)
`tests/test_translator.py` (mock `requests.post`):
- success → returns the translated string.
- network error → returns the **original** text.
- empty/whitespace input → returned unchanged, no call made.

`tests/test_api.py` (patch the module-level `_translator.to_english`):
- `POST /classify {"ingredients":["tocino"], "translate": true, "use_gemma": false}`
  with the stub mapping `tocino -> lard` → `verdict == "haram"`, and the
  classified `input` is the translated `"lard"`.

No test hits the network; the translator is stubbed and classification stays
rulebook-only.

## Out of scope (later sub-projects)
Auth, rate limiting, language auto-detection, caching translations.
