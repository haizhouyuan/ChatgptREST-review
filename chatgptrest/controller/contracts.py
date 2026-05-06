from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ControllerArtifact:
    artifact_id: str
    kind: str
    title: str
    work_id: str | None = None
    path: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ControllerCheckpoint:
    checkpoint_id: str
    title: str
    status: str
    blocking: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EffectIntent:
    intent_id: str
    effect_type: str
    payload: dict[str, Any]
    requires_approval: bool
    required_capabilities: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    status: str = "planned"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StepResult:
    work_status: str
    controller_status: str
    summary: str
    next_action: dict[str, Any]
    output: dict[str, Any] = field(default_factory=dict)
    delivery: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ControllerArtifact] = field(default_factory=list)
    checkpoints: list[ControllerCheckpoint] = field(default_factory=list)
    effect_intents: list[EffectIntent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_status": self.work_status,
            "controller_status": self.controller_status,
            "summary": self.summary,
            "next_action": dict(self.next_action),
            "output": dict(self.output),
            "delivery": dict(self.delivery),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
            "effect_intents": [intent.to_dict() for intent in self.effect_intents],
        }
