# Rate-Limit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the API rate limiter proxy-aware (honour a trusted `X-Forwarded-For`) and bound its memory by evicting stale keys (the in-process half of MED-1).

**Architecture:** Two focused changes in `src/halal_scanner/api/security.py`: a periodic stale-key sweep inside `RateLimiter`, and a `client_ip()` helper that `rate_limit` uses for its IP fallback (trusting `X-Forwarded-For` only when `HALAL_TRUST_PROXY` is set).

**Tech Stack:** FastAPI dependencies, stdlib `collections.deque`/`defaultdict`, pytest. Baseline on this branch (stacked on SP12): **142 passing, 2 skipped**.

---

## File Structure

- `src/halal_scanner/api/security.py` — `RateLimiter` gains `evict_every` + `_maybe_evict`; new `_trust_proxy()` and `client_ip()`; `rate_limit` keys on `client_ip(request)`.
- `tests/test_security.py` — eviction tests + `client_ip` tests (file already has a `FakeClock` helper).

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: Stale-key eviction in RateLimiter

**Files:**
- Modify: `src/halal_scanner/api/security.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_security.py` (it already imports `from halal_scanner.api.security import RateLimiter` and defines `FakeClock`):

```python
def test_rate_limiter_evicts_stale_keys():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window=60, now=clock, evict_every=2)
    limiter.allow("old")          # _since_evict -> 1 (no sweep yet)
    clock.advance(61)             # "old" is now past the window
    limiter.allow("active")       # _since_evict -> 2 => sweep removes expired "old"
    assert "old" not in limiter._hits
    assert "active" in limiter._hits


def test_rate_limiter_keeps_live_keys_on_evict():
    clock = FakeClock()
    limiter = RateLimiter(limit=5, window=60, now=clock, evict_every=2)
    limiter.allow("a")            # _since_evict -> 1
    limiter.allow("a")            # _since_evict -> 2 => sweep, but "a" is still live
    assert "a" in limiter._hits
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_security.py::test_rate_limiter_evicts_stale_keys -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'evict_every'`.

- [ ] **Step 3: Add the eviction logic**

In `src/halal_scanner/api/security.py`, update the `RateLimiter.__init__` (currently takes `limit, window, now=time.monotonic`) to add `evict_every` and a counter, and add the `_maybe_evict` method plus a call to it in `allow`. The class currently is:

```python
class RateLimiter:
    """Sliding-window-log limiter. Thread-safe; ``now`` is injectable for tests."""

    def __init__(
        self,
        limit: int,
        window: float,
        now: Callable[[], float] = time.monotonic,
    ):
        self.limit = limit
        self.window = window
        self._now = now
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for ``key`` and return whether it is within the limit."""
        if self.limit <= 0:
            return True  # disabled
        now = self._now()
        cutoff = now - self.window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True
```

Replace it with:

```python
class RateLimiter:
    """Sliding-window-log limiter. Thread-safe; ``now`` is injectable for tests."""

    def __init__(
        self,
        limit: int,
        window: float,
        now: Callable[[], float] = time.monotonic,
        evict_every: int = 1000,
    ):
        self.limit = limit
        self.window = window
        self._now = now
        self._evict_every = evict_every
        self._since_evict = 0
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _maybe_evict(self, cutoff: float) -> None:
        """Every ``evict_every`` calls, drop keys whose hits are all expired.

        Runs under the caller's lock. A key whose deque is empty or whose most
        recent hit is older than the cutoff has no live state, so removing it is
        safe — it would prune to empty on next access anyway. Bounds the memory
        the limiter holds for one-off IPs/keys (MED-1).
        """
        self._since_evict += 1
        if self._since_evict < self._evict_every:
            return
        self._since_evict = 0
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale:
            del self._hits[k]

    def allow(self, key: str) -> bool:
        """Record a hit for ``key`` and return whether it is within the limit."""
        if self.limit <= 0:
            return True  # disabled
        now = self._now()
        cutoff = now - self.window
        with self._lock:
            self._maybe_evict(cutoff)
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_security.py -v`
Expected: PASS — the two new eviction tests green; the three existing `RateLimiter` tests still pass (default `evict_every=1000` means no sweep during those short tests).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/security.py tests/test_security.py
git commit -m "feat(security): evict stale rate-limit keys to bound memory (MED-1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Proxy-aware client IP

**Files:**
- Modify: `src/halal_scanner/api/security.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_security.py`. Add `import pytest` at the top of the file if it is not already imported (the current file has no imports other than `from halal_scanner.api.security import RateLimiter` — add `import pytest` and extend the import to include `client_ip`). Then append:

