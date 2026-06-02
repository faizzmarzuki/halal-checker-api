"""Optional API-key auth and in-memory rate limiting for the API.

Both are disabled by default and configured purely via environment variables, so
local/dev use and the test suite are unaffected unless explicitly turned on:

- ``HALAL_API_KEYS``   comma-separated allowed keys. Unset/empty => auth off.
- ``HALAL_RATE_LIMIT`` max requests per window (int). Unset/0 => limiting off.
- ``HALAL_RATE_WINDOW`` window length in seconds (float, default 60).
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Header, HTTPException, Request


def _configured_api_keys() -> set[str]:
    """Read allowed API keys from the environment, live, on each call."""
    raw = os.environ.get("HALAL_API_KEYS", "")
    return {key.strip() for key in raw.split(",") if key.strip()}


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Dependency: enforce a valid X-API-Key when any keys are configured."""
    keys = _configured_api_keys()
    if not keys:
        return  # auth disabled
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


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


def _build_limiter() -> RateLimiter:
    limit = int(os.environ.get("HALAL_RATE_LIMIT", "0") or "0")
    window = float(os.environ.get("HALAL_RATE_WINDOW", "60") or "60")
    return RateLimiter(limit=limit, window=window)


# Module-level limiter built once from the environment. Tests may patch this.
limiter = _build_limiter()


def rate_limit(
    request: Request, x_api_key: str | None = Header(default=None)
) -> None:
    """Dependency: throttle by API key (if present) else client IP."""
    key = x_api_key or (request.client.host if request.client else "unknown")
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
