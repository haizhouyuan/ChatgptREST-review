"""Feedback collector — bridges execution outcomes to HealthTracker and EvoMap.

After each LLM call, the caller reports the outcome. This module
routes that feedback to the appropriate sinks.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .health_tracker import HealthTracker
from .types import ExecutionOutcome

logger = logging.getLogger(__name__)


class FeedbackCollector:
    """Collects execution outcomes and updates health + observability.

    Dual-write:
      1. HealthTracker: real-time provider availability
      2. EvoMap observer (if provided): long-term quality learning
    """

    def __init__(
        self,
        health_tracker: HealthTracker,
        evomap_observer: Any = None,
        on_quality_update: Callable[[str, str, float], None] | None = None,
    ):
        self._health = health_tracker
        self._evomap = evomap_observer
        self._on_quality_update = on_quality_update

    def report(self, outcome: ExecutionOutcome) -> None:
        """Process an execution outcome.

        Args:
            outcome: Result of an LLM call.
        """
        if not outcome.timestamp:
            outcome.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        # 1. Update HealthTracker
        if outcome.success:
            self._health.record_success(
                outcome.provider_id,
                latency_ms=outcome.latency_ms,
            )
        elif outcome.cooldown_seconds:
            self._health.record_cooldown(
                outcome.provider_id,
                seconds=outcome.cooldown_seconds,
            )
        else:
            self._health.record_failure(
                outcome.provider_id,
                error_type=outcome.error_type or "",
                latency_ms=outcome.latency_ms,
            )

        # 2. Update quality history if quality_score provided
        if outcome.quality_score is not None and self._on_quality_update:
            try:
                self._on_quality_update(
                    outcome.provider_id,
                    outcome.task_type,
                    outcome.quality_score,
                )
            except Exception as e:
                logger.warning("Quality update callback failed: %s", e)

        # 3. Emit to EvoMap
        if self._evomap:
            try:
                self._emit_evomap_signal(outcome)
            except Exception as e:
                logger.warning(
                    "EvoMap signal emission failed for provider=%s trace=%s: %s",
                    outcome.provider_id, outcome.trace_id, e,
                )

        logger.info(
            "Feedback recorded: provider=%s %s task=%s latency=%dms trace=%s%s",
            outcome.provider_id,
            "✓" if outcome.success else "✗",
            outcome.task_type,
            outcome.latency_ms,
            outcome.trace_id or "-",
            f" error={outcome.error_type}" if outcome.error_type else "",
        )

    def emit_fallback(
        self,
        *,
        trace_id: str,
        task_type: str,
        from_provider_id: str,
        to_provider_id: str,
        attempt_index: int,
        total_candidates: int,
        error_type: str | None = None,
        latency_ms: int = 0,
    ) -> None:
        """Emit an explicit routing fallback transition to EvoMap."""
        if not self._evomap:
            return
        try:
            from chatgptrest.evomap.signals import SignalType
            signal_type = SignalType.ROUTE_FALLBACK
        except ImportError:
            logger.debug("EvoMap signals module not available, skipping fallback emit")
            return

        payload = {
            "task_type": task_type,
            "from_provider_id": from_provider_id,
            "to_provider_id": to_provider_id,
            "attempt_index": attempt_index,
            "total_candidates": total_candidates,
            "latency_ms": latency_ms,
        }
        if error_type:
            payload["error_type"] = error_type

        self._evomap.emit(
            signal_type=signal_type,
            payload=payload,
            trace_id=trace_id or "",
            source="routing_fabric",
            domain="routing",
        )

    def _emit_evomap_signal(self, outcome: ExecutionOutcome) -> None:
        """Emit a routing outcome signal to EvoMap."""
        try:
            from chatgptrest.evomap.signals import SignalType
            signal_type = SignalType.ROUTE_CANDIDATE_OUTCOME
        except ImportError:
            logger.debug("EvoMap signals module not available, skipping emit")
            return

        payload = {
            "provider_id": outcome.provider_id,
            "task_type": outcome.task_type,
            "success": outcome.success,
            "latency_ms": outcome.latency_ms,
            "error_type": outcome.error_type,
        }
        if outcome.quality_score is not None:
            payload["quality_score"] = outcome.quality_score
        if outcome.cooldown_seconds:
            payload["cooldown_seconds"] = outcome.cooldown_seconds

        self._evomap.emit(
            signal_type=signal_type,
            payload=payload,
            trace_id=outcome.trace_id or "",
        )
