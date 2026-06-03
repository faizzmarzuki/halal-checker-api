# Backend Deploy to Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Halal Checker API to Render as a Docker web service backed by managed PostgreSQL, with Tesseract OCR included, via a committed `render.yaml` Blueprint.

**Architecture:** Add psycopg3 support (optional dep + runtime URL normalization in `db.py`) so the existing app talks to Postgres unchanged. A `Dockerfile` installs the `tesseract-ocr` binary plus the `ocr` and `postgres` extras and runs uvicorn on `$PORT`. A `render.yaml` Blueprint declares the web service + Postgres + env vars (prod posture, generated JWT secret, DB wired from the managed instance).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, psycopg3, Docker, Render Blueprint, Tesseract OCR.

---

## File Structure

- `src/halal_scanner/db.py` — add `_normalize_db_url()` helper; call it in `_make_engine()`. One responsibility: engine/session wiring.
- `tests/test_db_url.py` (new) — unit tests for `_normalize_db_url`.
- `pyproject.toml` — new `postgres` optional-dependency group.
- `Dockerfile` (new) — production image (tesseract + extras + uvicorn).
- `.dockerignore` (new) — trims build context.
- `render.yaml` (new) — Blueprint: web service + Postgres + env vars.
- `README.md` — "Deploy to Render" section.
- `docs/CHECKPOINT.md` — record SP26.

---

### Task 1: Postgres URL normalization (TDD)

**Files:**
- Test: `tests/test_db_url.py` (create)
- Modify: `src/halal_scanner/db.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_url.py`:

```python
from halal_scanner.db import _normalize_db_url


def test_sqlite_url_unchanged():
    assert _normalize_db_url("sqlite:///./halal_scanner.db") == "sqlite:///./halal_scanner.db"


def test_heroku_style_postgres_scheme_maps_to_psycopg3():
    assert (
        _normalize_db_url("postgres://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_plain_postgresql_scheme_maps_to_psycopg3():
    assert (
        _normalize_db_url("postgresql://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_explicit_driver_left_unchanged():
    assert (
        _normalize_db_url("postgresql+psycopg2://u:p@host/db")
        == "postgresql+psycopg2://u:p@host/db"
    )
    assert (
        _normalize_db_url("postgresql+psycopg://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_db_url.py -v`
Expected: FAIL with `ImportError: cannot import name '_normalize_db_url'`.

- [ ] **Step 3: Write minimal implementation**

In `src/halal_scanner/db.py`, add the helper above `_make_engine` and call it inside:

```python
def _normalize_db_url(url: str) -> str:
    """Adapt common Postgres URL schemes to the installed psycopg3 driver.

    Render gives ``postgresql://…`` and Heroku-style ``postgres://…`` is common;
    SQLAlchemy would otherwise default to the (uninstalled) psycopg2 driver. A
    URL that already names a driver (``postgresql+psycopg://`` /
    ``postgresql+psycopg2://``) or any non-Postgres URL (SQLite) is returned
    unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine():
    url = _normalize_db_url(
        os.environ.get("HALAL_DATABASE_URL", "sqlite:///./halal_scanner.db")
    )
    # check_same_thread=False lets the SQLite connection be shared across
    # FastAPI's threadpool workers; harmless for other backends (skipped).
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)
```

