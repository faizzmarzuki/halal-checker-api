# Sub-project 1: Halal Classification Engine — Design Spec

**Date:** 2026-06-01
**Status:** Approved design (pending user review of this document)
**Part of:** Halal Food Scanner (6 sub-project decomposition)

---

## 0. Context: where this fits

The full product is a "photograph a food product → get a halal verdict" tool, decomposed into
six independently-buildable sub-projects:

1. **CORE — Halal classification engine** ← *this spec*
2. API — FastAPI wrapper around the engine
3. Ingredient sourcing — translation (any language → English) + OpenFoodFacts DB lookup
4. OCR — read ingredient text from an uploaded photo
5. Vision (YOLOv8) — crop the label/name region before OCR (accuracy booster, optional)
6. Docs — teaching walkthrough + error log (maintained continuously, finalized here)

This spec covers **only Sub-project 1**. It is a pure Python library: ingredient strings in,
verdict out. No camera, OCR, translation, or web server.

### Product-wide decisions already made (for reference)
- **Goal:** learning project *and* a working product — optimize for both clarity and correctness.
- **Ingredient source (whole product):** hybrid — OCR the label first, fall back to OpenFoodFacts
  lookup by product name. (Relevant to Sub-projects 3 & 4, not this one.)
- **Verdict logic:** curated JAKIM-based rulebook is the authority; Gemma (via Ollama) is only
  consulted for ingredients the rulebook does not know, and its answers are always flagged
  low-confidence.
- **Runtime:** local Windows PC with GPU; everything offline via Ollama. Suggested model
  `gemma3:4b` (6–8 GB VRAM) or `gemma3:12b` (12 GB+).

---

## 1. Purpose & boundary

**Input:** a list of ingredient strings, already in English.
`["sugar", "gelatin", "E471", "soy lecithin"]`

**Output:** a per-ingredient classification plus one overall verdict, with reasons and citations.

Anything outside this (image handling, OCR, translation, HTTP) is explicitly **out of scope** for
this sub-project. Keeping the boundary tight is what makes the engine testable and easy to learn from.

---

## 2. The core concept: how *shubhah* is defined

Every ingredient has a **nature**, encoded in the rulebook:

| Nature | Meaning | Resolves to |
|---|---|---|
| `always_halal` | No animal/alcohol pathway (plant, mineral, synthetic). | `HALAL` regardless of source |
| `always_haram` | Intrinsically prohibited. | `HARAM` regardless of source |
| `source_dependent` | Could be halal **or** haram depending on origin. | depends on what the label discloses |

**Shubhah definition (for this engine):**
> An ingredient that is `source_dependent` AND whose origin is **not disclosed** by the label text.

This implements the jurisprudential principle of *mushtabihat* (matters of doubt). When the source
cannot be ascertained, the correct classification is **doubtful**, never an optimistic "halal."

### Resolving a `source_dependent` ingredient
The classifier inspects the ingredient string for a **source qualifier** (parenthetical or adjacent
words) and resolves using the rulebook entry's keyword lists:

```
"gelatin"                          → no clue           → SHUBHAH
"gelatin (fish)" / "halal gelatin" → halal_if matched  → HALAL
"pork gelatin" / "gelatin (pork)"  → haram_if matched  → HARAM
"mono- & diglycerides"             → no clue           → SHUBHAH
"mono- & diglycerides (vegetable)" → halal_if matched  → HALAL
"rennet (microbial)"               → halal_if matched  → HALAL
```

So plain `"gelatin"` with no disclosed source → **SHUBHAH** by design.

### Shubhah is a single level (+ reason)
There is one `SHUBHAH` status. Every shubhah (and every Gemma-sourced) result carries a **reason**
explaining *why* it is doubtful and *what would resolve it*, e.g.
*"Animal source not disclosed; would be halal if labeled fish/plant/halal-certified."*
Grading (low/medium/high doubt) is intentionally deferred — it can be added later without rework.

---

## 3. Components

Each is a small, single-purpose module under `src/halal_scanner/`.

### `models.py` — shared data shapes
- `Status` enum: `HALAL`, `HARAM`, `SHUBHAH`.
- `Source` enum: `RULEBOOK`, `GEMMA`.
- `Confidence` enum: `HIGH`, `LOW`.
- `IngredientResult` dataclass:
  `input`, `canonical`, `status`, `source`, `confidence`, `reason`, `citation`.
- `ScanVerdict` dataclass:
  `verdict` (Status), `ingredients` (list[IngredientResult]), `summary` (str), `disclaimer` (str).

### `normalizer.py` — canonicalize a raw ingredient string
- Lowercase, trim, collapse whitespace.
- Normalize E-number formats: `"E 471"`, `"e471"`, `"(E471)"` → `"e471"`.
- Map common synonyms/spellings to a canonical key (`"gelatine"` → `"gelatin"`).
- **Separate the source qualifier from the base name** so both are available to the classifier:
  `"gelatin (fish)"` → base `"gelatin"`, qualifier text `"fish"`.
- Pure functions, no I/O — trivially unit-testable.

### `rulebook.py` — load & query the knowledge base
- Loads `data/rulebook.yaml` once into memory.
- `lookup(canonical) -> RuleEntry | None`.
- A `RuleEntry` carries: `nature`, `default` status, `halal_if[]`, `haram_if[]`, `synonyms[]`,
  `reason`, `citation`.
- Synonyms are indexed so `"e441"` and `"gelatine"` both resolve to the `gelatin` entry.

