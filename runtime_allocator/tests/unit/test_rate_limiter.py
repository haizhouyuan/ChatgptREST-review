"""Unit tests for the token bucket rate limiter."""

from __future__ import annotations

import time

from runtime_allocator.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allow_within_burst(self):
        limiter = RateLimiter(rps=1.0, burst=5)
        # First 5 requests should be allowed
        for _ in range(5):
            assert limiter.allow("client_a")

    def test_deny_when_exhausted(self):
        limiter = RateLimiter(rps=1.0, burst=2)
        assert limiter.allow("client_a")
        assert limiter.allow("client_a")
        assert not limiter.allow("client_a")

    def test_independent_clients(self):
        limiter = RateLimiter(rps=1.0, burst=2)
        assert limiter.allow("client_a")
        assert limiter.allow("client_a")
        # client_b has its own bucket
        assert limiter.allow("client_b")
        assert limiter.allow("client_b")
        assert not limiter.allow("client_a")
        assert not limiter.allow("client_b")

    def test_refill_over_time(self):
        limiter = RateLimiter(rps=10.0, burst=1)
        assert limiter.allow("client_c")
        assert not limiter.allow("client_c")
        time.sleep(0.15)  # Wait for refill
        assert limiter.allow("client_c")

    def test_reset(self):
        limiter = RateLimiter(rps=1.0, burst=2)
        assert limiter.allow("client_d")
        assert limiter.allow("client_d")
        assert not limiter.allow("client_d")
        limiter.reset("client_d")
        assert limiter.allow("client_d")
        assert limiter.allow("client_d")
