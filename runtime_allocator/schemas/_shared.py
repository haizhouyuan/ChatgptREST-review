"""Shared base models and types for task output schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfidenceMixin(BaseModel):
    """Mixin providing confidence + human review fields."""
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the result, 0.0 to 1.0",
    )
    requires_human_review: bool = Field(
        default=False,
        description="Whether a human should review this output before use",
    )


class EvidenceRef(BaseModel):
    """Reference to evidence source."""
    source_id: str = Field(description="Identifier of the source document/data")
    span_text: Optional[str] = Field(default=None, description="Direct quote or span")
    relevance: str = Field(description="How this evidence supports the conclusion")


class RiskItem(BaseModel):
    """A risk with impact and mitigation."""
    risk: str
    impact: str = Field(default="medium", pattern="^(high|medium|low)$")
    mitigation: str


class AssumptionAndGapsMixin(BaseModel):
    """Mixin for assumptions and data gaps."""
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made by the model when data was incomplete",
    )
    data_gaps: list[str] = Field(
        default_factory=list,
        description="Known gaps in data that limit result quality",
    )


class TaskOutputBase(AssumptionAndGapsMixin, ConfidenceMixin):
    """Base model with all recommended fields from Pro review."""
    model_config = ConfigDict(extra="allow")

    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="References to evidence backing key claims",
    )