Note: `postgresql+psycopg://` and `postgresql+psycopg2://` do **not** start with the bare `postgresql://` (they start with `postgresql+`), so the second rule skips them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_db_url.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 188 passed + the 4 new = 192 passed (SQLite behaviour unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/test_db_url.py src/halal_scanner/db.py
git commit -m "feat(sp26): normalize Postgres DB URL to psycopg3 driver

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add the `postgres` optional dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the extra**

In `pyproject.toml`, under `[project.optional-dependencies]`, add after the `ocr` line:

```toml
# PostgreSQL driver for production deploys (HALAL_DATABASE_URL=postgresql://…).
postgres = ["psycopg[binary]>=3.1"]
```

- [ ] **Step 2: Verify it installs and the app still imports**

Run:
```bash
.venv/Scripts/python -m pip install -e ".[postgres]"
.venv/Scripts/python -c "import psycopg; from halal_scanner.api.app import app; print('ok')"
```
Expected: prints `ok` (no import errors).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(sp26): add psycopg3 postgres optional dependency

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Write the Dockerfile**

Create `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

# tesseract binary + eng/osd language data, for /scan-image OCR.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[ocr,postgres]"

# Render injects $PORT; default 8000 for local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn halal_scanner.api.app:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 2: Build the image locally (smoke test)**

Run: `docker build -t halal-scanner-api .`
Expected: build succeeds; final layer installs the package. (If Docker is unavailable locally, skip — Render builds it; note the skip.)

- [ ] **Step 3: Optional — run the container locally**

Run:
```bash
docker run --rm -e HALAL_JWT_SECRET=devsecret -p 8000:8000 halal-scanner-api
```
Then in another shell: `curl http://localhost:8000/health`
Expected: `{"status":"ok",...}`. Stop the container (Ctrl-C). (Defaults to SQLite inside the container since no `HALAL_DATABASE_URL` — fine for the smoke test; `HALAL_ENV` unset = dev, so no rate-limit requirement.)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat(sp26): production Dockerfile with tesseract + extras

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: .dockerignore

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Write the .dockerignore**

Create `.dockerignore` at the repo root:

```gitignore
.git/
.venv/
mobile/
tests/
docs/
examples/
__pycache__/
*.db
*.pyc
QA_SECURITY_FINDINGS.txt
```

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore(sp26): trim Docker build context

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: render.yaml Blueprint

**Files:**
- Create: `render.yaml`

- [ ] **Step 1: Write the Blueprint**

Create `render.yaml` at the repo root:

```yaml
databases:
  - name: halal-db
    plan: free
    databaseName: halal_scanner

services:
  - type: web
    name: halal-scanner-api
    runtime: docker
    plan: free
    healthCheckPath: /health
    envVars:
      - key: HALAL_DATABASE_URL
        fromDatabase:
          name: halal-db
          property: connectionString
      - key: HALAL_JWT_SECRET
        generateValue: true
      - key: HALAL_ENV
        value: production
      - key: HALAL_RATE_LIMIT
        value: "60"
      - key: HALAL_RATE_WINDOW
        value: "60"
      - key: HALAL_TRUST_PROXY
        value: "1"
      - key: HALAL_ADMIN_EMAILS
        sync: false
      - key: HALAL_CORS_ORIGINS
        sync: false
```

- [ ] **Step 2: Sanity-check it is valid YAML**

Run: `.venv/Scripts/python -c "import yaml; print(list(yaml.safe_load(open('render.yaml'))))"`
Expected: prints `['databases', 'services']` (parses without error).

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "feat(sp26): Render Blueprint (web + postgres + prod env)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: README deploy section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Deploy to Render" section**

Append to `README.md` (place after the existing run/usage instructions):

```markdown
## Deploy to Render

The repo ships a `render.yaml` Blueprint that provisions a Docker web service
plus a managed PostgreSQL database, with Tesseract OCR baked into the image so
`/scan-image` works in production.

1. Push the branch to GitHub.
2. In the Render dashboard: **New → Blueprint**, connect this repo, and apply
   `render.yaml`. Render creates the `halal-scanner-api` web service and the
   `halal-db` Postgres instance.
3. Fill the two manual env vars (declared `sync: false`):
   - `HALAL_ADMIN_EMAILS` — your account email, to get the `admin` role.
   - `HALAL_CORS_ORIGINS` — leave blank unless testing an Expo **web** build
     against prod (e.g. `https://your-web-build`); native Expo Go needs no CORS.
4. Deploy. The service boots with `HALAL_ENV=production` (docs hidden, rate
   limiting enforced), a generated `HALAL_JWT_SECRET`, and `HALAL_DATABASE_URL`
   wired from the managed Postgres. `create_all` builds the schema on first boot.

Notes:
- Free tier spins down after ~15 min idle; the first request after idle takes
  ~30–60s (cold start).
- Point the mobile app at the deployed URL by setting `EXPO_PUBLIC_API_URL` in
  `mobile/.env` to `https://halal-scanner-api.onrender.com`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(sp26): README Render deploy instructions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Checkpoint update

**Files:**
- Modify: `docs/CHECKPOINT.md`

- [ ] **Step 1: Record SP26**

In `docs/CHECKPOINT.md`, add SP26 to the built/feature list and update the
"Suggested next step" section to reflect that the deploy Blueprint now exists
(the operator still has to click through the Render Blueprint + fill the two
`sync:false` env vars). Mention: Docker + managed Postgres + tesseract;
`render.yaml` at repo root; `_normalize_db_url` adapts the DB URL to psycopg3.

Keep edits concise — one bullet under the feature list and a one-line update to
the next-step list. Match the existing prose style.

- [ ] **Step 2: Commit**

```bash
git add docs/CHECKPOINT.md
git commit -m "docs(sp26): checkpoint after Render deploy Blueprint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria

- `.venv/Scripts/python -m pytest -q` → 192 passed (188 existing + 4 new).
- `render.yaml`, `Dockerfile`, `.dockerignore` exist at repo root and parse/build.
- README documents the deploy; CHECKPOINT records SP26.
- Operator step (outside this plan): create the Render Blueprint, fill the two
  manual env vars, deploy, then update `mobile/.env`'s `EXPO_PUBLIC_API_URL`.
