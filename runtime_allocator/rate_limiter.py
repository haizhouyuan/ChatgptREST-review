"""Simple in-memory token bucket rate limiter.

Production should replace this with Redis-based rate limiting
for distributed deployments.

Usage:
    from runtime_allocator.rate_limiter import RateLimiter
    limiter = RateLimiter(rps=10, burst=20)
    if not limiter.allow("client_123"):
        raise HTTPException(429, "Rate limit exceeded")
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter per client key."""

    def __init__(self, rps: float = 10.0, burst: int = 20):
        self.rps = rps
        self.burst = burst
        self._tokens: dict[str, float] = {}
        self._last_update: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Check if request from key is allowed. Returns True if within limit."""
        now = time.time()
        with self._lock:
            last = self._last_update.get(key, now)
            tokens = self._tokens.get(key, self.burst)

            # Add tokens based on time elapsed
            elapsed = now - last
            tokens = min(self.burst, tokens + elapsed * self.rps)
            self._last_update[key] = now

            if tokens >= 1.0:
                tokens -= 1.0
                self._tokens[key] = tokens
                return True
            else:
                self._tokens[key] = tokens
                return False

    def reset(self, key: str):
        """Reset rate limit for a client key."""
        with self._lock:
            self._tokens.pop(key, None)
            self._last_update.pop(key, None)

    def reset_all(self):
        """Reset rate limits for all client keys."""
        with self._lock:
            self._tokens.clear()
            self._last_update.clear()
