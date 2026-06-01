# Halal Classification Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python library that takes a list of English ingredient strings and returns a per-ingredient halal/haram/shubhah classification plus an overall verdict, grounded in a curated JAKIM-based rulebook with an Ollama/Gemma fallback for unknown ingredients.

**Architecture:** Five small modules under `src/halal_scanner/`. `normalizer` cleans raw text; `rulebook` loads `data/rulebook.yaml` and matches ingredients (exact + synonym + word-subset); `classifier` orchestrates normalize → rulebook lookup → resolve source qualifiers → Gemma fallback → worst-status-wins aggregation; `gemma` is an injectable Ollama client (mocked in tests); `models` holds shared dataclasses/enums. No HTTP, OCR, translation, or image handling — those are later sub-projects.

**Tech Stack:** Python 3.13, `pyyaml`, `requests`, `pytest`. Commands use the project venv at `.venv/Scripts/python`.

---

## File Structure

```
halal-scanner/
  pyproject.toml                       # deps + pytest pythonpath=src config
  src/halal_scanner/
    __init__.py
    models.py                          # Status/Source/Confidence enums, IngredientResult, ScanVerdict
    normalizer.py                      # normalize(raw) -> canonical text string
    rulebook.py                        # Rulebook class: load YAML, RuleEntry, lookup()
    gemma.py                           # GemmaClient: Ollama fallback (injectable, mockable)
    classifier.py                      # HalalClassifier: orchestration + aggregation
    data/rulebook.yaml                 # curated knowledge base
  tests/
    test_normalizer.py
    test_rulebook.py
    test_classifier.py
  docs/
    learn/01-overview.md               # teaching walkthrough (built up continuously)
    ERRORS.md                          # error log (appended as real errors occur)
```

---

## Task 1: Project scaffold

**Files:**
- Create: `halal-scanner/pyproject.toml`
- Create: `halal-scanner/src/halal_scanner/__init__.py`
- Create: `halal-scanner/tests/__init__.py`
- Create: `halal-scanner/docs/ERRORS.md`

- [ ] **Step 1: Create the project directory and virtual environment**

Run (from `D:/Development/test-project`):
```bash
mkdir -p halal-scanner/src/halal_scanner/data halal-scanner/tests halal-scanner/docs/learn
cd halal-scanner && python -m venv .venv
```
Expected: a `.venv` folder is created inside `halal-scanner/`.

- [ ] **Step 2: Create `pyproject.toml`**

`halal-scanner/pyproject.toml`:
```toml
[project]
name = "halal-scanner"
version = "0.1.0"
description = "Halal/non-halal/shubhah classification engine"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "requests>=2.31"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Install dependencies into the venv**

Run (from `halal-scanner/`):
```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: pyyaml, requests, and pytest install without errors.

- [ ] **Step 4: Create empty package files**

`halal-scanner/src/halal_scanner/__init__.py`:
```python
"""Halal classification engine."""
```

`halal-scanner/tests/__init__.py`:
```python
```

- [ ] **Step 5: Create the error log**

`halal-scanner/docs/ERRORS.md`:
```markdown
# Error Log

Every real error hit during development, its cause, and the fix.

| Date | Where | Error | Cause | Fix |
|------|-------|-------|-------|-----|
```

- [ ] **Step 6: Verify pytest runs (no tests yet)**

Run (from `halal-scanner/`):
```bash
.venv/Scripts/python -m pytest
```
Expected: "no tests ran" (exit code 5) — confirms pytest + config work.

