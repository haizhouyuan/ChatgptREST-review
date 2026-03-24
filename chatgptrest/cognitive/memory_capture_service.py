from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.kernel.event_bus import TraceEvent
from chatgptrest.kernel.memory_manager import (
    MemoryRecord,
    MemorySource,
    MemoryTier,
    SourceType,
)
from chatgptrest.kernel.policy_engine import QualityContext


@dataclass
class MemoryCaptureItem:
    title: str
    content: str
    summary: str = ""
    trace_id: str = ""
    session_id: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    source_system: str = "openclaw"
    source_ref: str = ""
    security_label: str = "internal"
    confidence: float = 0.85
    category: str = "captured_memory"


@dataclass
class MemoryCaptureItemResult:
    ok: bool
    trace_id: str
    title: str
    record_id: str = ""
    category: str = "captured_memory"
    tier: str = ""
    duplicate: bool = False
    message: str = ""
    provenance_quality: str = "complete"
    identity_gaps: list[str] = field(default_factory=list)
    quality_gate: dict[str, Any] = field(default_factory=dict)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "title": self.title,
            "record_id": self.record_id,
            "category": self.category,
            "tier": self.tier,
            "duplicate": self.duplicate,
            "message": self.message,
            "provenance_quality": self.provenance_quality,
            "identity_gaps": list(self.identity_gaps),
            "quality_gate": dict(self.quality_gate),
            "audit_trail": list(self.audit_trail),
        }


@dataclass
class MemoryCaptureResult:
    ok: bool
    results: list[MemoryCaptureItemResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "results": [item.to_dict() for item in self.results],
        }


class MemoryCaptureService:
    def __init__(self, runtime: AdvisorRuntime):
        self._runtime = runtime

    def capture(self, items: list[MemoryCaptureItem]) -> MemoryCaptureResult:
        results = [self._capture_one(item) for item in items]
        return MemoryCaptureResult(ok=all(item.ok for item in results), results=results)

    def _capture_one(self, item: MemoryCaptureItem) -> MemoryCaptureItemResult:
        memory = self._runtime.memory
        if memory is None:
            return MemoryCaptureItemResult(
                ok=False,
                trace_id=item.trace_id or "",
                title=item.title,
                message="memory unavailable",
                provenance_quality="missing_authority",
                identity_gaps=["memory_unavailable"],
            )

        trace_id = item.trace_id or str(uuid.uuid4())
        title = item.title.strip() or "OpenMind memory capture"
        summary = (item.summary or item.content).strip()
        if len(summary) > 280:
            summary = f"{summary[:277]}..."

        identity_gaps = self._identity_gaps(item)
        provenance_quality = "complete" if not identity_gaps else "partial"
        quality_gate = self._quality_gate(item)
        if quality_gate and not quality_gate.get("allowed", False):
            self._emit_capture_event(
                item=item,
                trace_id=trace_id,
                event_type="memory.capture.blocked",
                data={
                    "title": title,
                    "category": item.category.strip() or "captured_memory",
                    "source_ref": item.source_ref.strip(),
                    "role_id": item.role_id.strip(),
                    "identity_gaps": list(identity_gaps),
                    "provenance_quality": provenance_quality,
                    "quality_gate": dict(quality_gate),
                },
            )
            return MemoryCaptureItemResult(
                ok=False,
                trace_id=trace_id,
                title=title,
                category=item.category.strip() or "captured_memory",
                message=quality_gate.get("reason", "blocked"),
                provenance_quality=provenance_quality,
                identity_gaps=identity_gaps,
                quality_gate=quality_gate,
            )

        source_agent = item.agent_id.strip() or item.source_system.strip() or "openclaw"
        record_id = memory.stage_and_promote(
            MemoryRecord(
                category=item.category.strip() or "captured_memory",
                key=title,
                value={
                    "title": title,
                    "summary": summary,
                    "content": item.content,
                    "source_ref": item.source_ref.strip(),
                    "source_system": item.source_system.strip() or "openclaw",
                    "origin_session_id": item.session_id.strip(),
                    "account_id": item.account_id.strip(),
                    "thread_id": item.thread_id.strip(),
                    "trace_id": trace_id,
                    "identity_gaps": list(identity_gaps),
                    "provenance_quality": provenance_quality,
                },
                confidence=max(0.75, min(float(item.confidence), 1.0)),
                source=MemorySource(
                    type=SourceType.USER_INPUT.value,
                    agent=source_agent,
                    role=item.role_id.strip(),
                    session_id=item.session_id.strip(),
                    account_id=item.account_id.strip(),
                    thread_id=item.thread_id.strip(),
                    task_id=trace_id,
                ).to_dict(),
                evidence_span=item.content[:500],
            ),
            MemoryTier.EPISODIC,
            reason="cognitive memory capture",
        )
        audit_trail = memory.audit_trail(record_id)
        duplicate = any(entry.get("action") == "update" for entry in audit_trail)

        self._emit_capture_event(
            item=item,
            trace_id=trace_id,
            event_type="memory.capture",
            data={
                "record_id": record_id,
                "title": title,
                "category": item.category.strip() or "captured_memory",
                "source_ref": item.source_ref.strip(),
                "duplicate": duplicate,
                "cross_session_visible": True,
                "role_id": item.role_id.strip(),
                "identity_gaps": list(identity_gaps),
                "provenance_quality": provenance_quality,
                "quality_gate": dict(quality_gate),
            },
        )

        return MemoryCaptureItemResult(
            ok=True,
            trace_id=trace_id,
            title=title,
            record_id=record_id,
            category=item.category.strip() or "captured_memory",
            tier=MemoryTier.EPISODIC.value,
            duplicate=duplicate,
            message="captured",
            provenance_quality=provenance_quality,
            identity_gaps=identity_gaps,
            quality_gate=quality_gate,
            audit_trail=audit_trail,
        )

    @staticmethod
    def _identity_gaps(item: MemoryCaptureItem) -> list[str]:
        gaps: list[str] = []
        if not item.source_ref.strip():
            gaps.append("missing_source_ref")
        if not item.session_id.strip():
            gaps.append("missing_session_key")
        if not item.agent_id.strip():
            gaps.append("missing_agent_id")
        if not item.account_id.strip():
            gaps.append("missing_account_id")
        if not item.thread_id.strip():
            gaps.append("missing_thread_id")
        return gaps

    def _quality_gate(self, item: MemoryCaptureItem) -> dict[str, Any]:
        policy = self._runtime.policy_engine
        if policy is None:
            return {}
        return policy.run_quality_gate(
            QualityContext(
                audience="internal",
                security_label=item.security_label.strip() or "internal",
                content=item.content,
                estimated_tokens=max(1, len(item.content) // 4),
                channel=item.source_system.strip() or "openclaw",
                risk_level="low",
                execution_success=True,
                business_success=True,
                claims=[],
            )
        ).to_dict()

    def _emit_capture_event(
        self,
        *,
        item: MemoryCaptureItem,
        trace_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        if self._runtime.event_bus is None:
            return
        self._runtime.event_bus.emit(
            TraceEvent.create(
                source=item.source_system.strip() or "openclaw",
                event_type=event_type,
                trace_id=trace_id,
                session_id=item.session_id.strip(),
                security_label=item.security_label.strip() or "internal",
                data=data,
            )
        )
