"""
TaskSpec compatibility bridge over the canonical task intake schema.

`Task Intake Spec` is the versioned front-door object. This module keeps the
older `IntentEnvelope` / `TaskSpec` carrier models available for system
optimization flows, but routes them through the shared intake normalizer so we
do not maintain a second parallel schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from chatgptrest.advisor.task_intake import (
    AcceptanceSpec as CanonicalAcceptanceSpec,
    TaskIntakeSpec,
    build_task_intake_spec,
)


_RAW_ENVELOPE_SOURCES = (
    "openclaw",
    "feishu",
    "codex",
    "rest",
    "cron",
    "mcp",
    "repair",
    "cli",
    "api",
    "direct",
    "unknown",
)
_CANONICAL_TASKSPEC_SOURCES = ("openclaw", "feishu", "rest", "mcp", "cli", "cron", "repair", "unknown")
_TASKSPEC_SCENARIOS = ("planning", "research", "quick_ask", "report", "code_review", "image", "repair", "general")
_TASKSPEC_OUTPUTS = (
    "brief_answer",
    "text_answer",
    "markdown_report",
    "planning_memo",
    "research_memo",
    "meeting_summary",
    "code_review_summary",
    "image_url",
    "other",
)


class IntentEnvelope(BaseModel):
    """Raw request wrapper for non-live task entry adapters."""

    source: Literal[
        "openclaw",
        "feishu",
        "codex",
        "rest",
        "cron",
        "mcp",
        "repair",
        "cli",
        "api",
        "direct",
        "unknown",
    ] = "rest"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str
    attachments: list[str] = Field(default_factory=list)

    cwd: Optional[str] = None
    repo: Optional[str] = None
    git_branch: Optional[str] = None
    selected_files: list[str] = Field(default_factory=list)

    mode_hint: Literal["interactive", "autonomous", "auto"] = "auto"
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)


class SkillRequirement(BaseModel):
    """A single skill requirement for a task."""

    name: str
    min_level: int = 1
    mandatory: bool = True


class AcceptanceSpec(CanonicalAcceptanceSpec):
    """Compatibility export for task acceptance over the canonical schema."""


class TaskSpec(BaseModel):
    """
    Compatibility dispatch object derived from the canonical task intake spec.

    `TaskSpec` stays as a lightweight runtime-oriented carrier for legacy flows,
    but it now embeds the canonical `task_intake` so downstream code can stop
    inventing a separate front-door contract.
    """

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    source: Literal["openclaw", "feishu", "rest", "mcp", "cli", "cron", "repair", "unknown"] = "rest"
    trace_id: str = ""
    session_id: Optional[str] = None
    mode: Literal["interactive", "autonomous"] = "interactive"
    user_intent: str
    objective: str = ""
    scenario: Literal["planning", "research", "quick_ask", "report", "code_review", "image", "repair", "general"] = "general"
    output_shape: Literal[
        "brief_answer",
        "text_answer",
        "markdown_report",
        "planning_memo",
        "research_memo",
        "meeting_summary",
        "code_review_summary",
        "image_url",
        "other",
    ] = "text_answer"
    deliverable_type: Literal[
        "answer",
        "report",
        "dataset",
        "code_patch",
        "research_memo",
        "scorecard",
        "summary",
    ] = "answer"

    latency_budget_s: int = 600
    lane: Literal["interactive_fast", "interactive_pro", "autonomous_batch", "local_only"] = "interactive_fast"

    evidence_mode: Literal["none", "kb", "web", "cross_provider"] = "none"
    difficulty: int = 2

    required_skills: list[SkillRequirement] = Field(default_factory=list)

    preferred_provider: list[str] = Field(default_factory=lambda: ["auto"])
    preferred_preset: Literal["auto", "normal", "pro", "deepthink"] = "auto"

    acceptance: AcceptanceSpec = Field(default_factory=AcceptanceSpec)
    artifact_root: Optional[str] = None
    task_intake: Optional[TaskIntakeSpec] = None

    parent_run_id: Optional[str] = None
    priority: int = 5
    created_at: datetime = Field(default_factory=datetime.now)


def intent_envelope_to_task_intake(
    envelope: IntentEnvelope,
    *,
    intent_label: Optional[str] = None,
) -> TaskIntakeSpec:
    """
    Convert a raw envelope into the canonical versioned task intake object.

    This is the authoritative bridge from the older compatibility carrier into
    the shared front-door schema.
    """

    metadata = dict(envelope.metadata or {})
    raw_task_intake = metadata.get("task_intake")
    trace_id = str(metadata.get("trace_id") or "").strip() or str(uuid.uuid4())
    intent_hint = _infer_intent_hint(intent_label, envelope.raw_text)

    context: dict[str, Any] = dict(metadata)
    if envelope.cwd:
        context.setdefault("cwd", envelope.cwd)
    if envelope.repo:
        context.setdefault("repo", envelope.repo)
    if envelope.git_branch:
        context.setdefault("git_branch", envelope.git_branch)
    if envelope.selected_files:
        context.setdefault("selected_files", list(envelope.selected_files))

    return build_task_intake_spec(
        ingress_lane="other",
        default_source=_default_source_from_envelope_source(envelope.source),
        raw_source=envelope.source,
        raw_task_intake=raw_task_intake if isinstance(raw_task_intake, dict) else None,
        question=envelope.raw_text,
        goal_hint=intent_hint,
        intent_hint=intent_hint,
        trace_id=trace_id,
        session_id=envelope.session_id or str(metadata.get("session_id") or "").strip(),
        user_id=envelope.user_id or str(metadata.get("user_id") or "").strip(),
        account_id=str(metadata.get("account_id") or "").strip(),
        thread_id=str(metadata.get("thread_id") or "").strip(),
        agent_id=str(metadata.get("agent_id") or "").strip(),
        role_id=str(metadata.get("role_id") or "").strip(),
        context=context,
        attachments=envelope.attachments,
        client_name=str(metadata.get("client_name") or "").strip(),
    )


def task_intake_to_task_spec(
    intake: TaskIntakeSpec,
    *,
    mode_hint: str = "auto",
    artifact_root: str | None = None,
    difficulty: Optional[int] = None,
) -> TaskSpec:
    """Derive the legacy-compatible dispatch object from canonical intake."""

    if difficulty is None:
        difficulty = _estimate_difficulty(intake.objective)

    mode = _resolve_mode(mode_hint=mode_hint, source=intake.source)
    lane = "interactive_fast" if mode == "interactive" else "autonomous_batch"
    latency_budget_s = 600 if mode == "interactive" else 3600
    deliverable_type = _deliverable_type_from_intake(intake)
    evidence_mode = _evidence_mode_from_intake(intake=intake, difficulty=difficulty)

    return TaskSpec(
        task_id=intake.task_id or f"task_{uuid.uuid4().hex[:12]}",
        source=_normalize_taskspec_source(intake.source),
        trace_id=intake.trace_id,
        session_id=intake.session_id,
        mode=mode,
        user_intent=intake.objective,
        objective=intake.objective,
        scenario=_normalize_taskspec_scenario(intake.scenario),
        output_shape=_normalize_taskspec_output_shape(intake.output_shape),
        deliverable_type=deliverable_type,
        latency_budget_s=latency_budget_s,
        lane=lane,
        evidence_mode=evidence_mode,
        difficulty=difficulty,
        acceptance=AcceptanceSpec(**intake.acceptance.to_dict()),
        artifact_root=artifact_root,
        task_intake=intake,
        priority=int(intake.priority) if intake.priority is not None else 5,
    )


def envelope_to_task_spec(
    envelope: IntentEnvelope,
    *,
    intent_label: Optional[str] = None,
    difficulty: Optional[int] = None,
) -> TaskSpec:
    """Convert a raw envelope into a legacy-compatible TaskSpec via canonical intake."""

    intake = intent_envelope_to_task_intake(envelope, intent_label=intent_label)
    return task_intake_to_task_spec(
        intake,
        mode_hint=envelope.mode_hint,
        artifact_root=envelope.cwd,
        difficulty=difficulty,
    )


def _infer_deliverable_type(
    text: str,
    intent_label: Optional[str] = None,
) -> str:
    """Lightweight heuristic to classify deliverable type."""
    t = text.lower()

    if intent_label:
        mapping = {
            "research": "research_memo",
            "report": "report",
            "dataset": "dataset",
            "code": "code_patch",
            "summary": "summary",
        }
        for key, val in mapping.items():
            if key in intent_label.lower():
                return val

    if any(kw in t for kw in ["调研", "研究", "分析", "market", "research"]):
        return "research_memo"
    if any(kw in t for kw in ["报告", "report"]):
        return "report"
    if any(kw in t for kw in ["数据", "dataset", "csv"]):
        return "dataset"
    if any(kw in t for kw in ["代码", "修复", "patch", "code", "fix", "refactor"]):
        return "code_patch"
    if any(kw in t for kw in ["总结", "摘要", "summary"]):
        return "summary"

    return "answer"


def _estimate_difficulty(text: str) -> int:
    """Estimate task difficulty from 1 to 5."""
    length = len(text)
    complexity_keywords = [
        "详细",
        "深入",
        "全面",
        "comprehensive",
        "detailed",
        "deep",
        "分析",
        "对比",
        "比较",
        "evaluate",
        "策略",
        "strategy",
        "优化",
        "optimize",
    ]
    score = 1

    if length > 500:
        score += 1
    if length > 1500:
        score += 1

    t = text.lower()
    keyword_hits = sum(1 for kw in complexity_keywords if kw in t)
    if keyword_hits >= 2:
        score += 1
    if keyword_hits >= 4:
        score += 1

    return min(score, 5)


def _default_source_from_envelope_source(source: str) -> str:
    raw = str(source or "").strip().lower()
    if raw == "codex":
        return "cli"
    if raw == "api":
        return "rest"
    if raw == "direct":
        return "unknown"
    if raw in _RAW_ENVELOPE_SOURCES:
        return raw
    return "unknown"


def _infer_intent_hint(intent_label: Optional[str], text: str = "") -> str:
    label = str(intent_label or "").strip().lower()
    if not label:
        body = str(text or "").strip().lower()
        if any(token in body for token in ("调研", "研究", "分析", "market", "research")):
            return "research"
        if any(token in body for token in ("报告", "report")):
            return "report"
        if any(token in body for token in ("review", "评审", "审查")):
            return "research"
        if any(token in body for token in ("quick", "快速", "简要")):
            return "quick"
        return ""
    if "report" in label:
        return "report"
    if any(token in label for token in ("research", "review")):
        return "research"
    if "quick" in label:
        return "quick"
    return label


def _resolve_mode(*, mode_hint: str, source: str) -> Literal["interactive", "autonomous"]:
    hint = str(mode_hint or "auto").strip().lower()
    if hint in {"interactive", "autonomous"}:
        return hint  # type: ignore[return-value]
    if source in {"cli", "mcp", "openclaw"}:
        return "interactive"
    return "autonomous"


def _deliverable_type_from_intake(intake: TaskIntakeSpec) -> str:
    if intake.scenario == "research" or intake.output_shape == "research_memo":
        return "research_memo"
    if intake.scenario == "report" or intake.output_shape == "markdown_report":
        return "report"
    if intake.scenario == "code_review":
        return "summary"
    if intake.scenario == "planning" or intake.output_shape == "planning_memo":
        return "summary"
    if intake.scenario == "image":
        return "answer"
    return _infer_deliverable_type(intake.objective)


def _evidence_mode_from_intake(*, intake: TaskIntakeSpec, difficulty: int) -> str:
    if intake.evidence_required.require_sources and intake.evidence_required.prefer_primary_sources:
        return "web"
    if intake.evidence_required.require_traceable_claims:
        return "kb" if difficulty <= 2 else "web"
    return "none"


def _normalize_taskspec_source(value: str) -> str:
    source = str(value or "").strip().lower()
    return source if source in _CANONICAL_TASKSPEC_SOURCES else "unknown"


def _normalize_taskspec_scenario(value: str) -> str:
    scenario = str(value or "").strip().lower()
    return scenario if scenario in _TASKSPEC_SCENARIOS else "general"


def _normalize_taskspec_output_shape(value: str) -> str:
    output_shape = str(value or "").strip().lower()
    return output_shape if output_shape in _TASKSPEC_OUTPUTS else "other"