- [ ] **Step 7: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/pyproject.toml halal-scanner/src halal-scanner/tests halal-scanner/docs/ERRORS.md
git commit -m "chore: scaffold halal-scanner project"
```

---

## Task 2: Data models (`models.py`)

**Files:**
- Create: `halal-scanner/src/halal_scanner/models.py`
- Test: `halal-scanner/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`halal-scanner/tests/test_models.py`:
```python
from halal_scanner.models import (
    Status, Source, Confidence, IngredientResult, ScanVerdict,
)


def test_status_values():
    assert Status.HALAL.value == "halal"
    assert Status.HARAM.value == "haram"
    assert Status.SHUBHAH.value == "shubhah"


def test_ingredient_result_holds_fields():
    r = IngredientResult(
        input="Gelatin",
        canonical="gelatin",
        status=Status.SHUBHAH,
        source=Source.RULEBOOK,
        confidence=Confidence.HIGH,
        reason="source not disclosed",
        citation="JAKIM MS1500:2009",
    )
    assert r.status is Status.SHUBHAH
    assert r.source is Source.RULEBOOK


def test_scan_verdict_holds_list():
    v = ScanVerdict(
        verdict=Status.HALAL,
        ingredients=[],
        summary="ok",
        disclaimer="not a ruling",
    )
    assert v.verdict is Status.HALAL
    assert v.ingredients == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'halal_scanner.models'`.

- [ ] **Step 3: Write minimal implementation**

`halal-scanner/src/halal_scanner/models.py`:
```python
"""Shared data shapes used across the engine."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    """The three possible classifications."""
    HALAL = "halal"
    HARAM = "haram"
    SHUBHAH = "shubhah"


class Source(str, Enum):
    """Where a classification came from."""
    RULEBOOK = "rulebook"
    GEMMA = "gemma"


class Confidence(str, Enum):
    """How much to trust a classification."""
    HIGH = "high"
    LOW = "low"


@dataclass
class IngredientResult:
    """The classification of one ingredient."""
    input: str          # original string as given
    canonical: str      # normalized form used for lookup
    status: Status
    source: Source
    confidence: Confidence
    reason: str
    citation: str


@dataclass
class ScanVerdict:
    """The overall result for a list of ingredients."""
    verdict: Status
    ingredients: list[IngredientResult]
    summary: str
    disclaimer: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/src/halal_scanner/models.py halal-scanner/tests/test_models.py
git commit -m "feat: add data models for classification engine"
```

---

## Task 3: Normalizer (`normalizer.py`)

The normalizer turns any raw ingredient string into a clean, lowercase, space-separated "canonical text" used for matching. It removes punctuation, collapses whitespace, and joins E-number formats (`E 471` / `(E471)` → `e471`).

**Files:**
- Create: `halal-scanner/src/halal_scanner/normalizer.py`
- Test: `halal-scanner/tests/test_normalizer.py`

- [ ] **Step 1: Write the failing test**

`halal-scanner/tests/test_normalizer.py`:
```python
from halal_scanner.normalizer import normalize


def test_lowercases_and_trims():
    assert normalize("  Gelatin  ") == "gelatin"


def test_collapses_internal_whitespace():
    assert normalize("soy   lecithin") == "soy lecithin"


def test_strips_punctuation_to_spaces():
    assert normalize("mono- & diglycerides") == "mono diglycerides"


def test_parentheses_become_spaces():
    assert normalize("gelatin (fish)") == "gelatin fish"


def test_enumber_with_space_is_joined():
    assert normalize("E 471") == "e471"


def test_enumber_in_parentheses():
    assert normalize("L-cysteine (E920)") == "l cysteine e920"


def test_already_clean_enumber():
    assert normalize("e471") == "e471"


def test_empty_and_non_string():
    assert normalize("   ") == ""
    assert normalize(None) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_normalizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'halal_scanner.normalizer'`.

- [ ] **Step 3: Write minimal implementation**

