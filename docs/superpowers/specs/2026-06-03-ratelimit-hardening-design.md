# Sub-project 13 — Rate-Limit Hardening (Design)

Date: 2026-06-03

Closes the in-process half of QA finding MED-1: the rate limiter is proxy-blind
and never evicts stale keys. Branched from the SP12 tip (stacked: SP11 → SP12 →
SP13). Touches only `src/halal_scanner/api/security.py`.

## Honest scoping note

The scanning endpoints (`/classify`, `/scan-barcode`, `/scan-image`) wrap
`require_api_key` then `rate_limit`. `require_api_key` runs first and raises 401
for a missing/invalid key, so `rate_limit` only runs for a VALID key, and
`rate_limit` keys on that API key (`key = x_api_key or client_ip(request)`).
The IP branch is therefore latent for the current wiring. MED-1 still matters as
(a) limiter correctness — the IP fallback should respect a trusted proxy, and
(b) bounding memory growth — and it readies correct IP-keying for any future
endpoint that is rate-limited WITHOUT an API key (e.g. login brute-force). This
sub-project does NOT add rate limiting to auth endpoints (out of scope for
MED-1).

## #1 Proxy-aware client IP

Add to `security.py`:

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

`rate_limit` changes its key derivation from `request.client.host` to
`client_ip(request)`:

```python
def rate_limit(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    """Dependency: throttle by API key (if present) else client IP."""
    key = x_api_key or client_ip(request)
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
```

Default behaviour (env unset) is identical to today (socket peer), so there is
no regression. XFF is trusted only on explicit opt-in.

## #3 Stale-key eviction

`RateLimiter._hits` is a `defaultdict(deque)` that never drops keys, so memory
grows slowly with distinct keys/IPs. Add periodic eviction:

- `__init__` gains `evict_every: int = 1000` and a counter `self._since_evict = 0`.
- `allow` calls `self._maybe_evict(cutoff)` at the top of the locked section.

```python
def _maybe_evict(self, cutoff: float) -> None:
    """Every ``evict_every`` calls, drop keys whose hits are all expired.

    Runs under the caller's lock. A key whose deque is empty or whose most
    recent hit is older than the window cutoff has no live state, so removing it
    is safe (it would prune to empty on next access anyway).
    """
    self._since_evict += 1
    if self._since_evict < self._evict_every:
        return
    self._since_evict = 0
    stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
    for k in stale:
        del self._hits[k]
```

`allow` becomes:

```python
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

The disabled fast-path (`limit <= 0`) keeps returning early, so eviction only
runs when limiting is active.

## Out of scope (remain open)

- **#2 Redis / shared limiter** — needed for multi-worker / multi-replica
  deploys so the limit is shared, not per-process. Requires a Redis dependency
  and deployment changes; deferred until a real scale-out. Recorded in
  `QA_SECURITY_FINDINGS.txt` and the checkpoint.
- Adding rate limiting to auth endpoints (not part of MED-1).

## Testing (TDD, red → green)

`client_ip` (`tests/test_security.py`, fake request + `monkeypatch` env):
- env unset → returns `request.client.host`, ignores a present XFF.
- `HALAL_TRUST_PROXY=1` + XFF `"1.2.3.4, 10.0.0.1"` → returns `"1.2.3.4"`.
- `HALAL_TRUST_PROXY=1` but no XFF → falls back to `request.client.host`.
- `HALAL_TRUST_PROXY=yes` + XFF with an empty leading segment (`", 10.0.0.1"`) →
  falls back to `request.client.host` (no empty limiter key).
- no `request.client` → returns `"unknown"`.

`RateLimiter` eviction (injected `now`, small `evict_every`):
- a key seen, then `now` advanced past the window, then `evict_every` calls made
  → the stale key is removed from `_hits`.
- a key with a live (recent) hit is NOT evicted by the sweep.

`rate_limit` regression (`tests/test_api.py` or `test_security.py`):
- with the limiter at limit 1, a second call returns 429 (unchanged behaviour),
  exercised through `client_ip` (e.g. with an XFF header set and trust enabled).

Run: `.venv/Scripts/python -m pytest -q` (baseline on this branch: 142 passing,
2 skipped).

## Conventions

Branch `sub-project-13-ratelimit-hardening` (stacked on SP12); spec here; plan in
`docs/superpowers/plans/`; TDD; `--no-ff` merge to `main` after SP11 & SP12;
delete the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