### `gemma.py` — Ollama fallback (only for unknown ingredients)
- Thin wrapper over the Ollama HTTP API (`http://localhost:11434`).
- Sends a structured prompt asking for: nature, likely status, short reason.
- Parses the response into an `IngredientResult` with `source=GEMMA`, `confidence=LOW`.
- **Never** raises to the caller: on timeout/error/unparseable output it signals failure so the
  classifier can fall back to `SHUBHAH — could not verify`.
- Designed for injection/mocking so tests run offline and fast.

### `classifier.py` — the orchestrator
For each input string:
1. `normalize` → canonical base + qualifier.
2. `rulebook.lookup(base)`:
   - found & `always_halal`/`always_haram` → that status, `HIGH` confidence.
   - found & `source_dependent` → resolve via qualifier against `halal_if`/`haram_if`;
     no match → `default` (shubhah), `HIGH` confidence (we are confident it is *doubtful*).
   - not found → call `gemma`; on success `LOW` confidence; on failure → `SHUBHAH —
     could not verify`, `LOW` confidence.
3. Aggregate into `ScanVerdict` using **worst-status-wins**:
   - any `HARAM` → overall `HARAM` (non-halal)
   - else any `SHUBHAH` → overall `SHUBHAH`
   - else → `HALAL`
4. Attach a human-readable `summary` and the fixed `disclaimer`.

---

## 4. The rulebook (`data/rulebook.yaml`)

Human-readable, version-controlled, the real "knowledge" of the system. Entry shape:

```yaml
gelatin:
  nature: source_dependent
  default: shubhah
  synonyms: [gelatine, e441]
  halal_if: [fish, plant, "halal beef", "halal-certified", bovine-halal]
  haram_if: [pork, porcine, swine, lard]
  reason: "Animal collagen; permissibility depends on the animal and slaughter. Label discloses no source."
  citation: "JAKIM MS1500:2009"

lard:
  nature: always_haram
  reason: "Rendered pork fat."
  citation: "JAKIM MS1500:2009"

sugar:
  nature: always_halal
  reason: "Plant-derived; no prohibited pathway."
  citation: "General"
```

**Seed content** (researched during the build, each with a citation from JAKIM MS1500 / MUI /
GSO and other recognized bodies; sources logged): pork & porcine derivatives, lard, blood,
gelatin, L-cysteine (E920), carmine/cochineal (E120), rennet, mono- & diglycerides (E471),
glycerin/glycerol (E422), enzymes, "natural flavours", ethanol/alcohol, and the common
always-halal staples (sugar, salt, water, common plant oils, etc.). The file is designed to grow.

---

## 5. Error handling

- **Ollama unavailable / slow / bad output:** never crash. The affected ingredient becomes
  `SHUBHAH — could not verify (Gemma unavailable)`, `confidence=LOW`. The incident is recorded
  in `docs/ERRORS.md`.
- **Malformed rulebook YAML:** fail fast *at load time* with a clear message (a broken knowledge
  base is a programming error, not a runtime input error).
- **Empty / non-string ingredient inputs:** skipped with a logged note; do not abort the batch.

---

## 6. Testing (TDD — tests written first)

Framework: `pytest`. Gemma is **mocked** so the suite is fast and offline.

- `test_normalizer.py` — casing, whitespace, E-number formats, synonym mapping, qualifier split.
- `test_rulebook.py` — synonym indexing, lookups, malformed-file handling.
- `test_classifier.py` — the decision matrix:
  - `"lard"` → HARAM; `"sugar"` → HALAL; `"gelatin"` → SHUBHAH.
  - `"gelatin (fish)"` → HALAL; `"pork gelatin"` → HARAM.
  - worst-status-wins aggregation (mixed lists).
  - unknown ingredient + mocked Gemma success → LOW confidence result.
  - unknown ingredient + mocked Gemma failure → SHUBHAH could-not-verify.

---

## 7. Disclaimer (baked into every verdict)

> *"This is automated guidance, not a religious ruling. Verify with official halal certification
> (e.g. JAKIM) before relying on it."*

Given the real religious stakes, this is non-negotiable output, not optional.

---

## 8. Project layout & stack

```
halal-scanner/                     (new folder, separate from other sandbox projects)
  pyproject.toml                   deps: pyyaml, requests (ollama), pytest (dev)
  src/halal_scanner/
    __init__.py
    models.py
    normalizer.py
    rulebook.py
    gemma.py
    classifier.py
    data/rulebook.yaml
  tests/
    test_normalizer.py
    test_rulebook.py
    test_classifier.py
  docs/
    learn/                         teaching walkthrough (built up continuously)
    ERRORS.md                      error log (appended as we hit real errors)
```

- **Language:** Python 3.11+
- **Runtime deps:** `pyyaml` (rulebook), `requests` (Ollama HTTP).
- **Dev deps:** `pytest`.

---

## 9. Out of scope (explicitly deferred to later sub-projects)

- Translation of non-English ingredients (Sub-project 3).
- OpenFoodFacts lookup by product name (Sub-project 3).
- OCR / image handling (Sub-project 4).
- YOLOv8 region detection (Sub-project 5).
- HTTP API (Sub-project 2).
- Graded shubhah levels (possible future enhancement).

---

## 10. Success criteria

- `pytest` passes, covering the full decision matrix above.
- Calling the engine with a mixed ingredient list returns a correct `ScanVerdict` with
  per-ingredient reasons, citations, and the disclaimer.
- The engine never crashes on Ollama being down — it degrades to `SHUBHAH — could not verify`.
- A `docs/learn/` walkthrough explains each module and the *why* behind it.
