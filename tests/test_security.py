from unittest.mock import patch

import pytest
from fastapi import HTTPException

from halal_scanner.api.security import RateLimiter, require_api_key


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_rate_limiter_allows_up_to_limit_then_blocks():
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window=60, now=clock)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False  # third within window


def test_rate_limiter_allows_again_after_window():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window=60, now=clock)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    clock.advance(61)
    assert limiter.allow("ip") is True


def test_rate_limiter_zero_limit_is_disabled():
    limiter = RateLimiter(limit=0, window=60)
    for _ in range(100):
        assert limiter.allow("ip") is True


def test_require_api_key_disabled_when_no_keys_configured():
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("HALAL_API_KEYS", None)
        # Should not raise.
        assert require_api_key(x_api_key=None) is None


def test_require_api_key_rejects_missing_and_accepts_valid():
    with patch.dict("os.environ", {"HALAL_API_KEYS": "alpha, beta"}):
        with pytest.raises(HTTPException) as exc:
            require_api_key(x_api_key=None)
        assert exc.value.status_code == 401
        with pytest.raises(HTTPException):
            require_api_key(x_api_key="wrong")
        # Valid key passes.
        assert require_api_key(x_api_key="beta") is None
