"""CircuitBreaker — real-time provider health actuator.

Subscribes to EventBus llm.call_failed / llm.call_completed signals and
maintains a sliding window of failures per provider. When thresholds are
breached, pushes state updates to the HealthTracker, causing the routing
fabric to automatically bypass degraded providers.

Thresholds (configurable):
  - 3 consecutive failures → DEGRADED (5 min)
  - 5 failures in 5 min window → COOLDOWN (10 min)
  - avg latency > 20s for healthy calls → DEGRADED

Recovery:
  - After cooldown period expires, provider automatically returns to HEALTHY
  - A single success resets the consecutive failure counter
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .registry import ActuatorMode, GovernedActuatorState

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────

@dataclass
class CircuitBreakerConfig:
    """Tunables for the circuit breaker."""
    window_seconds: int = 300           # 5-minute sliding window
    consecutive_fail_threshold: int = 3  # → DEGRADED
    window_fail_threshold: int = 5       # → COOLDOWN
    cooldown_seconds: int = 600          # 10-minute cooldown
    degraded_seconds: int = 300          # 5-minute degradation
    latency_threshold_ms: int = 20_000   # avg latency → DEGRADED
    # Half-open probe: after this many seconds in OFFLINE, transition to
    # HALF_OPEN so the next success can recover the provider.
    # Set to 0 to disable (permanently offline until manual reset).
    offline_probe_seconds: int = 1800    # 30-minute half-open probe


# ── Per-provider state ────────────────────────────────────────────

@dataclass
class _ProviderWindow:
    """Sliding window state for one provider."""
    failures: deque = field(default_factory=deque)      # deque of (timestamp, error_category)
    successes: deque = field(default_factory=deque)      # deque of (timestamp, latency_ms)
    consecutive_failures: int = 0
    state: str = "healthy"           # healthy | degraded | cooldown | offline | half_open
    state_until: float = 0.0         # Unix timestamp when state expires
    last_action_time: float = 0.0    # prevent rapid re-triggering
    offline_since: float = 0.0       # When provider went offline (for half-open probe)


class CircuitBreaker:
    """Real-time EventBus subscriber that reacts to LLM failures.

    Usage::

        breaker = CircuitBreaker(observer=evomap_observer)
        breaker.on_event(event)  # called by EventBus for each event

    The breaker also accepts an optional HealthTracker reference to push
    state updates into the routing fabric's real-time health system.
    """

    def __init__(
        self,
        observer: Any = None,
        health_tracker: Any = None,
        config: CircuitBreakerConfig | None = None,
        *,
        mode: ActuatorMode = ActuatorMode.ACTIVE,
        owner: str = "evomap.runtime",
        candidate_version: str = "circuit-breaker-live",
        rollback_trigger: str = "provider_misclassification_or_routing_regression",
    ) -> None:
        self._observer = observer
        self._health_tracker = health_tracker
        self._config = config or CircuitBreakerConfig()
        self._windows: dict[str, _ProviderWindow] = defaultdict(_ProviderWindow)
        self._lock = threading.Lock()
        self._governance_state = GovernedActuatorState(
            "circuit_breaker",
            mode=mode,
            owner=owner,
            candidate_version=candidate_version,
            rollback_trigger=rollback_trigger,
        )
        logger.info(
            "CircuitBreaker initialized: window=%ds fail_threshold=%d/%d cooldown=%ds",
            self._config.window_seconds,
            self._config.consecutive_fail_threshold,
            self._config.window_fail_threshold,
            self._config.cooldown_seconds,
        )

    @property
    def governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def describe_governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def get_audit_trail(self) -> list[dict[str, Any]]:
        return self._governance_state.snapshot()

    def update_governance(self, **kwargs: Any) -> dict[str, Any]:
        return self._governance_state.update_governance(**kwargs)

    # ── EventBus subscriber interface ─────────────────────────────

    def on_event(self, event: Any) -> None:
        """EventBus subscriber callback. Routes to appropriate handler."""
        event_type = getattr(event, "event_type", "") or ""
        if event_type == "llm.call_failed":
            self._handle_failure(event)
        elif event_type == "llm.call_completed":
            self._handle_success(event)

    # ── Internal handlers ─────────────────────────────────────────

    def _handle_failure(self, event: Any) -> None:
        data = getattr(event, "data", {}) or {}
        provider = self._extract_provider(data)
        if not provider:
            return

        # P0: Error isolation — only count infrastructure errors.
        # Business/payload errors (context_exceeded, json_decode, format_error)
        # should NOT trigger circuit breaking, as the provider itself is healthy.
        error_category = data.get("error_category", "unknown")
        _INFRA_ERRORS = {
            "timeout", "rate_limit_429",
            "provider_500", "provider_502", "provider_503", "provider_504",
            "connection_error", "unknown",
        }
        _FATAL_ERRORS = {"auth_error"}  # permanent — skip retry, go offline

        if error_category in _FATAL_ERRORS:
            logger.error(
                "CircuitBreaker: FATAL error %s for %s → immediate offline",
                error_category, provider,
            )
            with self._lock:
                w = self._windows[provider]
                old_state = w.state
                w.state = "offline"
                w.offline_since = time.time()
                if self._config.offline_probe_seconds > 0:
                    # Half-open probe: transition to half_open after probe interval
                    w.state_until = w.offline_since + self._config.offline_probe_seconds
                else:
                    w.state_until = float("inf")
            self._push_to_health_tracker(provider, "offline")
            audit_event = self._record_state_change(
                provider,
                action="offline",
                from_state=old_state,
                to_state="offline",
                reason=error_category,
                metadata={"mode": self.governance["mode"]},
            )
            self._emit_signal(
                provider, "offline", old_state, "offline", error_category, audit_event,
            )
            return

        if error_category not in _INFRA_ERRORS:
            logger.debug(
                "CircuitBreaker: ignoring non-infra error %s for %s",
                error_category, provider,
            )
            return

        now = time.time()

        with self._lock:
            w = self._windows[provider]
            self._prune_window(w, now)

            w.failures.append((now, error_category))
            w.consecutive_failures += 1

            # Only skip if already in cooldown or offline (can't escalate).
            # Allow degraded → cooldown escalation when window threshold met.
            if w.state in ("cooldown", "offline") and now < w.state_until:
                return  # already at maximum severity

            # Threshold 1: consecutive failures → DEGRADED
            if w.consecutive_failures >= self._config.consecutive_fail_threshold:
                if w.state != "degraded" or now - w.last_action_time > 30:
                    self._trigger_degraded(provider, w, now, error_category)
                    return

            # Threshold 2: window failures → COOLDOWN
            if len(w.failures) >= self._config.window_fail_threshold:
                if w.state != "cooldown" or now - w.last_action_time > 30:
                    self._trigger_cooldown(provider, w, now, error_category)

    def _handle_success(self, event: Any) -> None:
        data = getattr(event, "data", {}) or {}
        provider = self._extract_provider(data)
        if not provider:
            return

        now = time.time()
        latency_ms = data.get("latency_ms", 0)

        with self._lock:
            w = self._windows[provider]
            self._prune_window(w, now)

            w.successes.append((now, latency_ms))
            w.consecutive_failures = 0  # reset on success

            # Half-open recovery: if in half_open and we get a success → recover
            if w.state == "half_open":
                old_state = w.state
                w.state = "healthy"
                w.state_until = 0.0
                w.offline_since = 0.0
                logger.info(
                    "CircuitBreaker: %s half-open probe SUCCESS → healthy",
                    provider,
                )
                audit_event = self._record_state_change(
                    provider,
                    action="recovered",
                    from_state=old_state,
                    to_state="healthy",
                    reason="half_open_success",
                    metadata={"mode": self.governance["mode"]},
                )
                self._emit_signal(
                    provider, "recovered", old_state, "healthy", audit_event=audit_event,
                )
                self._push_to_health_tracker(provider, "healthy")
                return

            # Check if state expired → auto-recover
            if w.state not in ("healthy", "offline") and now >= w.state_until:
                old_state = w.state
                w.state = "healthy"
                w.state_until = 0.0
                logger.info(
                    "CircuitBreaker: %s recovered from %s → healthy",
                    provider, old_state,
                )
                audit_event = self._record_state_change(
                    provider,
                    action="recovered",
                    from_state=old_state,
                    to_state="healthy",
                    reason="timer_expired_success",
                    metadata={"mode": self.governance["mode"]},
                )
                self._emit_signal(
                    provider, "recovered", old_state, "healthy", audit_event=audit_event,
                )
                self._push_to_health_tracker(provider, "healthy")

            # Check latency threshold
            if w.state == "healthy" and len(w.successes) >= 3:
                recent = [lat for _, lat in list(w.successes)[-5:]]
                avg_lat = sum(recent) / len(recent)
                if avg_lat > self._config.latency_threshold_ms:
                    self._trigger_degraded(
                        provider, w, now, f"high_latency_avg_{int(avg_lat)}ms",
                    )

    # ── State transitions ─────────────────────────────────────────

    def _trigger_degraded(
        self, provider: str, w: _ProviderWindow, now: float, reason: str,
    ) -> None:
        old_state = w.state
        w.state = "degraded"
        w.state_until = now + self._config.degraded_seconds
        w.last_action_time = now
        logger.warning(
            "CircuitBreaker: %s → DEGRADED for %ds (reason=%s, failures=%d)",
            provider, self._config.degraded_seconds, reason, w.consecutive_failures,
        )
        audit_event = self._record_state_change(
            provider,
            action="degraded",
            from_state=old_state,
            to_state="degraded",
            reason=reason,
            metadata={
                "consecutive_failures": w.consecutive_failures,
                "window_failures": len(w.failures),
                "mode": self.governance["mode"],
            },
        )
        self._emit_signal(
            provider, "degraded", old_state, "degraded", reason, audit_event,
        )
        self._push_to_health_tracker(provider, "degraded")

    def _trigger_cooldown(
        self, provider: str, w: _ProviderWindow, now: float, reason: str,
    ) -> None:
        old_state = w.state
        w.state = "cooldown"
        w.state_until = now + self._config.cooldown_seconds
        w.last_action_time = now
        logger.warning(
            "CircuitBreaker: %s → COOLDOWN for %ds (reason=%s, window_failures=%d)",
            provider, self._config.cooldown_seconds, reason, len(w.failures),
        )
        audit_event = self._record_state_change(
            provider,
            action="cooldown",
            from_state=old_state,
            to_state="cooldown",
            reason=reason,
            metadata={
                "consecutive_failures": w.consecutive_failures,
                "window_failures": len(w.failures),
                "mode": self.governance["mode"],
            },
        )
        self._emit_signal(
            provider, "cooldown", old_state, "cooldown", reason, audit_event,
        )
        self._push_to_health_tracker(provider, "cooldown")

    # ── Integration with HealthTracker ────────────────────────────

    def _push_to_health_tracker(self, provider: str, new_status: str) -> None:
        """Push state change to the routing fabric's HealthTracker.

        Uses HealthTracker's actual API:
        - degraded → record_failure() (triggers HealthTracker's own degradation logic)
        - cooldown → record_cooldown() (enters timed cooldown)
        - healthy  → set_online() (clears offline/degraded state)
        """
        if not self._health_tracker:
            return
        try:
            if new_status == "offline":
                # FATAL: permanent offline — use dedicated set_offline() API
                self._health_tracker.set_offline(
                    provider, reason="circuit_breaker_fatal",
                )
            elif new_status == "cooldown":
                self._health_tracker.record_cooldown(
                    provider, seconds=self._config.cooldown_seconds,
                )
            elif new_status == "degraded":
                self._health_tracker.record_failure(
                    provider, error_type="circuit_breaker_degraded",
                )
            elif new_status == "healthy":
                # Recovery: clear any offline state
                if hasattr(self._health_tracker, "set_online"):
                    self._health_tracker.set_online(provider)
            logger.info(
                "CircuitBreaker → HealthTracker: %s = %s", provider, new_status,
            )
        except Exception as e:
            logger.warning("CircuitBreaker→HealthTracker push failed: %s", e)

    # ── Signal emission ───────────────────────────────────────────

    def _emit_signal(
        self,
        provider: str,
        action: str,
        from_state: str,
        to_state: str,
        reason: str = "",
        audit_event: dict[str, Any] | None = None,
    ) -> None:
        if not self._observer:
            return
        try:
            self._observer.record_event(
                trace_id="",
                signal_type="actuator.circuit_break",
                source="circuit_breaker",
                domain="actuator",
                data={
                    "provider": provider,
                    "action": action,
                    "from_state": from_state,
                    "to_state": to_state,
                    "reason": reason,
                    "governance": self.describe_governance(),
                    "audit_event": audit_event,
                },
            )
        except Exception:
            pass  # fail-open

    def _record_state_change(
        self,
        provider: str,
        *,
        action: str,
        from_state: str,
        to_state: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._governance_state.record(
            category="state_change",
            action=action,
            previous_state=from_state,
            new_state=to_state,
            reason=reason,
            metadata={"provider": provider, **(metadata or {})},
        )

    # ── Helpers ────────────────────────────────────────────────────

    def _prune_window(self, w: _ProviderWindow, now: float) -> None:
        """Remove entries older than the sliding window."""
        cutoff = now - self._config.window_seconds
        while w.failures and w.failures[0][0] < cutoff:
            w.failures.popleft()
        while w.successes and w.successes[0][0] < cutoff:
            w.successes.popleft()

    @staticmethod
    def _extract_provider(data: dict) -> str:
        """Extract provider identifier from event data."""
        # Various signal formats use different keys
        return (
            data.get("provider_id")
            or data.get("provider")
            or data.get("model", "").split("/")[0]
            or ""
        )

    # ── Introspection ─────────────────────────────────────────────

    def get_status(self) -> dict[str, dict]:
        """Return current state of all tracked providers.

        Materializes state transitions on read:
        - Timer-expired degraded/cooldown → healthy (with HealthTracker sync)
        - Timer-expired offline → half_open (probe mode)
        """
        now = time.time()
        result = {}
        recovered = []  # collect (provider, old_state) for post-lock push
        with self._lock:
            for provider, w in self._windows.items():
                self._prune_window(w, now)

                # Materialize state transitions on timer expiry
                if w.state in ("degraded", "cooldown") and now >= w.state_until:
                    old = w.state
                    w.state = "healthy"
                    w.state_until = 0.0
                    recovered.append((provider, old))
                elif w.state == "offline" and now >= w.state_until and w.state_until != float("inf"):
                    # Half-open probe: transition from offline to half_open
                    old = w.state
                    w.state = "half_open"
                    w.state_until = 0.0
                    logger.info(
                        "CircuitBreaker: %s offline expired → HALF_OPEN probe",
                        provider,
                    )
                    audit_event = self._record_state_change(
                        provider,
                        action="half_open",
                        from_state=old,
                        to_state="half_open",
                        reason="offline_probe_expired",
                        metadata={"mode": self.governance["mode"]},
                    )
                    self._emit_signal(
                        provider, "half_open", old, "half_open", audit_event=audit_event,
                    )

                result[provider] = {
                    "state": w.state,
                    "consecutive_failures": w.consecutive_failures,
                    "window_failures": len(w.failures),
                    "window_successes": len(w.successes),
                    "state_until": w.state_until,
                    "seconds_remaining": max(0, w.state_until - now) if w.state_until != float("inf") else float("inf"),
                }

        # Push recovered states outside lock
        for provider, old_state in recovered:
            self._push_to_health_tracker(provider, "healthy")
            audit_event = self._record_state_change(
                provider,
                action="recovered",
                from_state=old_state,
                to_state="healthy",
                reason="timer_expired_read_path",
                metadata={"mode": self.governance["mode"]},
            )
            self._emit_signal(
                provider, "recovered", old_state, "healthy", audit_event=audit_event,
            )

        return result

    def reset_provider(self, provider: str) -> bool:
        """Admin API: manually reset a provider from offline to healthy.

        Returns True if provider was reset, False if not found.
        """
        with self._lock:
            if provider not in self._windows:
                return False
            w = self._windows[provider]
            old_state = w.state
            w.state = "healthy"
            w.state_until = 0.0
            w.offline_since = 0.0
            w.consecutive_failures = 0
            w.failures.clear()

        self._push_to_health_tracker(provider, "healthy")
        audit_event = self._record_state_change(
            provider,
            action="admin_reset",
            from_state=old_state,
            to_state="healthy",
            reason="manual_reset",
            metadata={"mode": self.governance["mode"]},
        )
        self._emit_signal(
            provider, "admin_reset", old_state, "healthy", audit_event=audit_event,
        )
        logger.info(
            "CircuitBreaker: %s manually reset from %s → healthy",
            provider, old_state,
        )
        return True
