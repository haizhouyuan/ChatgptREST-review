"""EvoMap Signal types — structured event signal records.

Signal types collected by the Observer:
  - route.selected
  - funnel.stage_completed
  - report.step_completed
  - gate.passed / gate.failed
  - dispatch.task_completed / dispatch.task_failed
  - kb.writeback / kb.artifact_helpful / kb.artifact_pruned
  - llm.call_completed / llm.call_failed / llm.model_switched
  - actuator.circuit_break / actuator.gate_tuned
  - user.rapid_retry
  - team.run.created / team.run.completed / team.run.failed
  - team.role.completed / team.role.failed
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Legacy → canonical signal name mapping  (underscore → dot)
_LEGACY_NAMES: dict[str, str] = {
    "route_selected": "route.selected",
}


def normalize_signal_type(raw: str) -> str:
    """Normalize legacy signal names to canonical dot-delimited form."""
    return _LEGACY_NAMES.get(raw, raw)


@dataclass
class Signal:
    """A structured signal record from system events.

    Signals are aggregated by trace_id for per-request observability.
    """
    signal_id: str = ""
    trace_id: str = ""
    signal_type: str = ""        # e.g. "route_selected", "gate.passed"
    source: str = ""             # e.g. "advisor", "funnel", "report"
    timestamp: str = ""
    domain: str = ""             # e.g. "routing", "gate", "dispatch"
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_trace_event(cls, event) -> "Signal":
        """Convert an EventBus TraceEvent into an EvoMap Signal.

        Domain is inferred from the event_type prefix:
          route.* → routing, funnel.* → funnel, report.* → report,
          gate.* → gate, kb.* → kb, llm.* → llm, etc.
        """
        event_type = getattr(event, "event_type", "") or ""
        prefix = event_type.split(".")[0] if "." in event_type else event_type
        _DOMAIN_MAP = {
            "route": "routing", "route_selected": "routing",
            "funnel": "funnel", "report": "report",
            "gate": "gate", "dispatch": "dispatch",
            "kb": "kb", "llm": "llm",
            "skill": "skill", "tool": "tool",
            "team": "team",
        }
        domain = _DOMAIN_MAP.get(prefix, prefix)
        return cls(
            signal_id=getattr(event, "event_id", ""),
            trace_id=getattr(event, "trace_id", ""),
            signal_type=event_type,
            source=getattr(event, "source", ""),
            timestamp=getattr(event, "timestamp", ""),
            domain=domain,
            data=getattr(event, "data", {}) or {},
        )


class SignalType:
    """Known signal types."""
    ROUTE_SELECTED = "route.selected"
    ROUTE_FALLBACK = "route.fallback"
    FUNNEL_STAGE_COMPLETED = "funnel.stage_completed"
    REPORT_STEP_COMPLETED = "report.step_completed"
    GATE_PASSED = "gate.passed"
    GATE_FAILED = "gate.failed"
    DISPATCH_COMPLETED = "dispatch.task_completed"
    DISPATCH_FAILED = "dispatch.task_failed"
    KB_WRITEBACK = "kb.writeback"
    # hcom/multi-agent feedback loop
    SKILL_LEARNED = "skill.learned"
    TOOL_FAILURE = "tool.failure"
    TOOL_RECOVERY = "tool.recovery"
    # Langfuse-sourced LLM observability
    LLM_CALL_COMPLETED = "llm.call_completed"
    LLM_CALL_FAILED = "llm.call_failed"
    LLM_MODEL_SWITCHED = "llm.model_switched"
    # Routing engine feedback loop
    ROUTE_CANDIDATE_OUTCOME = "route.candidate_outcome"
    # ── Actuator signals (Phase 2) ──
    ACTUATOR_CIRCUIT_BREAK = "actuator.circuit_break"
    ACTUATOR_GATE_TUNED = "actuator.gate_tuned"
    KB_ARTIFACT_HELPFUL = "kb.artifact_helpful"
    KB_ARTIFACT_PRUNED = "kb.artifact_pruned"
    USER_RAPID_RETRY = "user.rapid_retry"
    # ── Team lifecycle signals ──
    TEAM_RUN_CREATED = "team.run.created"
    TEAM_RUN_COMPLETED = "team.run.completed"
    TEAM_RUN_FAILED = "team.run.failed"
    TEAM_ROLE_COMPLETED = "team.role.completed"
    TEAM_ROLE_FAILED = "team.role.failed"
    TEAM_OUTPUT_ACCEPTED = "team.output.accepted"
    TEAM_OUTPUT_REJECTED = "team.output.rejected"


class SignalDomain:
    """Signal domains for filtering."""
    ROUTING = "routing"
    FUNNEL = "funnel"
    REPORT = "report"
    GATE = "gate"
    DISPATCH = "dispatch"
    KB = "kb"
    # hcom/multi-agent + tooling
    SKILL = "skill"
    TOOL = "tool"
    # LLM observability
    LLM = "llm"
    TEAM = "team"
