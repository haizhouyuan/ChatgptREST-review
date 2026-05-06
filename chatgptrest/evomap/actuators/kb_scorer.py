"""KBScorer — usage-based KB artifact quality scoring.

Subscribes to EventBus signals to track KB artifact effectiveness:
  - advisor_ask.kb_direct → successful KB-only answer (positive signal)
  - user.rapid_retry → user immediately retried (negative signal)
  - dispatch.task_failed → downstream task failed (negative signal)

Adjusts quality_score in kb_registry.db based on usage outcomes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .registry import ActuatorMode, GovernedActuatorState

logger = logging.getLogger(__name__)

# Default score adjustments
_SCORE_SUCCESS = 0.1       # kb_direct success without retry
_SCORE_RETRY_PENALTY = -0.2  # user retried within window
_SCORE_INITIAL = 0.5       # initial score for new artifacts
_RETRY_WINDOW_SECONDS = 60  # seconds to detect rapid retry


class KBScorer:
    """EventBus subscriber that scores KB artifacts by usage effectiveness.

    Tracks recent kb_direct events and correlates with retries/failures
    to adjust quality_score in kb_registry.db.
    """

    def __init__(
        self,
        observer: Any = None,
        *,
        mode: ActuatorMode = ActuatorMode.ACTIVE,
        owner: str = "evomap.runtime",
        candidate_version: str = "kb-scorer-live",
        rollback_trigger: str = "score_drift_or_retrieval_quality_regression",
    ) -> None:
        self._observer = observer
        self._lock = threading.Lock()
        self._governance_state = GovernedActuatorState(
            "kb_scorer",
            mode=mode,
            owner=owner,
            candidate_version=candidate_version,
            rollback_trigger=rollback_trigger,
        )
        # Track recent kb_direct events: {trace_id: (timestamp, artifact_ids)}
        self._recent_kb_directs: dict[str, tuple[float, list[str]]] = {}
        # Pending positive scores: scheduled after retry window
        self._pending_timer: threading.Timer | None = None
        logger.info("KBScorer initialized")

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
        if event_type == "advisor_ask.kb_direct":
            self._handle_kb_direct(event)
        elif event_type == "user.rapid_retry":
            self._handle_rapid_retry(event)
        elif event_type == "dispatch.task_failed":
            self._handle_task_failed(event)

    def _handle_kb_direct(self, event: Any) -> None:
        """Record a kb_direct event and schedule positive scoring."""
        data = getattr(event, "data", {}) or {}
        trace_id = getattr(event, "trace_id", "") or ""
        now = time.time()

        # Extract artifact IDs if available
        artifact_ids = data.get("artifact_ids", [])
        if not artifact_ids and data.get("artifact_id"):
            artifact_ids = [data["artifact_id"]]

        with self._lock:
            self._recent_kb_directs[trace_id] = (now, artifact_ids)

        # Schedule a delayed positive score (cancelled if rapid_retry arrives)
        self._schedule_positive_score(trace_id, artifact_ids)

    def _handle_rapid_retry(self, event: Any) -> None:
        """User retried quickly — penalize the KB artifact that served them."""
        data = getattr(event, "data", {}) or {}
        # Find the most recent kb_direct for this trace or any recent one
        trace_id = getattr(event, "trace_id", "") or ""
        now = time.time()

        with self._lock:
            # Check if there was a recent kb_direct
            entry = self._recent_kb_directs.pop(trace_id, None)
            if not entry:
                # Check any recent kb_direct within window
                for tid, (ts, aids) in list(self._recent_kb_directs.items()):
                    if now - ts < _RETRY_WINDOW_SECONDS:
                        entry = (ts, aids)
                        del self._recent_kb_directs[tid]
                        break

        if entry and entry[1]:  # has artifact IDs
            for aid in entry[1]:
                self._update_score(aid, _SCORE_RETRY_PENALTY, "rapid_retry")
            logger.info(
                "KBScorer: penalized %d artifacts for rapid_retry (delta=%.2f)",
                len(entry[1]), _SCORE_RETRY_PENALTY,
            )

    def _handle_task_failed(self, event: Any) -> None:
        """Downstream task failed — mild penalty to recent KB artifact."""
        data = getattr(event, "data", {}) or {}
        trace_id = getattr(event, "trace_id", "") or ""
        now = time.time()

        with self._lock:
            entry = self._recent_kb_directs.pop(trace_id, None)

        if entry and entry[1]:
            for aid in entry[1]:
                self._update_score(aid, -0.05, "downstream_failure")

    def _schedule_positive_score(
        self, trace_id: str, artifact_ids: list[str],
    ) -> None:
        """After retry window passes without retry, award positive score."""
        def _award():
            with self._lock:
                # Only award if still in recent (not claimed by retry)
                entry = self._recent_kb_directs.pop(trace_id, None)
            if entry and entry[1]:
                for aid in entry[1]:
                    self._update_score(aid, _SCORE_SUCCESS, "kb_direct_success")
                logger.info(
                    "KBScorer: awarded %d artifacts for successful kb_direct (delta=+%.2f)",
                    len(entry[1]), _SCORE_SUCCESS,
                )

        timer = threading.Timer(_RETRY_WINDOW_SECONDS, _award)
        timer.daemon = True
        timer.start()

    def _update_score(self, artifact_id: str, delta: float, reason: str) -> None:
        """Update KB artifact quality_score via observer."""
        audit_event = self._governance_state.record(
            category="state_change",
            action="score_updated",
            previous_state=None,
            new_state=None,
            reason=reason,
            metadata={
                "artifact_id": artifact_id,
                "delta": delta,
                "mode": self.governance["mode"],
            },
        )
        if self._observer and hasattr(self._observer, "update_kb_score"):
            new_score = self._observer.update_kb_score(artifact_id, delta)
            # Emit signal for audit trail
            try:
                self._observer.record_event(
                    trace_id="",
                    signal_type="kb.artifact_helpful" if delta > 0 else "kb.artifact_penalized",
                    source="kb_scorer",
                    domain="kb",
                    data={
                        "artifact_id": artifact_id,
                        "delta": delta,
                        "new_score": new_score,
                        "reason": reason,
                        "governance": self.describe_governance(),
                        "audit_event": audit_event,
                    },
                )
            except Exception:
                pass  # fail-open

    def cleanup_stale(self) -> None:
        """Remove kb_direct entries older than the retry window."""
        now = time.time()
        with self._lock:
            stale = [
                tid for tid, (ts, _) in self._recent_kb_directs.items()
                if now - ts > _RETRY_WINDOW_SECONDS * 2
            ]
            for tid in stale:
                del self._recent_kb_directs[tid]
