from halal_scanner.api.security import RateLimiter


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