`halal-scanner/src/halal_scanner/normalizer.py`:
```python
"""Turn a raw ingredient string into canonical matching text."""
from __future__ import annotations

import re

# Matches an E-number, optionally split by spaces: "e 471" -> groups ("471")
_ENUMBER_SPACED = re.compile(r"\be\s+(\d{3,4})\b")
# Any run of characters that is not a letter or digit.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# One or more spaces.
_WS = re.compile(r"\s+")


def normalize(raw: object) -> str:
    """Return a clean, lowercase, space-separated canonical form.

    Steps: coerce to str, lowercase, turn punctuation into spaces,
    rejoin spaced E-numbers ("e 471" -> "e471"), collapse whitespace.
    Returns "" for empty/None input.
    """
    if not isinstance(raw, str):
        return ""
    text = raw.lower()
    # Replace all punctuation with spaces first.
    text = _NON_ALNUM.sub(" ", text)
    # Rejoin spaced E-numbers (now "e 471" after punctuation removal).
    text = _ENUMBER_SPACED.sub(r"e\1", text)
    # Collapse whitespace and trim.
    text = _WS.sub(" ", text).strip()
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_normalizer.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/src/halal_scanner/normalizer.py halal-scanner/tests/test_normalizer.py
git commit -m "feat: add ingredient normalizer"
```

---

## Task 4: Rulebook (`rulebook.py` + `data/rulebook.yaml`)

The rulebook loads the YAML knowledge base and matches normalized text to an entry via exact match, synonym, or word-subset (so `"pork gelatin"` and `"gelatin"` both find the `gelatin` entry).

**Files:**
- Create: `halal-scanner/src/halal_scanner/data/rulebook.yaml`
- Create: `halal-scanner/src/halal_scanner/rulebook.py`
- Test: `halal-scanner/tests/test_rulebook.py`

- [ ] **Step 1: Create the seed rulebook**

> NOTE: citations use the JAKIM MS1500:2009 standard as the reference anchor. During execution, verify each ruling against JAKIM/MUI/GSO sources and log sources checked in `docs/ERRORS.md` / `docs/learn/`. The file is designed to grow.

`halal-scanner/src/halal_scanner/data/rulebook.yaml`:
```yaml
# Each entry key is a canonical (normalized) ingredient name.
# nature: always_halal | always_haram | source_dependent
# For source_dependent: halal_if / haram_if list keywords that resolve the doubt;
# if none are present in the ingredient text, the result is `default` (shubhah).

sugar:
  nature: always_halal
  reason: "Plant-derived; no prohibited pathway."
  citation: "General"

salt:
  nature: always_halal
  reason: "Mineral; no prohibited pathway."
  citation: "General"

water:
  nature: always_halal
  reason: "No prohibited pathway."
  citation: "General"

soy lecithin:
  nature: always_halal
  synonyms: [lecithin, e322]
  reason: "Commonly soy-derived emulsifier; plant origin."
  citation: "JAKIM MS1500:2009"

lard:
  nature: always_haram
  reason: "Rendered pork fat."
  citation: "JAKIM MS1500:2009"

pork:
  nature: always_haram
  synonyms: [porcine, swine, bacon, ham]
  reason: "Pig and pig derivatives are prohibited."
  citation: "JAKIM MS1500:2009"

blood:
  nature: always_haram
  reason: "Flowing blood is prohibited."
  citation: "JAKIM MS1500:2009"

ethanol:
  nature: always_haram
  synonyms: [alcohol]
  reason: "Intoxicant added as an ingredient."
  citation: "JAKIM MS1500:2009"

gelatin:
  nature: source_dependent
  default: shubhah
  synonyms: [gelatine, e441]
  halal_if: [fish, plant, "halal beef", "halal certified", bovine halal]
  haram_if: [pork, porcine, swine, lard]
  reason: "Animal collagen; permissibility depends on the animal and slaughter. Source not disclosed."
  citation: "JAKIM MS1500:2009"

rennet:
  nature: source_dependent
  default: shubhah
  halal_if: [microbial, vegetable, plant, "halal certified"]
  haram_if: [pork, porcine, swine]
  reason: "Enzyme for cheese-making; may be animal-derived. Source not disclosed."
  citation: "JAKIM MS1500:2009"

diglycerides:
  nature: source_dependent
  default: shubhah
  synonyms: [e471, "mono diglycerides", monoglycerides, "mono and diglycerides"]
  halal_if: [vegetable, plant, soy, palm]
  haram_if: [pork, porcine, lard]
  reason: "Emulsifier from fat; fat may be animal or plant. Source not disclosed."
  citation: "JAKIM MS1500:2009"

glycerin:
  nature: source_dependent
  default: shubhah
  synonyms: [glycerine, glycerol, e422]
  halal_if: [vegetable, plant, synthetic]
  haram_if: [pork, porcine, lard]
  reason: "May be animal-fat-derived. Source not disclosed."
  citation: "JAKIM MS1500:2009"

l cysteine:
  nature: source_dependent
  default: shubhah
  synonyms: [cysteine, e920]
  halal_if: [synthetic, microbial, "from feathers"]
  haram_if: ["human hair", pork]
  reason: "Amino acid; may be from hair/feathers. Source not disclosed."
  citation: "JAKIM MS1500:2009"

carmine:
  nature: source_dependent
  default: shubhah
  synonyms: [cochineal, e120, "carminic acid"]
  halal_if: []
  haram_if: []
  reason: "Insect-derived colour; scholars differ. Treated as doubtful."
  citation: "JAKIM MS1500:2009"
```

