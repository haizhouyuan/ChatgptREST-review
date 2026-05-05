"""Labebe task output schemas (5 types)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from runtime_allocator.schemas._shared import (
    AssumptionAndGapsMixin,
    ConfidenceMixin,
    EvidenceRef,
    RiskItem,
    TaskOutputBase,
)


class CommerceDecisionOutput(TaskOutputBase):
    """labebe_commerce_decision output."""
    product_id: str = Field(description="Product or SKU identifier")
    decision: str = Field(pattern="^(approve|reject|request_review|defer)$")
    rationale: list[str] = Field(description="Ordered reasoning steps")
    alternatives: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class EvidenceBundleOutput(TaskOutputBase):
    """labebe_evidence_bundle output."""
    product_id: str
    claims: list[dict] = Field(
        default_factory=list,
        description="Extracted claims: {claim_text, type, source, confidence}"
    )
    counter_claims: list[dict] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source_spans: list[dict] = Field(
        default_factory=list,
        description="Specific source spans: {source_id, span_text, page/section}"
    )
    input_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Proportion of input sources actually used",
    )


class DtcCopyOutput(BaseModel):
    """dtc_copy output."""
    headline: str
    body: str
    cta: str = Field(description="Call-to-action text")
    tone: str
    target_audience: str
    assumptions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class BossGalleryCardOutput(BaseModel):
    """boss_gallery_card output."""
    title: str
    description: str
    key_features: list[str]
    media_suggestions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class ProductEvalOutput(TaskOutputBase):
    """labebe_product_eval output."""
    product_id: str
    score: float = Field(ge=0.0, le=100.0, description="Overall score 0-100")
    pros: list[str]
    cons: list[str]
    recommendations: list[str]
    compliance_notes: list[str] = Field(default_factory=list)
