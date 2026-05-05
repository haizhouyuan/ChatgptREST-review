"""Memory Research Lab output schemas (4 types)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from runtime_allocator.schemas._shared import (
    AssumptionAndGapsMixin,
    ConfidenceMixin,
    EvidenceRef,
    TaskOutputBase,
)


class _DimensionScore(BaseModel):
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: str


class _NotablePaper(BaseModel):
    title: str
    relevance: str


class MemorySystemEvalOutput(TaskOutputBase):
    """system_eval output."""
    system_name: str
    architecture_summary: str
    dimensions: dict[str, _DimensionScore] = Field(
        default_factory=dict,
        description="Dimensions: retrieval_precision, memory_persistence, "
                    "context_window_utilization, incremental_update_efficiency, "
                    "multi_hop_reasoning"
    )
    strengths: list[str]
    weaknesses: list[str]
    best_fit_scenarios: list[str]
    notable_papers: list[_NotablePaper] = Field(default_factory=list)


class MemoryBenchmarkOutput(BaseModel):
    """benchmark output."""
    benchmark_name: str
    systems_compared: list[str]
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Metrics: avg_precision, avg_recall, avg_latency_ms, case_count"
    )
    system_rankings: list[dict] = Field(
        default_factory=list,
        description="Rankings: {system, rank, score, notes}"
    )
    statistical_significance: str
    recommendations: list[str]
    methodology_notes: str


class MemoryComparisonOutput(TaskOutputBase):
    """comparison output."""
    systems: list[str]
    comparison_matrix: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Matrix: architecture_pattern, memory_organization, "
                    "retrieval_strategy, scalability, ease_of_integration"
    )
    best_fit_scenarios: dict[str, list[str]]
    limitations: dict[str, list[str]]
    overall_recommendation: str


class MemoryRecommendationOutput(TaskOutputBase):
    """recommendation output."""
    recommendation_summary: str
    systems_evaluated: list[str]
    top_recommendation: dict[str, Any] = Field(
        default_factory=dict,
        description="{system, rationale, confidence}"
    )
    runner_up: dict[str, Any] = Field(
        default_factory=dict,
        description="{system, rationale}"
    )
    implementation_roadmap: list[dict] = Field(
        default_factory=list,
        description="Phases: {phase, duration, deliverables}"
    )
    risks: list[dict] = Field(
        default_factory=list,
        description="Risks: {risk, mitigation}"
    )
    open_questions: list[str]