- [ ] **Step 2: Write the failing test**

`halal-scanner/tests/test_rulebook.py`:
```python
import pytest

from halal_scanner.rulebook import Rulebook, RuleEntry


@pytest.fixture
def book():
    return Rulebook.load_default()


def test_exact_lookup(book):
    e = book.lookup("sugar")
    assert isinstance(e, RuleEntry)
    assert e.nature == "always_halal"


def test_synonym_lookup(book):
    e = book.lookup("gelatine")
    assert e is not None
    assert e.key == "gelatin"


def test_enumber_synonym_lookup(book):
    e = book.lookup("e471")
    assert e is not None
    assert e.key == "diglycerides"


def test_word_subset_lookup(book):
    # "pork gelatin" should still find the gelatin entry.
    e = book.lookup("pork gelatin")
    assert e is not None
    assert e.key == "gelatin"


def test_unknown_returns_none(book):
    assert book.lookup("unobtanium") is None


def test_malformed_yaml_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [a, valid, mapping\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Rulebook.load_from(bad)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_rulebook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'halal_scanner.rulebook'`.

- [ ] **Step 4: Write minimal implementation**

`halal-scanner/src/halal_scanner/rulebook.py`:
```python
"""Load and query the curated halal knowledge base."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).parent / "data" / "rulebook.yaml"


@dataclass
class RuleEntry:
    """One ingredient ruling from the knowledge base."""
    key: str
    nature: str                      # always_halal | always_haram | source_dependent
    reason: str
    citation: str
    default: str = "shubhah"
    synonyms: list[str] = field(default_factory=list)
    halal_if: list[str] = field(default_factory=list)
    haram_if: list[str] = field(default_factory=list)


class Rulebook:
    """In-memory index of ingredient rulings with flexible matching."""

    def __init__(self, entries: list[RuleEntry]):
        self._entries = entries
        # Map every term (key + synonyms) to its entry.
        self._index: dict[str, RuleEntry] = {}
        for entry in entries:
            for term in [entry.key, *entry.synonyms]:
                self._index[term] = entry

    @classmethod
    def load_default(cls) -> "Rulebook":
        return cls.load_from(_DEFAULT_PATH)

    @classmethod
    def load_from(cls, path: Path) -> "Rulebook":
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed rulebook YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("Rulebook must be a mapping of ingredient -> ruling.")
        entries = []
        for key, data in raw.items():
            entries.append(RuleEntry(
                key=key,
                nature=data["nature"],
                reason=data.get("reason", ""),
                citation=data.get("citation", ""),
                default=data.get("default", "shubhah"),
                synonyms=data.get("synonyms", []) or [],
                halal_if=data.get("halal_if", []) or [],
                haram_if=data.get("haram_if", []) or [],
            ))
        return cls(entries)

    def lookup(self, text: str) -> RuleEntry | None:
        """Find the ruling for normalized `text`.

        Tries exact term match first, then word-subset match (every word of
        a term appears in the text), preferring the longest matching term.
        """
        if text in self._index:
            return self._index[text]
        tokens = set(text.split())
        best_len = -1
        best: RuleEntry | None = None
        for term, entry in self._index.items():
            term_tokens = term.split()
            if all(t in tokens for t in term_tokens):
                if len(term) > best_len:
                    best_len = len(term)
                    best = entry
        return best
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_rulebook.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/src/halal_scanner/rulebook.py halal-scanner/src/halal_scanner/data/rulebook.yaml halal-scanner/tests/test_rulebook.py
git commit -m "feat: add rulebook loader and seed knowledge base"
```

