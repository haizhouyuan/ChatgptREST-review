"""Planning task output schemas (8 types)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from runtime_allocator.schemas._shared import (
    AssumptionAndGapsMixin,
    ConfidenceMixin,
    EvidenceRef,
    RiskItem,
    TaskOutputBase,
)


class _Objective(BaseModel):
    objective: str
    priority: str = Field(pattern="^(high|medium|low)$")
    owner: str


class _TimelinePhase(BaseModel):
    phase: str
    duration: str
    deliverables: list[str]


class StrategyBriefOutput(TaskOutputBase):
    """strategy_brief output."""
    summary: str
    objectives: list[_Objective]
    constraints: list[str]
    timeline: list[_TimelinePhase]
    risks: list[RiskItem]
    recommended_next_steps: list[str]
    decision_required: str


class StrategicPlanOutput(TaskOutputBase):
    """strategic_plan output."""
    executive_summary: str
    vision: str
    strategic_pillars: list[dict] = Field(
        description="Pillars: {pillar, initiatives, kpis}"
    )
    resource_requirements: dict[str, Any] = Field(
        default_factory=dict,
        description="{headcount, budget, tools}"
    )
    timeline: list[dict] = Field(
        default_factory=list,
        description="Quarters: {quarter, milestones}"
    )
    risks: list[RiskItem]
    success_metrics: list[str]
    dependencies: list[str]


class HrPolicyOutput(BaseModel):
    """hr_policy output (always requires human review)."""
    policy_title: str
    summary: str
    key_provisions: list[str]
    compliance_notes: list[dict] = Field(
        default_factory=list,
        description="Notes: {region, requirement}"
    )
    escalation_checklist: list[str]
    requires_human_review: bool = Field(default=True)
    reviewer_notes: str


class HrSensitiveReviewOutput(BaseModel):
    """hr_sensitive_review output."""
    review_summary: str
    risk_items: list[dict] = Field(
        default_factory=list,
        description="Risks: {item, risk_level, recommendation}"
    )
    compliance_flags: list[dict] = Field(
        default_factory=list,
        description="Flags: {flag, regulation}"
    )
    sensitivity_notes: list[str]
    requires_human_review: bool = Field(default=True)
    recommended_actions: list[str]


class MeetingExtractionOutput(BaseModel):
    """meeting_extraction output."""
    summary: str
    decisions: list[dict] = Field(
        default_factory=list,
        description="Decisions: {decision, owner, deadline}"
    )
    action_items: list[dict] = Field(
        default_factory=list,
        description="Actions: {item, assignee, due_date, priority}"
    )
    risks: list[dict] = Field(
        default_factory=list,
        description="Risks: {risk, raised_by}"
    )
    open_questions: list[str]
    participants: list[str]
    meeting_duration_estimate: str


class MeetingSummaryOutput(BaseModel):
    """meeting_summary output."""
    executive_summary: str
    key_decisions: list[str]
    top_action_items: list[dict] = Field(
        default_factory=list,
        description="Actions: {item, owner}"
    )
    blockers: list[str]
    next_meeting_agenda: list[str]


class DocumentDraftOutput(BaseModel):
    """document_draft output."""
    title: str
    sections: list[dict] = Field(
        default_factory=list,
        description="Sections: {heading, content}"
    )
    summary: str
    key_points: list[str]
    tone: str
    target_audience: str


class DecisionMemoOutput(TaskOutputBase):
    """decision_memo output."""
    decision_point: str
    options: list[dict] = Field(
        default_factory=list,
        description="Options: {option, pros, cons, risk}"
    )
    recommendation: str
    rationale: list[str]
    resources_required: str
    timeline: str
    stakeholders: list[str]
