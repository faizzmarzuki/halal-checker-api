# Halal Scanner: A Complete Learner's Walkthrough

This document explains the halal-scanner classification engine from first principles.
It is written for someone who can write basic Python but is new to idioms like
`Enum`, `dataclass`, regular expressions, and HTTP clients. Every code excerpt is
taken verbatim from the real source files.

---

## Table of Contents

1. [What this project is](#1-what-this-project-is)
2. [How the pieces fit together](#2-how-the-pieces-fit-together)
3. [Module-by-module walkthrough](#3-module-by-module-walkthrough)
   - [models.py](#31-modelspy--shared-data-shapes)
   - [normalizer.py](#32-normalizerpy--cleaning-ingredient-strings)
   - [rulebook.py](#33-rulebookpy--the-knowledge-base)
   - [gemma.py](#34-gemmappy--the-ai-fallback)
   - [classifier.py](#35-classifierpy--the-orchestrator)
4. [The rulebook is the knowledge base](#4-the-rulebook-is-the-knowledge-base)
5. [How to run it](#5-how-to-run-it)
6. [Design decisions and disclaimers](#6-design-decisions-and-disclaimers)

---

## 1. What This Project Is

When a Muslim consumer picks up a packaged food product, they need to know whether
the ingredients are **halal** (permissible), **haram** (prohibited), or
**shubhah** (doubtful — literally "resemblance to doubt" in Arabic).

The three statuses map to real-world situations:

| Status | Meaning | Example |
|--------|---------|---------|
| `halal` | Clearly permissible | Sugar, salt, water, plant oils |
| `haram` | Clearly prohibited | Lard, blood, ethanol added as an ingredient |
| `shubhah` | Doubtful — origin or process unclear | Gelatin with no source declared |

### The concept of "nature"

Not every ingredient is black-and-white. The engine models each ingredient's
**nature** as one of three values:

- **`always_halal`** — permissible regardless of context (e.g. sugar).
- **`always_haram`** — prohibited regardless of context (e.g. pork, blood).
- **`source_dependent`** — permissibility depends on where the ingredient came
  from (e.g. gelatin can be halal if from a fish, haram if from a pig).

### When does shubhah arise?

For a `source_dependent` ingredient the manufacturer sometimes declares the source
right on the label: "fish gelatin" or "pork gelatin". When they do, the engine can
resolve the doubt. When they write nothing but "gelatin", the source is unknown and
the ingredient is classified as **shubhah** — the safest honest answer.

### Where this fits in the bigger picture

This engine is **Sub-project 1** of a larger food-scanner system. Later sub-projects
will add:

- **OCR** — photograph a label and extract the text automatically.
- **Translation** — handle labels in Arabic, Malay, or other languages.
- **API layer** — expose the engine as a web service.

For now, the engine works purely with ingredient strings you provide directly.

---

## 2. How the Pieces Fit Together

Here is the journey from raw ingredient text to a final verdict:

```
  Input list of strings
  ["sugar", "pork gelatin", "e471"]
          |
          v
  +-----------------+
  |   normalize()   |  lowercase, strip punctuation, rejoin E-numbers
  +-----------------+
          |
          v  "sugar" / "pork gelatin" / "e471"
          |
          v
  +--------------------+
  | Rulebook.lookup()  |  exact match or word-subset match -> RuleEntry
  +--------------------+
          |
          +-- found? --> _from_rulebook()
          |                 resolve nature: always_halal / always_haram
          |                 or source_dependent:
          |                   scan haram_if keywords (conservative first)
          |                   then halal_if keywords
          |                   else -> shubhah
          |
          +-- not found? --> GemmaClient.classify()  (AI fallback, LOW confidence)
                                or shubhah if Gemma is unavailable
          |
          v
  IngredientResult (one per ingredient)
          |
          v
  +---------------------+
  |  _aggregate()       |  worst-status-wins:
  |                     |  any haram  -> HARAM
  |                     |  any shubhah -> SHUBHAH
  |                     |  all halal  -> HALAL
  +---------------------+
          |
          v
  ScanVerdict (overall verdict + per-ingredient list + disclaimer)
```

The entry point for callers is `HalalClassifier.classify(ingredients)`. Everything
else is an internal detail.

---

## 3. Module-by-Module Walkthrough

### 3.1 `models.py` — Shared Data Shapes

**File location:** `src/halal_scanner/models.py`

This file defines all the data types used by every other module. It has two
concerns: *enumerations* (a fixed set of named values) and *data classes* (simple
containers for structured data).

#### What is an `Enum`?

An `Enum` is Python's way of defining a fixed set of named constants that cannot be
confused with plain strings or integers. Consider this code from `models.py`:

```python
from enum import Enum

class Status(str, Enum):
    """The three possible classifications."""
    HALAL = "halal"
    HARAM = "haram"
    SHUBHAH = "shubhah"
```

**Breaking that down line by line:**

- `from enum import Enum` — imports the `Enum` base class from Python's standard
  library.
- `class Status(str, Enum):` — creates a new class called `Status` that inherits
  from *both* `str` and `Enum`. The `str` part is important: it means each member is
  also a proper string. So `Status.HALAL == "halal"` is `True`. Without the `str`
  parent you would have to write `Status.HALAL.value` to get the string. With it,
  the member itself behaves as its string value in comparisons and f-strings.
- `HALAL = "halal"` — declares a member whose name is `HALAL` and whose value is the
  string `"halal"`. The convention is ALL_CAPS for enum member names.

**Why use Enum instead of plain strings?**

If you used bare strings you could silently write `"Halal"` (capital H) and the
comparison would fail. With an Enum, typos are caught immediately because Python
raises a `ValueError` when you try to construct `Status("Halal")` — the value does
not exist. It also makes the code self-documenting: when a function returns a
`Status`, you immediately know there are only three possible values.

The file defines three enums for the same reason:

```python
class Source(str, Enum):
    RULEBOOK = "rulebook"
    GEMMA = "gemma"

class Confidence(str, Enum):
    HIGH = "high"
    LOW = "low"
```

`Source` records whether the classification came from the curated rulebook or the
AI model. `Confidence` records how much to trust it (rulebook lookups are `HIGH`,
AI guesses are `LOW`).

#### What is a `@dataclass`?

```python
from dataclasses import dataclass

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
```

A **dataclass** is a class whose only purpose is to hold data. Without the
`@dataclass` decorator you would need to write a `__init__` method manually:

```python
# Without @dataclass — tedious boilerplate:
class IngredientResult:
    def __init__(self, input, canonical, status, source, confidence, reason, citation):
        self.input = input
        self.canonical = canonical
        self.status = status
        # ... and so on
```

The `@dataclass` decorator reads the annotated fields and generates `__init__`
automatically. The `# original string as given` comments are just documentation
for the reader — Python ignores them at runtime.

**The `@` symbol** introduces a *decorator*. A decorator is a function that wraps
another function or class to add behaviour. `@dataclass` is a built-in decorator
from `dataclasses` that transforms the class.

`ScanVerdict` uses the same pattern but holds the overall result:

```python
@dataclass
class ScanVerdict:
    """The overall result for a list of ingredients."""
    verdict: Status
    ingredients: list[IngredientResult]
    summary: str
    disclaimer: str
```

`list[IngredientResult]` is a **type annotation** — it says this field should be a
list of `IngredientResult` objects. Python does not enforce this at runtime, but it
helps editors and human readers understand the expected shape.

#### What is `from __future__ import annotations`?

Both files start with this line:

```python
from __future__ import annotations
```

This is a compatibility import that tells Python to treat all type annotations as
strings rather than evaluating them immediately. It allows you to write
`list[IngredientResult]` in a class that was defined earlier in the same file
without getting a `NameError`. On Python 3.11+ (which this project requires) it is
mostly harmless, but it is a common idiom worth knowing.

---

### 3.2 `normalizer.py` — Cleaning Ingredient Strings

**File location:** `src/halal_scanner/normalizer.py`

Before looking up an ingredient in the rulebook, every string must be converted to
a consistent lowercase, punctuation-free form. "Gelatin", "GELATIN", "Gelatin (E441)"
and "gelatine" should all resolve to the same thing. That is what the normalizer does.

#### The three compiled regular expressions

```python
import re

_ENUMBER_SPACED = re.compile(r"\be\s+(\d{3,4})\b")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")
```

**Why `re.compile`?**

`re.compile` pre-processes the pattern string into an internal representation once.
If you called `re.sub(pattern, ...)` inside a loop that runs thousands of times,
Python would re-parse the pattern every iteration. Compiling once and storing the
result in a module-level variable is faster and cleaner.

**What do the patterns mean?**

Regular expressions are a mini-language for describing text patterns. Here is each
one explained:

**`_ENUMBER_SPACED = re.compile(r"\be\s+(\d{3,4})\b")`**

This matches an E-number that has been split by a space, like "e 471".

| Part | Meaning |
|------|---------|
| `\b` | Word boundary — the match must start at the edge of a word |
| `e` | The literal letter "e" |
| `\s+` | One or more whitespace characters (space, tab, etc.) |
| `(` … `)` | A *capture group* — whatever matches inside is remembered |
| `\d{3,4}` | Three or four consecutive digits (E-numbers are 3–4 digits) |
| `\b` | Word boundary at the end |

The `r` prefix (`r"\b..."`) makes this a *raw string*. In a normal Python string,
`\b` would be a backspace character. In a raw string, backslashes are passed through
as-is, which is what `re` expects.

**`_NON_ALNUM = re.compile(r"[^a-z0-9]+")`**

This matches any run of one or more characters that are *not* a lowercase letter or
digit. The `[^...]` notation means "anything except what is listed".

- `[a-z0-9]` — lowercase letters or digits.
- `[^a-z0-9]` — anything that is NOT a lowercase letter or digit.
- `+` — one or more of them in a row.

So brackets, commas, hyphens, parentheses — anything that is not a letter or digit
— will be captured by this pattern.

**`_WS = re.compile(r"\s+")`**

Matches one or more whitespace characters. Used at the end to collapse multiple
spaces into one.

#### The `normalize` function — a concrete trace

```python
def normalize(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.lower()
    text = _NON_ALNUM.sub(" ", text)
    text = _ENUMBER_SPACED.sub(r"e\1", text)
    text = _WS.sub(" ", text).strip()
    return text
```

Let us trace `"L-cysteine (E920)"` through every step:

| Step | Code | Value after step |
|------|------|-----------------|
| Guard | `isinstance(raw, str)` → `True`, continue | `"L-cysteine (E920)"` |
| Lowercase | `raw.lower()` | `"l-cysteine (e920)"` |
| Remove non-alnum | `_NON_ALNUM.sub(" ", text)` | `"l cysteine  e920 "` |
| Rejoin spaced E-numbers | `_ENUMBER_SPACED.sub(r"e\1", text)` | `"l cysteine  e920 "` *(no match here — "e920" has no space)* |
| Collapse whitespace | `_WS.sub(" ", text).strip()` | `"l cysteine e920"` |

Final result: `"l cysteine e920"`.

Now a slightly different input, `"E 920"` (with a space between E and 920):

| Step | Value after step |
|------|-----------------|
| Guard | pass |
| Lowercase | `"e 920"` |
| Remove non-alnum | `"e 920"` *(space is non-alnum, but spaces are allowed by `[^a-z0-9]`... wait — space IS matched)* → `"e 920"` becomes `"e  920"` — actually, the hyphen was the only non-alnum, so this stays `"e 920"` |
| Rejoin E-number | `_ENUMBER_SPACED` matches `"e 920"` → replaced with `"e920"` |
| Collapse | `"e920"` |

This matters because the rulebook indexes `e920` as a synonym for `l cysteine`.

**Why `isinstance(raw, str)` guards non-strings?**

The function signature says `raw: object` — the most general possible type. In
Python, type annotations are not enforced at runtime. A caller could pass `None`,
`42`, or a list by mistake. Calling `.lower()` on `None` would raise an
`AttributeError`. The guard catches that early and returns an empty string, which
the classifier then skips:

```python
# In classifier.py — empty strings are silently filtered:
results = [
    self._classify_one(raw)
    for raw in ingredients
    if normalize(raw)   # falsy (empty string "") is skipped
]
```

An empty string is *falsy* in Python — `if ""` evaluates to `False`. So any
ingredient that normalizes to nothing is quietly ignored.

---

### 3.3 `rulebook.py` — The Knowledge Base

**File location:** `src/halal_scanner/rulebook.py`

The rulebook module has two parts: `RuleEntry` (one row of knowledge) and
`Rulebook` (the in-memory index that lets you query that knowledge quickly).

#### `RuleEntry` — one ingredient's ruling

```python
from dataclasses import dataclass, field

@dataclass
class RuleEntry:
    key: str
    nature: str                      # always_halal | always_haram | source_dependent
    reason: str = ""
    citation: str = ""
    default: str = "shubhah"
    synonyms: list[str] = field(default_factory=list)
    halal_if: list[str] = field(default_factory=list)
    haram_if: list[str] = field(default_factory=list)
```

Most fields have default values (`= ""`), meaning callers do not have to provide
them. `synonyms`, `halal_if`, and `haram_if` use `field(default_factory=list)` —
this deserves explanation.

**Why `field(default_factory=list)` instead of `= []`?**

In Python, a mutable default (like `[]`) is shared across all instances. If you
wrote `synonyms: list = []` and then mutated the list on one instance, the change
would appear on every other instance too — a notorious Python gotcha. The
`default_factory=list` tells the dataclass to call `list()` fresh for each new
instance, so every `RuleEntry` gets its own independent list.

#### How the YAML is loaded

```python
import yaml
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parent / "data" / "rulebook.yaml"
```

`Path(__file__)` is the path to `rulebook.py` itself. `.parent` moves up one
directory to `halal_scanner/`. Then `/ "data" / "rulebook.yaml"` appends path
segments. The `/` operator on `Path` objects constructs file paths — it does not
divide numbers. This works on Windows and Linux alike because `Path` handles the
separator differences.

```python
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
            ...
        ))
    return cls(entries)
```

**`@classmethod`** — a method that receives the *class* itself (`cls`) as its first
argument instead of an instance (`self`). It is called as `Rulebook.load_from(path)`
rather than `some_rulebook_instance.load_from(path)`. This pattern is used as a
named constructor — a second way to create a `Rulebook` besides `__init__`.

**`yaml.safe_load`** — parses the YAML file and returns Python objects (dicts,
lists, strings). It is `safe_load` rather than `load` because `yaml.load` can
execute arbitrary Python code embedded in the YAML file (a security risk).
`safe_load` forbids those constructs.

**`data.get("reason", "")`** — `dict.get(key, default)` returns the value for
`key` if it exists, or `default` if not. This is safer than `data["reason"]` which
would raise `KeyError` if the YAML entry omits that field.

**`f"..."` strings** — an f-string interpolates variables directly into the string
using `{variable}` placeholders. `f"Malformed rulebook YAML: {exc}"` inserts the
exception message.

#### The `_index` dictionary and why it exists

```python
def __init__(self, entries: list[RuleEntry]):
    self._entries = entries
    self._index: dict[str, RuleEntry] = {}
    for entry in entries:
        for term in [entry.key, *entry.synonyms]:
            self._index[term] = entry
```

When the `Rulebook` is created, it builds `_index`, a dictionary that maps every
known term (the entry's main key AND all its synonyms) to the same `RuleEntry`.

The `*entry.synonyms` syntax is an **unpacking operator**. It spreads the list
`entry.synonyms` into individual items. So if `entry.key = "gelatin"` and
`entry.synonyms = ["gelatine", "e441"]`, then:

```python
[entry.key, *entry.synonyms]
# evaluates to:
["gelatin", "gelatine", "e441"]
```

All three terms now point to the same `RuleEntry` in `_index`. This means whether
a label says "gelatin", "gelatine", or "e441", the lookup finds the same ruling.

The `_` prefix on `_index` is a Python convention meaning "internal — do not use
this directly from outside the class". It is not enforced by the language; it is a
signal to readers.

#### The `lookup` function — exact match then word-subset match

```python
def lookup(self, text: str) -> RuleEntry | None:
    if text in self._index:
        return self._index[text]
    tokens = set(text.split())
    matches = [
        term for term in self._index
        if all(word in tokens for word in term.split())
    ]
    if not matches:
        return None
    winner = max(matches, key=lambda t: (len(t.split()), len(t), t))
    return self._index[winner]
```

**Step 1 — Exact match.** If the full normalized ingredient string is in `_index`,
return it immediately. "sugar" → instant hit.

**Step 2 — Word-subset match.** If there is no exact match, split the input into
individual words (`tokens`) and try every indexed term. A term matches if all of
*its* words appear somewhere in the input's word set. This is a list comprehension:

```python
matches = [
    term for term in self._index
    if all(word in tokens for word in term.split())
]
```

Read this as: "Build a list of every `term` in the index, but only include a term
if every word in that term appears in the input's tokens."

Example: input is `"pork gelatin"`, so `tokens = {"pork", "gelatin"}`.

- Term `"gelatin"` → words `["gelatin"]` → is `"gelatin"` in `tokens`? Yes → match.
- Term `"pork"` → words `["pork"]` → is `"pork"` in `tokens`? Yes → match.
- Term `"soy lecithin"` → words `["soy", "lecithin"]` → is `"soy"` in tokens? No → skip.

Both `"gelatin"` and `"pork"` match. We need to pick one.

**Step 3 — Pick the most specific match.**

```python
winner = max(matches, key=lambda t: (len(t.split()), len(t), t))
```

`max(iterable, key=fn)` returns the item for which `fn(item)` is largest. The key
here is a **lambda** — an anonymous one-line function. `lambda t: (...)` defines a
function with one argument `t` that returns the tuple on the right.

For each candidate term `t`, the tuple is:
1. `len(t.split())` — number of words in the term (prefer more words).
2. `len(t)` — character length of the term (tiebreak: prefer longer).
3. `t` — the term itself as a string (tiebreak: alphabetical).

Python compares tuples element by element (lexicographic ordering). So a 2-word
term always beats a 1-word term. Among 1-word terms, the longer one wins.

Applied to our example:

| Term | `len(t.split())` | `len(t)` | `t` |
|------|-----------------|----------|-----|
| `"pork"` | 1 | 4 | `"pork"` |
| `"gelatin"` | 1 | 7 | `"gelatin"` |

Both have 1 word. `"gelatin"` has 7 characters vs `"pork"`'s 4. So `"gelatin"`
wins. The classifier then resolves the ruling: `gelatin` is `source_dependent`,
and `"pork"` appears in `haram_if`, so the final status is **HARAM**.

This is intentional: we want the most specific ingredient-focused entry (gelatin's
full ruling, including its haram sources) rather than the bare `pork` always_haram
entry. Both lead to HARAM here, but for an ingredient like "vegetable gelatin" the
full gelatin entry correctly resolves it as HALAL, while the `pork` entry (if it
somehow won) would not match at all.

**`RuleEntry | None`** — the return type uses a pipe `|` to mean "either a
`RuleEntry` or `None`". This is Python 3.10+ syntax for union types. The `None`
case means the ingredient was not found in the rulebook at all.

---

### 3.4 `gemma.py` — The AI Fallback

**File location:** `src/halal_scanner/gemma.py`

When the rulebook has no entry for an ingredient, the engine tries a local AI
model (Gemma, running via Ollama) as a low-confidence fallback.

#### The prompt template

```python
_PROMPT = (
    "You are a halal food analyst. Classify the single ingredient below as "
    "halal, haram, or shubhah (doubtful). Respond with ONLY a JSON object: "
    '{{"status": "halal|haram|shubhah", "reason": "short reason"}}.\n'
    "Ingredient: {ingredient}"
)
```

This is a multi-line string created by placing string literals next to each other
in parentheses — Python joins them automatically. `{{` and `}}` inside an
f-string template are escaped braces that produce literal `{` and `}` in the
output (needed because the AI must return JSON, which uses braces).

Later the prompt is formatted with the actual ingredient:

```python
_PROMPT.format(ingredient=ingredient_text)
```

`str.format()` replaces `{ingredient}` with the value of `ingredient_text`.

#### What is an HTTP POST to Ollama?

Ollama is a local server that hosts AI models. It exposes a REST API — a set of
web-style endpoints you can call with standard HTTP. The engine calls it like this:

```python
import requests

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
```

- `requests.post(url, json=...)` — sends an HTTP POST request to the URL. The
  `json=` argument automatically serializes the Python dict to JSON and sets the
  correct `Content-Type` header.
- `f"{self.host}/api/generate"` — builds the full URL from the host
  (`http://localhost:11434`) and the path (`/api/generate`).
- `"stream": False` — tells Ollama to return the complete response in one go rather
  than streaming tokens one at a time.
- `"format": "json"` — instructs Ollama/Gemma to produce only valid JSON output.
  Without this the model might add conversational text around the JSON.
- `timeout=self.timeout` — if the server takes longer than 30 seconds, `requests`
  raises a `Timeout` exception rather than waiting forever.
- `resp.raise_for_status()` — if the HTTP response code indicates an error (4xx or
  5xx), this raises an exception. Without it, a failed request would silently return
  a broken response.
- `resp.json()["response"]` — Ollama wraps the model output in a JSON envelope. The
  actual generated text is inside the `"response"` key.
- `json.loads(...)` — parses the model's JSON string into a Python dict.

#### Why `except Exception: return None`?

```python
try:
    resp = requests.post(...)
    ...
    status = Status(payload["status"])
    reason = str(payload.get("reason", "")).strip()
except Exception:
    return None
```

The `except Exception:` clause catches *any* exception — network errors, timeouts,
the model being offline, malformed JSON, an unexpected status string, anything.
Instead of crashing the whole classification run, the method returns `None`.

This pattern is called **graceful degradation**: when the optional component
(Gemma) fails, the system falls back to a safe default (shubhah) rather than
raising an error to the user. The caller in `classifier.py` handles `None`:

```python
def _from_gemma(self, raw, text) -> IngredientResult:
    if self.gemma_client is not None:
        result = self.gemma_client.classify(text)
        if result is not None:
            return result
    return IngredientResult(
        ...
        status=Status.SHUBHAH,
        reason="Unknown ingredient and could not verify (Gemma unavailable).",
        ...
    )
```

The AI is genuinely optional. The rulebook-only path is the reliable, auditable one.

The default model is `gemma4:latest`:

```python
def __init__(
    self,
    host: str = "http://localhost:11434",
    model: str = "gemma4:latest",
    timeout: int = 30,
):
```

All three parameters have default values, so `GemmaClient()` with no arguments is
a valid call. To use a different model, pass `GemmaClient(model="gemma4:31b-cloud")`.

---

### 3.5 `classifier.py` — The Orchestrator

**File location:** `src/halal_scanner/classifier.py`

The classifier is the top-level glue. Its public method is `classify(ingredients)`.
Every other method is an internal detail, signalled by the `_` prefix.

#### The `DISCLAIMER` constant

```python
DISCLAIMER = (
    "This is automated guidance, not a religious ruling. "
    "Verify with official halal certification (e.g. JAKIM) before relying on it."
)
```

Every `ScanVerdict` carries this string. It is a module-level constant (not inside
any class) because it never changes.

#### Classifying one ingredient — the `_from_rulebook` branch

```python
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
```

Notice the order for `source_dependent` ingredients: **`haram_if` is checked
BEFORE `halal_if`**. This is deliberate and conservative. If an ingredient text
somehow contained both a haram keyword and a halal keyword (which should not happen
in practice, but could appear in a badly-formatted label), the engine takes the
worse outcome. Food safety errs on the side of caution.

`status, reason = Status.HALAL, entry.reason` is **tuple unpacking** — it assigns
both variables in one line. It is shorthand for:
```python
status = Status.HALAL
reason = entry.reason
```

#### `_match_keyword` — word-set matching for qualifiers

```python
def _match_keyword(tokens: set[str], keywords: list[str]) -> str | None:
    """Return the first keyword whose words all appear in tokens."""
    for kw in keywords:
        if all(word in tokens for word in kw.split()):
            return kw
    return None
```

This helper is called with the ingredient's word tokens and a list like
`["pork", "porcine", "swine", "lard"]`. It returns the first keyword that is fully
contained in the tokens. The `all(...)` call returns `True` only if every element
of the generator expression is `True`. For single-word keywords like `"pork"`, it
checks that `"pork"` is in the token set. For multi-word keywords like
`"halal beef"`, both `"halal"` and `"beef"` must appear.

#### The `_aggregate` method — worst-status-wins

```python
@staticmethod
def _aggregate(results: list[IngredientResult]) -> Status:
    statuses = {r.status for r in results}
    if Status.HARAM in statuses:
        return Status.HARAM
    if Status.SHUBHAH in statuses:
        return Status.SHUBHAH
    return Status.HALAL
```

`{r.status for r in results}` is a **set comprehension** — it builds a `set` (a
collection with no duplicates) of all the status values. Even if 10 ingredients are
HALAL and 1 is HARAM, the set will contain `{Status.HALAL, Status.HARAM}` and the
HARAM check fires.

`@staticmethod` means this method does not need `self` or `cls`. It is a plain
function that lives inside the class for organisational reasons. Calling it as
`HalalClassifier._aggregate(results)` or `self._aggregate(results)` both work.

The logic is a strict hierarchy: HARAM outranks SHUBHAH, which outranks HALAL. A
single prohibited ingredient makes the whole product prohibited. A single doubtful
ingredient makes the whole product doubtful (even if everything else is clearly
halal). This is the safe, conservative approach.

#### The `classify` entry point

```python
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
```

This is a **list comprehension with a filter condition**. The `if normalize(raw)`
part at the end acts as a guard: if `normalize(raw)` returns an empty string
(falsy), that item is skipped entirely and never classified. This handles `None`,
empty strings, or non-string entries in the input list gracefully.

---

## 4. The Rulebook Is the Knowledge Base

The file `src/halal_scanner/data/rulebook.yaml` is the engine's source of truth
for all ingredients it knows about.

#### What a YAML entry looks like

Here is the `gelatin` entry in full:

```yaml
gelatin:
  nature: source_dependent
  default: shubhah
  synonyms: [gelatine, e441]
  halal_if: [fish, plant, "halal beef", "halal certified", bovine halal]
  haram_if: [pork, porcine, swine, lard]
  reason: "Animal collagen; permissibility depends on the animal and slaughter. Source not disclosed."
  citation: "JAKIM MS1500:2009"
```

| Field | Required? | Meaning |
|-------|-----------|---------|
| `key` (the YAML mapping key, here `gelatin`) | Yes | The canonical (normalized) name. Must match what `normalize()` would produce — lowercase, no punctuation. |
| `nature` | Yes | `always_halal`, `always_haram`, or `source_dependent`. |
| `default` | No (defaults to `shubhah`) | The status when nature is `source_dependent` and no source qualifier is found. Usually `shubhah`. |
| `synonyms` | No | Other normalized names or E-numbers that should resolve to this entry. |
| `halal_if` | No | Keywords (or phrases) in the ingredient text that indicate a permissible source. |
| `haram_if` | No | Keywords that indicate a prohibited source. Checked first. |
| `reason` | No | Human-readable explanation. Shown in the result. |
| `citation` | No | The standard or authority behind the ruling (e.g. JAKIM MS1500:2009). |

#### How to add a new ingredient

Suppose you want to add a ruling for **carnauba wax** (a plant-derived wax used as
a glazing agent, always halal).

1. Open `src/halal_scanner/data/rulebook.yaml`.

2. Decide on the **canonical key** by mentally running `normalize()` on the name:
   - `"Carnauba Wax"` → lowercase → `"carnauba wax"` → no punctuation to strip →
     `"carnauba wax"`. That is your key.

3. Choose the **nature**:
   - It is plant-derived. No animal source is possible. Use `always_halal`.

4. Add the entry at the end of the file:

   ```yaml
   carnauba wax:
     nature: always_halal
     reason: "Plant-derived wax from Brazilian palm leaves."
     citation: "General"
   ```

5. You do not need `halal_if` or `haram_if` for `always_halal` entries. You do not
   need synonyms unless there are common alternative names (e.g. `e903`):

   ```yaml
   carnauba wax:
     nature: always_halal
     synonyms: [e903]
     reason: "Plant-derived wax from Brazilian palm leaves."
     citation: "General"
   ```

For a **`source_dependent`** ingredient, for example a new emulsifier:

```yaml
lecithin:
  nature: source_dependent
  default: shubhah
  synonyms: [e322]
  halal_if: [soy, sunflower, plant, vegetable]
  haram_if: [pork, porcine, egg]
  reason: "Emulsifier; source may be plant or animal."
  citation: "JAKIM MS1500:2009"
```

The `haram_if` keywords will be checked first. Add the most specific concern first
in each list, so the most important disqualifiers are checked first.

**Important:** all keys and synonyms must be in **normalized form** — lowercase,
no punctuation, spaces instead of hyphens. If you add `"l-cysteine"` it will never
match because the normalizer would turn the input into `"l cysteine"` (hyphen →
space) before the lookup.

---

## 5. How to Run It

All commands should be run from the `halal-scanner/` directory.

#### Run the tests

```
.venv/Scripts/python -m pytest
```

There are **32 tests** covering normalization, rulebook lookups, source-dependent
resolution, Gemma fallback behaviour, and end-to-end classification. All 32 should
pass.

#### Run the demo

```
.venv/Scripts/python examples/demo.py
```

The demo (`examples/demo.py`) creates the full engine and classifies a sample list:

```python
sample = ["sugar", "gelatin", "gelatin (fish)", "pork gelatin", "e471", "carmine"]
```

Expected output (with Gemma online):

```
Overall verdict: HARAM based on 6 ingredient(s).
  - sugar                    -> halal    [rulebook/high] Plant-derived; ...
  - gelatin                  -> shubhah  [rulebook/high] Animal collagen; ...
  - gelatin (fish)           -> halal    [rulebook/high] Halal source named. ...
  - pork gelatin             -> haram    [rulebook/high] Haram source named. ...
  - e471                     -> shubhah  [rulebook/high] Emulsifier from fat; ...
  - carmine                  -> shubhah  [rulebook/high] Insect-derived colour; ...

This is automated guidance, not a religious ruling. ...
```

The overall verdict is HARAM because "pork gelatin" is present (worst-status-wins).

If Ollama is not running or the model is not installed, ingredients unknown to the
rulebook will still be classified as `shubhah` with `confidence=low` and a message
saying Gemma was unavailable — the engine does not crash.

---

## 6. Design Decisions and Disclaimers

### Why the rulebook is the authority

The rulebook entries are written by a human and backed by citations (JAKIM
MS1500:2009, the Malaysian halal standard). Every ruling is auditable — you can
read the entry and see exactly why an ingredient was classified the way it was.

Gemma (the AI fallback) is only used for ingredients the rulebook does not know
about. Its results carry `confidence=low` and its reason text is marked
`(Gemma estimate — unverified)`. This is not modesty — a language model can and
does make mistakes on domain-specific factual questions. Trusting it without
verification would undermine the whole purpose of the tool.

The principle is: **curated knowledge first, AI as a last resort**.

### Every verdict carries a disclaimer

```python
DISCLAIMER = (
    "This is automated guidance, not a religious ruling. "
    "Verify with official halal certification (e.g. JAKIM) before relying on it."
)
```

This disclaimer is attached to every `ScanVerdict` and printed in the demo. Food
ingredients are a sensitive domain and regulations differ between countries and
scholarly interpretations. The engine provides a practical first filter; it is not
a substitute for official certification.

### The error log

Real errors hit during development — not hypothetical ones — are documented in
[`docs/ERRORS.md`](../ERRORS.md). Reading it shows you what actually went wrong and
how it was fixed. For example: the Gemma client originally defaulted to
`gemma3:4b`, a model not installed on the development machine, so every AI fallback
silently returned `None`. The fix was to change the default to `gemma4:latest` to
match the actually-installed model. The `except Exception: return None` pattern that
swallowed this failure is exactly why the error was hard to spot — and exactly why
low-confidence AI results are never trusted without scrutiny.