---

## Task 5: Gemma client (`gemma.py`)

A thin, injectable Ollama client used **only** for ingredients the rulebook does not know. It returns an `IngredientResult` (source=GEMMA, confidence=LOW) on success, or `None` on any error/timeout so the classifier can degrade gracefully. Tests mock the network entirely.

**Files:**
- Create: `halal-scanner/src/halal_scanner/gemma.py`
- Test: `halal-scanner/tests/test_gemma.py`

- [ ] **Step 1: Write the failing test**

`halal-scanner/tests/test_gemma.py`:
```python
from unittest.mock import MagicMock, patch

from halal_scanner.gemma import GemmaClient
from halal_scanner.models import Status, Source, Confidence


def _fake_response(payload_text):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"response": payload_text}
    return resp


@patch("halal_scanner.gemma.requests.post")
def test_classify_success(mock_post):
    mock_post.return_value = _fake_response(
        '{"status": "haram", "reason": "pork enzyme"}'
    )
    client = GemmaClient()
    result = client.classify("some unknown enzyme")
    assert result is not None
    assert result.status is Status.HARAM
    assert result.source is Source.GEMMA
    assert result.confidence is Confidence.LOW
    assert "pork enzyme" in result.reason


@patch("halal_scanner.gemma.requests.post", side_effect=Exception("conn refused"))
def test_classify_network_error_returns_none(mock_post):
    client = GemmaClient()
    assert client.classify("anything") is None


@patch("halal_scanner.gemma.requests.post")
def test_classify_bad_json_returns_none(mock_post):
    mock_post.return_value = _fake_response("this is not json")
    client = GemmaClient()
    assert client.classify("anything") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_gemma.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'halal_scanner.gemma'`.

- [ ] **Step 3: Write minimal implementation**

`halal-scanner/src/halal_scanner/gemma.py`:
```python
"""Ollama/Gemma fallback for ingredients not in the rulebook."""
from __future__ import annotations

import json

import requests

from .models import Confidence, IngredientResult, Source, Status

_PROMPT = (
    "You are a halal food analyst. Classify the single ingredient below as "
    "halal, haram, or shubhah (doubtful). Respond with ONLY a JSON object: "
    '{{"status": "halal|haram|shubhah", "reason": "short reason"}}.\n'
    "Ingredient: {ingredient}"
)


class GemmaClient:
    """Calls a local Ollama server. Never raises to the caller."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gemma3:4b",
        timeout: int = 30,
    ):
        self.host = host
        self.model = model
        self.timeout = timeout

    def classify(self, ingredient_text: str) -> IngredientResult | None:
        """Return a LOW-confidence result, or None on any failure."""
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": _PROMPT.format(ingredient=ingredient_text),
                    "stream": False,
                    "format": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = json.loads(resp.json()["response"])
            status = Status(payload["status"])
            reason = str(payload.get("reason", "")).strip()
        except Exception:
            return None
        return IngredientResult(
            input=ingredient_text,
            canonical=ingredient_text,
            status=status,
            source=Source.GEMMA,
            confidence=Confidence.LOW,
            reason=f"{reason} (Gemma estimate — unverified)",
            citation="Gemma (no citation)",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_gemma.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/src/halal_scanner/gemma.py halal-scanner/tests/test_gemma.py
git commit -m "feat: add Gemma/Ollama fallback client"
```

