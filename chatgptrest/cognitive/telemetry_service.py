from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.evomap.signals import normalize_signal_type
from chatgptrest.kernel.event_bus import TraceEvent
from chatgptrest.kernel.memory_manager import MemoryRecord, MemorySource, MemoryTier, SourceType
from chatgptrest.telemetry_contract import apply_identity_defaults, extract_identity_fields


@dataclass
class TelemetryEventInput:
    event_type: str
    source: str = "openclaw"
    domain: str = "execution"
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    security_label: str = "internal"
    event_id: str = ""
    run_id: str = ""
    parent_run_id: str = ""
    job_id: str = ""
    issue_id: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    repo_name: str = ""
    repo_path: str = ""
    repo_branch: str = ""
    repo_head: str = ""
    repo_upstream: str = ""
    agent_name: str = ""
    agent_source: str = ""
    provider: str = ""
    model: str = ""
    commit_sha: str = ""


@dataclass
class TelemetryIngestResult:
    ok: bool
    trace_id: str
    recorded: int
    signal_types: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "recorded": self.recorded,
            "signal_types": list(self.signal_types),
        }


class TelemetryIngestService:
    def __init__(self, runtime: AdvisorRuntime):
        self._runtime = runtime

    def ingest(
        self,
        *,
        trace_id: str,
        session_id: str,
        events: list[TelemetryEventInput],
    ) -> TelemetryIngestResult:
        if not trace_id:
            trace_id = str(uuid.uuid4())

        recorded = 0
        signal_types: list[str] = []
        for item in events:
            signal_type = normalize_signal_type(item.event_type)
            raw_payload = dict(item.data or {})
            identity = extract_identity_fields(
                {
                    **raw_payload,
                    "event_id": item.event_id,
                    "run_id": item.run_id,
                    "parent_run_id": item.parent_run_id,
                    "job_id": item.job_id,
                    "issue_id": item.issue_id,
                    "task_ref": item.task_ref,
                    "logical_task_id": item.logical_task_id,
                    "repo_name": item.repo_name,
                    "repo_path": item.repo_path,
                    "repo_branch": item.repo_branch,
                    "repo_head": item.repo_head,
                    "repo_upstream": item.repo_upstream,
                    "agent_name": item.agent_name,
                    "agent_source": item.agent_source,
                    "provider": item.provider,
                    "model": item.model,
                    "commit_sha": item.commit_sha,
                },
                event_type=signal_type,
                trace_id=trace_id,
                session_id=item.session_id or session_id,
                source=item.source,
            )
            payload = apply_identity_defaults(raw_payload, identity=identity)
            upstream_event_id = identity.get("upstream_event_id") or identity.get("event_id")
            if upstream_event_id:
                payload.setdefault("upstream_event_id", upstream_event_id)
            event = TraceEvent(
                event_id=upstream_event_id or uuid.uuid4().hex,
                source=item.source,
                event_type=signal_type,
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                data=payload,
                session_id=item.session_id or session_id,
                security_label=item.security_label,
            )

            if self._runtime.event_bus is not None:
                emitted = self._runtime.event_bus.emit(event)
                if not emitted:
                    continue
            elif self._runtime.observer is not None:
                self._runtime.observer.record_event(
                    trace_id=trace_id,
                    signal_type=signal_type,
                    source=item.source,
                    domain=item.domain,
                    data=payload,
                )

            self._mirror_feedback_memory(
                trace_id=trace_id,
                session_id=item.session_id or session_id,
                signal_type=signal_type,
                source=item.source,
                data=payload,
            )
            recorded += 1
            signal_types.append(signal_type)

        return TelemetryIngestResult(
            ok=True,
            trace_id=trace_id,
            recorded=recorded,
            signal_types=signal_types,
        )

    def _mirror_feedback_memory(
        self,
        *,
        trace_id: str,
        session_id: str,
        signal_type: str,
        source: str,
        data: dict[str, Any],
    ) -> None:
        if self._runtime.memory is None:
            return
        if signal_type not in {
            "tool.completed",
            "tool.failed",
            "workflow.completed",
            "workflow.failed",
            "user.feedback",
        }:
            return

        summary = {
            "signal_type": signal_type,
            "source": source,
            "data": data,
            "trace_id": trace_id,
        }
        self._runtime.memory.stage_and_promote(
            MemoryRecord(
                category="execution_feedback",
                key=f"telemetry:{trace_id}:{signal_type}",
                value=summary,
                confidence=0.8,
                source=MemorySource(
                    type=SourceType.SYSTEM.value,
                    agent=source,
                    session_id=session_id,
                    task_id=str(data.get("logical_task_id") or data.get("task_ref") or trace_id),
                ).to_dict(),
            ),
            MemoryTier.EPISODIC,
            reason="openclaw telemetry ingest",
        )
