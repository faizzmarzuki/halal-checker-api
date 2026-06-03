import pytest

from halal_scanner.api.security import RateLimiter, client_ip


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
