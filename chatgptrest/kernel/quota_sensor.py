"""QuotaSensor — lightweight provider health tracking for routing decisions.

Maintains in-memory health state per provider, updated by failure/success/cooldown
reports from the Worker execution layer. The RoutingEngine queries this to skip
exhausted providers and deprioritize degraded ones.

Design principles:
  - No external probes at routing time (latency-free)
  - Health is event-driven: Worker reports outcomes, sensor updates state
  - Thread-safe via copy-on-write dicts
  - Fail-open: if sensor fails, all providers appear healthy

Usage::

    sensor = QuotaSensor(profile)
    sensor.report_failure("chatgpt_web", "rate_limited")
    sensor.report_cooldown("chatgpt_web", until_ts=time.time() + 300)

    health = sensor.check("chatgpt_web")
    # health.status == "degraded" or "exhausted"
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Health Status ─────────────────────────────────────────────────


class HealthStatus:
    """Provider health status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    EXHAUSTED = "exhausted"
    COOLDOWN = "cooldown"


@dataclass
class TierHealth:
    """Health state for a single provider."""
    provider_id: str = ""
    status: str = HealthStatus.HEALTHY
    consecutive_failures: int = 0
    total_failures_1h: int = 0
    total_successes_1h: int = 0
    cooldown_until: float = 0.0
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    reason: str = ""

    @property
    def is_available(self) -> bool:
        """True if the provider can accept new requests."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    @property
    def is_in_cooldown(self) -> bool:
        """True if the provider is in an active cooldown period."""
        return self.cooldown_until > time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "total_failures_1h": self.total_failures_1h,
            "total_successes_1h": self.total_successes_1h,
            "cooldown_until": self.cooldown_until,
            "reason": self.reason,
        }


# ── Failure Record ────────────────────────────────────────────────


@dataclass
class _FailureRecord:
    """Internal record of a failure event."""
    ts: float
    error_type: str


# ── QuotaSensor ───────────────────────────────────────────────────


class QuotaSensor:
    """Provider health tracker for quota-aware routing.

    Tracks per-provider failure/success history and cooldown state.
    The RoutingEngine uses ``check()`` to filter/deprioritize unhealthy providers.
    """

    # Thresholds for status transitions
    DEGRADE_THRESHOLD = 2     # consecutive failures to enter DEGRADED
    EXHAUST_THRESHOLD = 5     # consecutive failures to enter EXHAUSTED
    RECOVERY_SUCCESSES = 2    # consecutive successes to recover from DEGRADED
    HISTORY_WINDOW_S = 3600   # 1 hour sliding window for total counts

    def __init__(
        self,
        *,
        degrade_threshold: int = 2,
        exhaust_threshold: int = 5,
        recovery_successes: int = 2,
    ) -> None:
        self._degrade_threshold = degrade_threshold
        self._exhaust_threshold = exhaust_threshold
        self._recovery_successes = recovery_successes
        # provider_id → TierHealth
        self._health: dict[str, TierHealth] = {}
        # provider_id → list of failure records (for sliding window)
        self._failure_history: dict[str, list[_FailureRecord]] = {}
        # provider_id → list of success timestamps (for sliding window)
        self._success_history: dict[str, list[float]] = {}
        # provider_id → consecutive successes counter
        self._consecutive_successes: dict[str, int] = {}

    def check(self, provider_id: str) -> TierHealth:
        """Check current health status of a provider.

        Returns TierHealth with status. Automatically lifts cooldown
        when cooldown period has elapsed.
        """
        health = self._health.get(provider_id)
        if health is None:
            # Unknown provider = healthy by default (fail-open)
            return TierHealth(
                provider_id=provider_id,
                status=HealthStatus.HEALTHY,
            )

        now = time.time()

        # Auto-lift cooldown if period has elapsed
        if health.status == HealthStatus.COOLDOWN and health.cooldown_until <= now:
            health.status = HealthStatus.DEGRADED
            health.reason = f"cooldown lifted, still degraded (failures={health.consecutive_failures})"
            logger.info("QuotaSensor: %s cooldown lifted → degraded", provider_id)

        # Recount sliding window stats
        self._recount(provider_id, now)
        health.total_failures_1h = len(self._failure_history.get(provider_id, []))
        health.total_successes_1h = len(self._success_history.get(provider_id, []))

        return health

    def check_all(self) -> dict[str, TierHealth]:
        """Check health of all known providers."""
        return {pid: self.check(pid) for pid in self._health}

    def report_failure(
        self,
        provider_id: str,
        error_type: str = "unknown",
        *,
        cooldown_seconds: int = 0,
    ) -> TierHealth:
        """Report a provider failure. Updates health status.

        Args:
            provider_id: The provider that failed.
            error_type: Type of error (rate_limited, auth_failed, timeout, blocked, etc.)
            cooldown_seconds: If >0, put provider into cooldown for this duration.
        """
        now = time.time()
        health = self._ensure_health(provider_id)

        # Record failure
        if provider_id not in self._failure_history:
            self._failure_history[provider_id] = []
        self._failure_history[provider_id].append(_FailureRecord(ts=now, error_type=error_type))

        # Reset consecutive successes
        self._consecutive_successes[provider_id] = 0

        # Increment consecutive failures
        health.consecutive_failures += 1
        health.last_failure_ts = now
        health.reason = error_type

        # Determine new status
        if cooldown_seconds > 0:
            health.status = HealthStatus.COOLDOWN
            health.cooldown_until = now + cooldown_seconds
            health.reason = f"{error_type} (cooldown {cooldown_seconds}s)"
        elif health.consecutive_failures >= self._exhaust_threshold:
            health.status = HealthStatus.EXHAUSTED
            health.reason = f"{error_type} (exhausted after {health.consecutive_failures} failures)"
        elif health.consecutive_failures >= self._degrade_threshold:
            health.status = HealthStatus.DEGRADED
            health.reason = f"{error_type} (degraded after {health.consecutive_failures} failures)"

        logger.info(
            "QuotaSensor: %s failure #%d (%s) → %s",
            provider_id, health.consecutive_failures, error_type, health.status,
        )

        return health

    def report_success(self, provider_id: str) -> TierHealth:
        """Report a provider success. May recover from DEGRADED."""
        now = time.time()
        health = self._ensure_health(provider_id)

        # Record success
        if provider_id not in self._success_history:
            self._success_history[provider_id] = []
        self._success_history[provider_id].append(now)

        # Increment consecutive successes
        self._consecutive_successes[provider_id] = (
            self._consecutive_successes.get(provider_id, 0) + 1
        )

        health.last_success_ts = now

        # Recovery logic
        consec_ok = self._consecutive_successes[provider_id]
        if health.status in (HealthStatus.DEGRADED, HealthStatus.COOLDOWN):
            if consec_ok >= self._recovery_successes:
                health.status = HealthStatus.HEALTHY
                health.consecutive_failures = 0
                health.cooldown_until = 0.0
                health.reason = f"recovered after {consec_ok} consecutive successes"
                logger.info("QuotaSensor: %s recovered → healthy", provider_id)
        elif health.status == HealthStatus.HEALTHY:
            # Already healthy, just reset failure counter
            health.consecutive_failures = 0

        return health

    def report_cooldown(
        self,
        provider_id: str,
        until_ts: float,
        reason: str = "cooldown",
    ) -> TierHealth:
        """Mark a provider as in cooldown until a specific timestamp."""
        health = self._ensure_health(provider_id)
        health.status = HealthStatus.COOLDOWN
        health.cooldown_until = until_ts
        health.reason = reason
        logger.info(
            "QuotaSensor: %s → cooldown until %.0f (%s)",
            provider_id, until_ts, reason,
        )
        return health

    def reset(self, provider_id: str) -> None:
        """Reset a provider's health to healthy."""
        if provider_id in self._health:
            del self._health[provider_id]
        self._failure_history.pop(provider_id, None)
        self._success_history.pop(provider_id, None)
        self._consecutive_successes.pop(provider_id, None)

    # ── Internal ──────────────────────────────────────────────────

    def _ensure_health(self, provider_id: str) -> TierHealth:
        if provider_id not in self._health:
            self._health[provider_id] = TierHealth(
                provider_id=provider_id,
                status=HealthStatus.HEALTHY,
            )
        return self._health[provider_id]

    def _recount(self, provider_id: str, now: float) -> None:
        """Prune events outside the sliding window."""
        cutoff = now - self.HISTORY_WINDOW_S

        # Prune failure history
        if provider_id in self._failure_history:
            self._failure_history[provider_id] = [
                f for f in self._failure_history[provider_id] if f.ts > cutoff
            ]

        # Prune success history
        if provider_id in self._success_history:
            self._success_history[provider_id] = [
                ts for ts in self._success_history[provider_id] if ts > cutoff
            ]