---

## Task 6: Classifier (`classifier.py`)

The orchestrator. For each ingredient: normalize → rulebook lookup → resolve `source_dependent` via keyword match → Gemma fallback for unknowns → aggregate with worst-status-wins.

**Files:**
- Create: `halal-scanner/src/halal_scanner/classifier.py`
- Test: `halal-scanner/tests/test_classifier.py`

- [ ] **Step 1: Write the failing test**

`halal-scanner/tests/test_classifier.py`:
```python
from halal_scanner.classifier import HalalClassifier
from halal_scanner.rulebook import Rulebook
from halal_scanner.models import (
    Status, Source, Confidence, IngredientResult,
)


class FakeGemma:
    """Stand-in for GemmaClient. Returns a preset result or None."""
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def classify(self, text):
        self.calls.append(text)
        return self.result


def make_classifier(gemma=None):
    return HalalClassifier(Rulebook.load_default(), gemma_client=gemma)


def test_always_halal():
    c = make_classifier()
    v = c.classify(["sugar"])
    assert v.verdict is Status.HALAL
    assert v.ingredients[0].confidence is Confidence.HIGH


def test_always_haram():
    c = make_classifier()
    v = c.classify(["lard"])
    assert v.verdict is Status.HARAM


def test_source_dependent_silent_is_shubhah():
    c = make_classifier()
    v = c.classify(["gelatin"])
    assert v.verdict is Status.SHUBHAH
    assert v.ingredients[0].source is Source.RULEBOOK
    assert v.ingredients[0].confidence is Confidence.HIGH


def test_source_dependent_halal_qualifier():
    c = make_classifier()
    v = c.classify(["gelatin (fish)"])
    assert v.ingredients[0].status is Status.HALAL


def test_source_dependent_haram_qualifier():
    c = make_classifier()
    v = c.classify(["pork gelatin"])
    assert v.ingredients[0].status is Status.HARAM


def test_worst_status_wins_haram_dominates():
    c = make_classifier()
    v = c.classify(["sugar", "gelatin", "lard"])
    assert v.verdict is Status.HARAM


def test_worst_status_wins_shubhah_over_halal():
    c = make_classifier()
    v = c.classify(["sugar", "gelatin"])
    assert v.verdict is Status.SHUBHAH


def test_unknown_uses_gemma():
    fake = FakeGemma(IngredientResult(
        input="frobnicate", canonical="frobnicate", status=Status.HARAM,
        source=Source.GEMMA, confidence=Confidence.LOW,
        reason="x", citation="Gemma",
    ))
    c = make_classifier(gemma=fake)
    v = c.classify(["frobnicate"])
    assert v.ingredients[0].source is Source.GEMMA
    assert fake.calls == ["frobnicate"]


def test_unknown_without_gemma_is_shubhah_unverified():
    c = make_classifier(gemma=FakeGemma(result=None))
    v = c.classify(["frobnicate"])
    assert v.ingredients[0].status is Status.SHUBHAH
    assert v.ingredients[0].confidence is Confidence.LOW
    assert "could not verify" in v.ingredients[0].reason.lower()


def test_empty_inputs_are_skipped():
    c = make_classifier()
    v = c.classify(["sugar", "", "   ", None])
    assert len(v.ingredients) == 1


def test_disclaimer_present():
    c = make_classifier()
    v = c.classify(["sugar"])
    assert "not a religious ruling" in v.disclaimer.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'halal_scanner.classifier'`.

- [ ] **Step 3: Write minimal implementation**