```python
class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, client_host=None, headers=None):
        self.headers = headers or {}
        self.client = _FakeClient(client_host) if client_host is not None else None


def test_client_ip_ignores_xff_without_trust(monkeypatch):
    monkeypatch.delenv("HALAL_TRUST_PROXY", raising=False)
    req = _FakeRequest(client_host="10.0.0.9", headers={"x-forwarded-for": "1.2.3.4"})
    assert client_ip(req) == "10.0.0.9"


def test_client_ip_uses_first_xff_when_trusted(monkeypatch):
    monkeypatch.setenv("HALAL_TRUST_PROXY", "1")
    req = _FakeRequest(client_host="10.0.0.9", headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"})
    assert client_ip(req) == "1.2.3.4"


def test_client_ip_trusted_but_no_xff_falls_back(monkeypatch):
    monkeypatch.setenv("HALAL_TRUST_PROXY", "true")
    req = _FakeRequest(client_host="10.0.0.9", headers={})
    assert client_ip(req) == "10.0.0.9"


def test_client_ip_no_client_returns_unknown(monkeypatch):
    monkeypatch.delenv("HALAL_TRUST_PROXY", raising=False)
    req = _FakeRequest(client_host=None, headers={})
    assert client_ip(req) == "unknown"


def test_client_ip_empty_xff_segment_falls_back(monkeypatch):
    # A malformed leading comma must not yield an empty limiter key.
    monkeypatch.setenv("HALAL_TRUST_PROXY", "yes")
    req = _FakeRequest(client_host="10.0.0.9", headers={"x-forwarded-for": ", 10.0.0.1"})
    assert client_ip(req) == "10.0.0.9"
```

For the import line at the top, change:
```python
from halal_scanner.api.security import RateLimiter
```
to:
```python
from halal_scanner.api.security import RateLimiter, client_ip
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_security.py::test_client_ip_uses_first_xff_when_trusted -v`
Expected: FAIL with `ImportError: cannot import name 'client_ip'`.

- [ ] **Step 3: Add `_trust_proxy` and `client_ip`, and wire `rate_limit`**

In `src/halal_scanner/api/security.py`, add the two helpers just above the existing `rate_limit` function (after the module-level `limiter = _build_limiter()` line):

```python
def _trust_proxy() -> bool:
    """Whether to believe X-Forwarded-For (operator opt-in via env)."""
    return os.environ.get("HALAL_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes"}


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Honour X-Forwarded-For ONLY when HALAL_TRUST_PROXY is set — i.e. the operator
    asserts the service sits behind their own proxy that sets the header. The
    left-most XFF entry is the original client. Without the opt-in, an attacker
    could spoof XFF to evade or poison the limiter, so we use the socket peer.
    """
    if _trust_proxy():
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Guard against a malformed/empty first segment (e.g. ", 10.0.0.1"):
            # an empty key would lump unrelated requests into one bucket.
            candidate = xff.split(",")[0].strip()
            if candidate:
                return candidate
    return request.client.host if request.client else "unknown"
```

Then change the body of `rate_limit` (currently `key = x_api_key or (request.client.host if request.client else "unknown")`) to use the helper:

```python
def rate_limit(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    """Dependency: throttle by API key (if present) else client IP."""
    key = x_api_key or client_ip(request)
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
```

`os` and `Request` are already imported at the top of the file (`import os`; `from fastapi import Depends, Header, HTTPException, Request`), so no new imports are needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_security.py -v`
Expected: PASS — all four `client_ip` tests green; eviction and existing limiter tests still pass.

- [ ] **Step 5: Run the API tests to confirm no regression**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -q`
Expected: PASS — `test_rate_limit_returns_429_when_exceeded` still passes (it sends a valid API key, so the key is the API key; the `client_ip` change does not affect that path).

- [ ] **Step 6: Commit**

```bash
git add src/halal_scanner/api/security.py tests/test_security.py
git commit -m "feat(security): proxy-aware client IP via trusted X-Forwarded-For (MED-1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Full-suite verification & checkpoint

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (142 baseline + 6 new = 148 passing, 2 skipped). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`:
- Update the test count.
- Add an SP13 entry under "What's built".
- Under "Already fixed", add the MED-1 in-process half (proxy-aware IP + stale eviction, via SP13); keep the Redis/shared limiter listed under "Still open" with a note that the proxy-aware + eviction parts are now done.
- Add the new env var `HALAL_TRUST_PROXY` to the "Key env vars" list.
- Update the SP11/SP12/SP13 branch state (SP13 stacked on SP12) and "Suggested next step".

- [ ] **Step 3: Commit the checkpoint and plan**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-ratelimit-hardening.md
git commit -m "docs(halal-scanner): SP13 done — proxy-aware + self-evicting rate limiter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `HALAL_TRUST_PROXY` env var (truthy = `1`/`true`/`yes`, case-insensitive) gates whether `X-Forwarded-For` is trusted. Default off → socket peer, no behaviour change.
- `evict_every` defaults to 1000 so the existing short limiter tests never trigger a sweep; the new tests pass a small value to force it.
- Do NOT add a Redis backend or rate-limit the auth endpoints — both are out of scope for this sub-project.
- The `_maybe_evict` sweep runs under the same lock as `allow`, so it stays thread-safe.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is stacked on SP12; final `--no-ff` merge to `main` happens after SP11 and SP12 merge (handled after review, not in this plan).
