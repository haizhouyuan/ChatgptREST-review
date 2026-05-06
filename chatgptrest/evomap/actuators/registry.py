"""Governance primitives for EvoMap actuators.

Lane C adds metadata and audit visibility around existing actuators without
changing their default runtime behavior. The registry is intentionally
in-memory and local to the actuator package so it can be adopted without
touching broader contracts or durable schemas.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ActuatorMode(str, Enum):
    """Rollout mode for a runtime actuator."""

    OBSERVE_ONLY = "observe_only"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"


@dataclass(frozen=True)
class ActuatorGovernance:
    """Human-readable governance metadata for one actuator."""

    name: str
    mode: ActuatorMode = ActuatorMode.ACTIVE
    owner: str = "self-iteration-v2"
    candidate_version: str = "live"
    rollback_trigger: str = "manual_rollback_on_runtime_regression"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        return payload


@dataclass(frozen=True)
class ActuatorAuditEvent:
    """Immutable audit event emitted by a governed actuator."""

    timestamp: float
    actuator: str
    category: str
    action: str
    previous_state: str | None = None
    new_state: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class GovernedActuatorState:
    """Shared governance/audit helper used by existing actuators."""

    def __init__(
        self,
        name: str,
        *,
        mode: ActuatorMode = ActuatorMode.ACTIVE,
        owner: str = "self-iteration-v2",
        candidate_version: str = "live",
        rollback_trigger: str = "manual_rollback_on_runtime_regression",
    ) -> None:
        self._lock = threading.Lock()
        self._governance = ActuatorGovernance(
            name=name,
            mode=mode,
            owner=owner,
            candidate_version=candidate_version,
            rollback_trigger=rollback_trigger,
        )
        self._events: list[ActuatorAuditEvent] = []

    @property
    def governance(self) -> ActuatorGovernance:
        return self._governance

    def describe(self) -> dict[str, Any]:
        return self._governance.as_dict()

    def record(
        self,
        *,
        category: str,
        action: str,
        previous_state: str | None = None,
        new_state: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = ActuatorAuditEvent(
            timestamp=time.time(),
            actuator=self._governance.name,
            category=category,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._events.append(event)
        return event.as_dict()

    def update_governance(
        self,
        *,
        mode: ActuatorMode | str | None = None,
        owner: str | None = None,
        candidate_version: str | None = None,
        rollback_trigger: str | None = None,
        reason: str = "governance_update",
    ) -> dict[str, Any]:
        current = self._governance
        next_mode = current.mode if mode is None else ActuatorMode(mode)
        updated = ActuatorGovernance(
            name=current.name,
            mode=next_mode,
            owner=current.owner if owner is None else owner,
            candidate_version=(
                current.candidate_version
                if candidate_version is None
                else candidate_version
            ),
            rollback_trigger=(
                current.rollback_trigger
                if rollback_trigger is None
                else rollback_trigger
            ),
        )
        self._governance = updated
        return self.record(
            category="governance",
            action="metadata_updated",
            previous_state=current.mode.value,
            new_state=updated.mode.value,
            reason=reason,
            metadata={
                "owner": updated.owner,
                "candidate_version": updated.candidate_version,
                "rollback_trigger": updated.rollback_trigger,
            },
        )

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [event.as_dict() for event in self._events]