`halal-scanner/src/halal_scanner/classifier.py`:
```python
"""Orchestrate normalization, rulebook lookup, Gemma fallback, aggregation."""
from __future__ import annotations

from .models import Confidence, IngredientResult, ScanVerdict, Source, Status
from .normalizer import normalize
from .rulebook import RuleEntry, Rulebook

DISCLAIMER = (
    "This is automated guidance, not a religious ruling. "
    "Verify with official halal certification (e.g. JAKIM) before relying on it."
)


def _match_keyword(tokens: set[str], keywords: list[str]) -> str | None:
    """Return the first keyword whose words all appear in tokens."""
    for kw in keywords:
        if all(word in tokens for word in kw.split()):
            return kw
    return None


class HalalClassifier:
    def __init__(self, rulebook: Rulebook, gemma_client=None):
        self.rulebook = rulebook
        self.gemma_client = gemma_client

    def classify(self, ingredients: list) -> ScanVerdict:
        results = [
            self._classify_one(raw)
            for raw in ingredients
            if normalize(raw)  # skip empty / non-string
        ]
        verdict = self._aggregate(results)
        return ScanVerdict(
            verdict=verdict,
            ingredients=results,
            summary=self._summarize(verdict, results),
            disclaimer=DISCLAIMER,
        )

    def _classify_one(self, raw) -> IngredientResult:
        text = normalize(raw)
        entry = self.rulebook.lookup(text)
        if entry is not None:
            return self._from_rulebook(raw, text, entry)
        return self._from_gemma(raw, text)

    def _from_rulebook(self, raw, text, entry: RuleEntry) -> IngredientResult:
        if entry.nature == "always_halal":
            status, reason = Status.HALAL, entry.reason
        elif entry.nature == "always_haram":
            status, reason = Status.HARAM, entry.reason
        else:  # source_dependent
            tokens = set(text.split())
            if _match_keyword(tokens, entry.haram_if):
                status = Status.HARAM
                reason = f"Haram source named. {entry.reason}"
            elif _match_keyword(tokens, entry.halal_if):
                status = Status.HALAL
                reason = f"Halal source named. {entry.reason}"
            else:
                status = Status.SHUBHAH
                reason = entry.reason
        return IngredientResult(
            input=raw, canonical=text, status=status,
            source=Source.RULEBOOK, confidence=Confidence.HIGH,
            reason=reason, citation=entry.citation,
        )

    def _from_gemma(self, raw, text) -> IngredientResult:
        if self.gemma_client is not None:
            result = self.gemma_client.classify(text)
            if result is not None:
                return result
        return IngredientResult(
            input=raw, canonical=text, status=Status.SHUBHAH,
            source=Source.GEMMA, confidence=Confidence.LOW,
            reason="Unknown ingredient and could not verify (Gemma unavailable).",
            citation="N/A",
        )

    @staticmethod
    def _aggregate(results: list[IngredientResult]) -> Status:
        statuses = {r.status for r in results}
        if Status.HARAM in statuses:
            return Status.HARAM
        if Status.SHUBHAH in statuses:
            return Status.SHUBHAH
        return Status.HALAL

    @staticmethod
    def _summarize(verdict: Status, results: list[IngredientResult]) -> str:
        n = len(results)
        return f"Overall verdict: {verdict.value.upper()} based on {n} ingredient(s)."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: 11 passed.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all tests across all files pass (31 total).

- [ ] **Step 6: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/src/halal_scanner/classifier.py halal-scanner/tests/test_classifier.py
git commit -m "feat: add halal classifier orchestration"
```

---

## Task 7: End-to-end smoke check + live Gemma verification

Confirm the engine works as a real library and that the Gemma fallback talks to the running Ollama.

**Files:**
- Create: `halal-scanner/examples/demo.py`

- [ ] **Step 1: Write the demo script**

