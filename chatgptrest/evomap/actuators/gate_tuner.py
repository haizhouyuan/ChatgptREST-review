"""GateAutoTuner — auto-adjusts quality gate thresholds.

Monitors the pass/fail ratio of quality gates and correlates with
downstream task outcomes. Tightens thresholds when gates are too
permissive (high pass rate + downstream failures), loosens when
gates are too restrictive (low pass rate).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .registry import ActuatorMode, GovernedActuatorState

logger = logging.getLogger(__name__)

# Default configuration
_CHECK_INTERVAL = 50        # re-evaluate every N gate events
_TIGHTEN_STEP = 0.05        # increase threshold by this much (fast tighten)
_LOOSEN_STEP = 0.01         # decrease threshold by this much (slow loosen — AIMD)
_HIGH_PASS_RATE = 0.90      # pass rate above this → consider tightening
_LOW_PASS_RATE = 0.60       # pass rate below this → consider loosening
_DOWNSTREAM_FAIL_RATE = 0.05  # downstream fail rate above this → tighten
_MIN_ADJUST_INTERVAL_S = 5.0   # minimum seconds between threshold changes


class GateAutoTuner:
    """EventBus subscriber that auto-adjusts quality gate thresholds.

    Tracks gate.passed / gate.failed / dispatch.task_failed events and
    periodically adjusts the quality threshold used by advisor graph gates.

    The current threshold is stored in-memory and can be read by the
    advisor graph's quality gate nodes via ``get_threshold()``.
    """

    def __init__(
        self,
        observer: Any = None,
        initial_threshold: float = 0.6,
        min_threshold: float = 0.3,
        max_threshold: float = 0.95,
        *,
        mode: ActuatorMode = ActuatorMode.ACTIVE,
        owner: str = "evomap.runtime",
        candidate_version: str = "gate-tuner-live",
        rollback_trigger: str = "threshold_regression_or_false_gate_decisions",
    ) -> None:
        self._observer = observer
        self._threshold = max(min_threshold, min(max_threshold, initial_threshold))
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        self._lock = threading.Lock()
        self._governance_state = GovernedActuatorState(
            "gate_tuner",
            mode=mode,
            owner=owner,
            candidate_version=candidate_version,
            rollback_trigger=rollback_trigger,
        )

        # Counters (reset after each evaluation)
        self._gate_passed = 0
        self._gate_failed = 0
        self._task_failed = 0
        self._total_events = 0
        self._last_adjust_time: float = 0.0  # time-based AIMD throttle

        logger.info(
            "GateAutoTuner initialized: threshold=%.2f range=[%.2f, %.2f]",
            self._threshold, self._min_threshold, self._max_threshold,
        )

    @property
    def threshold(self) -> float:
        """Current quality gate threshold. Thread-safe read."""
        return self._threshold

    def get_threshold(self) -> float:
        """Get current quality gate threshold (alias for property)."""
        return self._threshold

    @property
    def governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def describe_governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def get_audit_trail(self) -> list[dict[str, Any]]:
        return self._governance_state.snapshot()

    def update_governance(self, **kwargs: Any) -> dict[str, Any]:
        return self._governance_state.update_governance(**kwargs)

    def on_event(self, event: Any) -> None:
        """EventBus subscriber callback."""
        event_type = getattr(event, "event_type", "") or ""

        with self._lock:
            if event_type == "gate.passed":
                self._gate_passed += 1
                self._total_events += 1
            elif event_type == "gate.failed":
                self._gate_failed += 1
                self._total_events += 1
            elif event_type == "dispatch.task_failed":
                self._task_failed += 1

            # Check if time to re-evaluate
            if self._total_events >= _CHECK_INTERVAL:
                self._evaluate()

    def _evaluate(self) -> None:
        """Re-evaluate and adjust threshold based on accumulated stats."""
        total_gates = self._gate_passed + self._gate_failed
        if total_gates == 0:
            self._reset_counters()
            return

        pass_rate = self._gate_passed / total_gates
        downstream_fail_rate = (
            self._task_failed / self._gate_passed
            if self._gate_passed > 0 else 0
        )

        old_threshold = self._threshold

        # Time-based throttle: prevent rapid threshold changes under high QPS.
        # Even though _evaluate fires every 50 gate events, at 50+ QPS that's
        # sub-second. Enforce minimum interval to smooth recovery slope.
        now = time.monotonic()
        if (now - self._last_adjust_time) < _MIN_ADJUST_INTERVAL_S:
            self._reset_counters()
            return

        # Decision logic
        if pass_rate > _HIGH_PASS_RATE and downstream_fail_rate > _DOWNSTREAM_FAIL_RATE:
            # Too permissive: high pass rate + downstream failures → tighten
            self._threshold = min(
                self._max_threshold,
                self._threshold + _TIGHTEN_STEP,
            )
            reason = (
                f"tighten: pass_rate={pass_rate:.2f} "
                f"downstream_fail={downstream_fail_rate:.2f}"
            )
        elif pass_rate < _LOW_PASS_RATE:
            # Too restrictive: low pass rate → loosen
            self._threshold = max(
                self._min_threshold,
                self._threshold - _LOOSEN_STEP,
            )
            reason = f"loosen: pass_rate={pass_rate:.2f}"
        else:
            reason = "no_change"

        # Log and emit signal if threshold changed
        if self._threshold != old_threshold:
            self._last_adjust_time = now
            audit_event = self._governance_state.record(
                category="state_change",
                action="threshold_adjusted",
                previous_state=f"{old_threshold:.2f}",
                new_state=f"{self._threshold:.2f}",
                reason=reason,
                metadata={
                    "passed": self._gate_passed,
                    "failed": self._gate_failed,
                    "downstream_failures": self._task_failed,
                    "mode": self.governance["mode"],
                },
            )
            logger.info(
                "GateAutoTuner: threshold %.2f → %.2f (%s) "
                "[passed=%d failed=%d downstream_fail=%d]",
                old_threshold, self._threshold, reason,
                self._gate_passed, self._gate_failed, self._task_failed,
            )
            self._emit_signal(old_threshold, self._threshold, reason, audit_event)

        self._reset_counters()

    def _reset_counters(self) -> None:
        self._gate_passed = 0
        self._gate_failed = 0
        self._task_failed = 0
        self._total_events = 0

    def _emit_signal(
        self,
        old_threshold: float,
        new_threshold: float,
        reason: str,
        audit_event: dict[str, Any] | None = None,
    ) -> None:
        if not self._observer:
            return
        try:
            self._observer.record_event(
                trace_id="",
                signal_type="actuator.gate_tuned",
                source="gate_tuner",
                domain="actuator",
                data={
                    "old_threshold": old_threshold,
                    "new_threshold": new_threshold,
                    "reason": reason,
                    "governance": self.describe_governance(),
                    "audit_event": audit_event,
                },
            )
        except Exception:
            pass  # fail-open
