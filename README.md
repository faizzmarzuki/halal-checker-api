# Halal Food Scanner

Classify food ingredients as **halal**, **haram** (non-halal), or **shubhah**
(doubtful). A deterministic English rulebook is the authority; everything else
(barcode lookup, OCR, translation, an optional local LLM) just feeds clean
ingredient text into that engine. Every verdict carries a disclaimer — this is a
decision aid, **not a religious ruling**.

## Architecture

```
                 barcode ──▶ OpenFoodFacts ─┐
  image ──▶ OCR (Tesseract) ────────────────┤
  raw ingredient list ──────────────────────┤─▶ [translate?] ─▶ HalalClassifier ─▶ verdict
                                              │      (Gemma)         │
                                              │                 rulebook (authority)
                                              │                 Gemma fallback (low-confidence)
```

The project was built in six sub-projects (specs in `docs/superpowers/specs/`):

1. **Classification engine** — `models`, `normalizer`, `rulebook`, `gemma`, `classifier`.
2. **FastAPI layer** — `POST /classify`, `GET /health`.
3. **OpenFoodFacts barcode lookup** — `POST /scan-barcode`.
4. **OCR label scanning** — `POST /scan-image`.
5. **Translation** — opt-in `translate` flag (foreign-language labels → English).
6. **Hardening** — optional API-key auth + in-memory rate limiting.

## API

| Method | Path           | Body / input                                   | Notes |
|--------|----------------|------------------------------------------------|-------|
| POST   | `/classify`    | `{"ingredients": [...], "use_gemma", "translate"}` | Classify a list of strings. |
| POST   | `/scan-barcode`| `{"barcode": "...", "use_gemma", "translate"}` | Look up ingredients on OpenFoodFacts. 404 if not found. |
| POST   | `/scan-image`  | raw image bytes; `?use_gemma=&translate=`      | OCR a label photo. 422 if no text read. |
| GET    | `/health`      | —                                              | Liveness; reports Ollama reachability. Always open. |
| GET    | `/docs`        | —                                              | Swagger UI. |

- `use_gemma` (default `true`): allow the local Gemma/Ollama fallback for
  ingredients missing from the rulebook. `false` => fully deterministic, no network.
- `translate` (default `false`): translate each ingredient to English (via the
  local Ollama server) before classifying.

## Configuration (environment variables)

| Var | Default | Effect |
|-----|---------|--------|
| `HALAL_API_KEYS`   | _(unset)_ | Comma-separated allowed keys. Unset => auth **off**. When set, send `X-API-Key`. |
| `HALAL_RATE_LIMIT` | `0`       | Max requests per window. `0` => limiting **off**. |
| `HALAL_RATE_WINDOW`| `60`      | Rate-limit window, seconds. |

Auth and rate limiting guard `/classify`, `/scan-barcode`, and `/scan-image`;
`/health` is always open.

## Install & run

```bash
cd halal-scanner
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
# Optional, for real OCR (also needs the system `tesseract` binary):
#   .venv/Scripts/python -m pip install -e ".[ocr]"

# Run the API
.venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
# open http://localhost:8000/docs
```

The Gemma fallback and translation expect a local [Ollama](https://ollama.com)
server (`gemma4:latest`); both degrade gracefully when it is unreachable.

## Test

```bash
.venv/Scripts/python -m pytest -q
```

All tests are network-free and binary-free: the LLM, OpenFoodFacts, and OCR
backends are stubbed, so the suite runs anywhere with no external services.