`halal-scanner/examples/demo.py`:
```python
"""Manual end-to-end demo of the classification engine."""
from halal_scanner.classifier import HalalClassifier
from halal_scanner.gemma import GemmaClient
from halal_scanner.rulebook import Rulebook


def main():
    engine = HalalClassifier(Rulebook.load_default(), gemma_client=GemmaClient())
    sample = ["sugar", "gelatin", "gelatin (fish)", "pork gelatin", "e471", "carmine"]
    verdict = engine.classify(sample)
    print(verdict.summary)
    for r in verdict.ingredients:
        print(f"  - {r.input:25} -> {r.status.value:8} [{r.source.value}/{r.confidence.value}] {r.reason}")
    print("\n" + verdict.disclaimer)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ensure a Gemma model is available**

Run: `ollama pull gemma3:4b`
Expected: model downloads (or "already exists"). If your VRAM is 12 GB+, you may instead pull `gemma3:12b` and update the `model=` default in `gemma.py`.

- [ ] **Step 3: Run the demo**

Run (from `halal-scanner/`): `.venv/Scripts/python examples/demo.py`
Expected output (rulebook entries are deterministic; `carmine` may route to Gemma or stay shubhah):
```
Overall verdict: HARAM based on 6 ingredient(s).
  - sugar          -> halal    [rulebook/high] ...
  - gelatin        -> shubhah  [rulebook/high] ...
  - gelatin (fish) -> halal    [rulebook/high] ...
  - pork gelatin   -> haram    [rulebook/high] ...
  - e471           -> shubhah  [rulebook/high] ...
  - carmine        -> shubhah  [rulebook/high] ...
```
If Ollama is not running, the engine must still complete (unknowns → "could not verify"). Log any error encountered to `docs/ERRORS.md`.

- [ ] **Step 4: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/examples/demo.py
git commit -m "chore: add end-to-end demo script"
```

---

## Task 8: Teaching documentation (`docs/learn/`)

Write the learner-facing walkthrough explaining each module and the reasoning behind it.

**Files:**
- Create: `halal-scanner/docs/learn/01-overview.md`

- [ ] **Step 1: Write the overview walkthrough**

`halal-scanner/docs/learn/01-overview.md` must cover, in plain language for someone new to Python/ML/APIs:
- What problem the engine solves and the halal/haram/shubhah model (the `nature` concept).
- A walk through each module (`models`, `normalizer`, `rulebook`, `gemma`, `classifier`) explaining what each function does and *why* it is written that way (e.g. why `normalize` turns punctuation into spaces; why the rulebook uses word-subset matching; why Gemma never raises; why worst-status-wins).
- How to add a new ingredient to `rulebook.yaml`.
- How to run the tests and the demo.

Write it as prose with short code excerpts pulled from the actual files (keep excerpts accurate to the committed code).

- [ ] **Step 2: Commit**

```bash
cd D:/Development/test-project
git add halal-scanner/docs/learn/01-overview.md
git commit -m "docs: add learner walkthrough for the classification engine"
```

---

## Self-Review Notes

**Spec coverage:**
- §1 purpose/boundary → Tasks 2–6 (pure library, list-in/verdict-out). ✓
- §2 shubhah/`nature` model → Task 4 (rulebook fields) + Task 6 (resolution logic + tests). ✓
- §3 components → models (T2), normalizer (T3), rulebook (T4), gemma (T5), classifier (T6). ✓
- §4 rulebook YAML → Task 4 seed file. ✓
- §5 error handling → Gemma returns None / degrade to shubhah (T5, T6); malformed YAML raises (T4). ✓
- §6 testing → tests written first in every task; full matrix in T6. ✓
- §7 disclaimer → Task 6 `DISCLAIMER` + `test_disclaimer_present`. ✓
- §8 layout/stack → Task 1. ✓
- §10 success criteria → Task 6 full-suite run + Task 7 smoke check. ✓

**Type consistency:** `Status/Source/Confidence/IngredientResult/ScanVerdict` (T2) are used with identical signatures in T5/T6. `Rulebook.load_default()`, `RuleEntry.key`, `Rulebook.lookup()` (T4) match their use in T6. `GemmaClient.classify()` returning `IngredientResult | None` (T5) matches the `FakeGemma` test double and classifier usage (T6). ✓

**Placeholder scan:** all code steps contain complete, runnable code; the only "fill-in" is Task 8 prose docs, which is inherently descriptive. ✓
