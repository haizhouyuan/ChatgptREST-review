"""Health tracker — real-time provider availability monitoring.

Extends the QuotaSensor concept with OFFLINE state and per-provider
sliding-window statistics.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    EXHAUSTED = "exhausted"
    COOLDOWN = "cooldown"
    OFFLINE = "offline"


@dataclass
class ProviderHealth:
    """Real-time health state for a single provider."""
    provider_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    failure_rate: float = 0.0
    recent_latency_ms: float = 0.0
    consecutive_successes: int = 0
    cooldown_until: float = 0.0   # Unix timestamp
    offline_reason: str = ""
    last_success: float = 0.0     # Unix timestamp
    last_failure: float = 0.0

    def is_available(self) -> bool:
        """Can this provider accept requests right now?"""
        if self.status == HealthStatus.OFFLINE:
            return False
        if self.status == HealthStatus.EXHAUSTED:
            return False
        if self.status == HealthStatus.COOLDOWN:
            return time.time() >= self.cooldown_until
        return True

    @property
    def degradation_factor(self) -> float:
        """0.0 (fully degraded) to 1.0 (healthy). Used in scoring."""
        if self.status == HealthStatus.HEALTHY:
            return 1.0
        elif self.status == HealthStatus.DEGRADED:
            return max(0.3, 1.0 - self.failure_rate)
        elif self.status == HealthStatus.COOLDOWN:
            return 0.1
        else:
            return 0.0


@dataclass
class _Event:
    """Internal event in the sliding window."""
    timestamp: float
    success: bool
    latency_ms: int = 0
    error_type: str = ""


class HealthTracker:
    """Tracks health of all providers using sliding-window statistics.

    Thread-safe. Used by Selector to filter/deprioritize unhealthy providers.
    """

    def __init__(
        self,
        window_seconds: int = 600,
        degraded_failure_rate: float = 0.3,
        exhausted_failure_rate: float = 0.6,
        recovery_successes: int = 3,
        cooldown_default_seconds: int = 120,
    ):
        self._window = window_seconds
        self._degraded_rate = degraded_failure_rate
        self._exhausted_rate = exhausted_failure_rate
        self._recovery_successes = recovery_successes
        self._cooldown_default = cooldown_default_seconds
        self._events: dict[str, list[_Event]] = {}  # provider_id -> events
        self._health: dict[str, ProviderHealth] = {}
        self._offline: dict[str, str] = {}  # provider_id -> reason
        self._lock = threading.Lock()

    def get_health(self, provider_id: str) -> ProviderHealth:
        with self._lock:
            return self._health.get(
                provider_id,
                ProviderHealth(provider_id=provider_id),
            )

    def all_health(self) -> dict[str, ProviderHealth]:
        with self._lock:
            return dict(self._health)

    def record_success(self, provider_id: str, latency_ms: int = 0) -> None:
        with self._lock:
            self._append_event(provider_id, _Event(
                timestamp=time.time(), success=True, latency_ms=latency_ms,
            ))
            self._recompute(provider_id)

    def record_failure(
        self,
        provider_id: str,
        error_type: str = "",
        latency_ms: int = 0,
    ) -> None:
        with self._lock:
            self._append_event(provider_id, _Event(
                timestamp=time.time(), success=False,
                latency_ms=latency_ms, error_type=error_type,
            ))
            self._recompute(provider_id)

    def record_cooldown(
        self,
        provider_id: str,
        seconds: int | None = None,
    ) -> None:
        cd = seconds or self._cooldown_default
        with self._lock:
            h = self._ensure_health(provider_id)
            h.status = HealthStatus.COOLDOWN
            h.cooldown_until = time.time() + cd
            logger.info(
                "Provider %s entering cooldown for %ds",
                provider_id, cd,
            )

    def set_offline(self, provider_id: str, reason: str = "") -> None:
        with self._lock:
            h = self._ensure_health(provider_id)
            h.status = HealthStatus.OFFLINE
            h.offline_reason = reason
            self._offline[provider_id] = reason

    def set_online(self, provider_id: str) -> None:
        with self._lock:
            if provider_id in self._offline:
                del self._offline[provider_id]
            h = self._ensure_health(provider_id)
            if h.status == HealthStatus.OFFLINE:
                h.status = HealthStatus.HEALTHY
                h.offline_reason = ""

    def reset(self, provider_id: str) -> None:
        with self._lock:
            self._events.pop(provider_id, None)
            self._health.pop(provider_id, None)
            self._offline.pop(provider_id, None)

    # ── Internals ────────────────────────────────────────────────

    def _ensure_health(self, pid: str) -> ProviderHealth:
        if pid not in self._health:
            self._health[pid] = ProviderHealth(provider_id=pid)
        return self._health[pid]

    def _append_event(self, pid: str, event: _Event) -> None:
        if pid not in self._events:
            self._events[pid] = []
        self._events[pid].append(event)

    def _recompute(self, pid: str) -> None:
        h = self._ensure_health(pid)

        # Don't auto-recover from offline
        if pid in self._offline:
            h.status = HealthStatus.OFFLINE
            return

        # Trim window
        now = time.time()
        cutoff = now - self._window
        events = self._events.get(pid, [])
        events = [e for e in events if e.timestamp >= cutoff]
        self._events[pid] = events

        if not events:
            h.status = HealthStatus.HEALTHY
            h.failure_rate = 0.0
            return

        total = len(events)
        failures = sum(1 for e in events if not e.success)
        rate = failures / total if total > 0 else 0.0
        latencies = [e.latency_ms for e in events if e.latency_ms > 0]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

        h.failure_rate = rate
        h.recent_latency_ms = avg_lat

        # Update last success/failure timestamps
        for e in reversed(events):
            if e.success and not h.last_success:
                h.last_success = e.timestamp
            if not e.success and not h.last_failure:
                h.last_failure = e.timestamp

        # Check cooldown expiry
        if h.status == HealthStatus.COOLDOWN:
            if now >= h.cooldown_until:
                # Cooldown expired, recompute based on recent data
                pass
            else:
                return  # Still in cooldown

        # Count consecutive recent successes (for recovery)
        consecutive = 0
        for e in reversed(events):
            if e.success:
                consecutive += 1
            else:
                break
        h.consecutive_successes = consecutive

        # Determine status
        if rate >= self._exhausted_rate:
            h.status = HealthStatus.EXHAUSTED
        elif rate >= self._degraded_rate:
            # Allow recovery if enough consecutive successes
            if consecutive >= self._recovery_successes:
                h.status = HealthStatus.HEALTHY
            else:
                h.status = HealthStatus.DEGRADED
        else:
            h.status = HealthStatus.HEALTHY
