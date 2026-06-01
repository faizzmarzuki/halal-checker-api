# Sub-project 2: FastAPI Wrapper — Design Spec

**Date:** 2026-06-01
**Status:** Approved (decisions confirmed via questions)
**Part of:** Halal Food Scanner — Sub-project 2 of 6
**Depends on:** Sub-project 1 (the `halal_scanner` classification engine, merged to master)

## Purpose
Expose the existing `HalalClassifier` over HTTP. A thin transport layer — no new
classification logic. Lives inside the same `halal-scanner/` project.

## Endpoints
- `POST /classify`
  - Request body: `{ "ingredients": ["sugar", "gelatin", ...], "use_gemma": true }`
    - `ingredients`: a JSON array of strings (array only — caller splits labels). Must be non-empty.
    - `use_gemma`: optional, default `true`. When `false`, the engine runs rulebook-only
      (deterministic, no network); unknown ingredients become "could not verify" shubhah.
  - Response: the serialized `ScanVerdict`:
    `{ "verdict", "ingredients": [{input, canonical, status, source, confidence, reason, citation}], "summary", "disclaimer" }`
- `GET /health` → `{ "status": "ok", "ollama_available": bool }`. `ollama_available` is a
  short-timeout probe of the Ollama server (`GET {host}/api/tags`).
- `GET /docs` → FastAPI's auto Swagger UI (free).

## Structure
```
halal-scanner/src/halal_scanner/api/
  __init__.py
  schemas.py    # Pydantic request/response models
  app.py        # FastAPI app + handlers
halal-scanner/tests/test_api.py
```
- The `Rulebook` and a shared `GemmaClient` are constructed once at module load.
- Per request: build `HalalClassifier(rulebook, gemma_client=(client if use_gemma else None))`
  (construction is cheap — just stores references).
- Map the engine's dataclasses/enums to Pydantic models for clean JSON (enum `.value`).

## Dependencies (add to pyproject.toml)
- runtime: `fastapi`, `uvicorn[standard]`
- dev: `httpx` (required by FastAPI `TestClient`)

## Testing (TDD, network-free)
Use `fastapi.testclient.TestClient`:
- `POST /classify {"ingredients":["lard"]}` → 200, `verdict == "haram"`.
- `POST /classify {"ingredients":["gelatin"]}` → 200, `verdict == "shubhah"`.
- `POST /classify {"ingredients":["sugar","lard"]}` → `verdict == "haram"` (worst-status-wins).
- `POST /classify {"ingredients":["zzunknownzz"], "use_gemma": false}` → ingredient `status == "shubhah"`,
  reason contains "could not verify" (rulebook-only path, no network).
- `POST /classify {"ingredients":[]}` → 422 (validation: non-empty required).
- `GET /health` → 200, `status == "ok"`, `ollama_available` is a bool.
- Response includes the disclaimer string.

All `/classify` tests use rulebook ingredients or `use_gemma:false`, so no test hits the network.

## Run
```
cd halal-scanner
.venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
# open http://localhost:8000/docs
```

## Out of scope (later sub-projects)
Translation, OpenFoodFacts lookup, OCR, image upload, auth, rate limiting.
