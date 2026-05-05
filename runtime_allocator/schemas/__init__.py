"""Pydantic output schemas for Paperclip Skill Agent task types.

Each task type has a dedicated Pydantic model that enforces structure on
LLM output (via JSON mode). These schemas are consumed by execute_with_fallback()
for validation.

Usage:
    from runtime_allocator.schemas import CommerceDecisionOutput
    result = execute_with_fallback(
        ...,
        schema_model=CommerceDecisionOutput,
    )
"""

from __future__ import annotations

# Re-export all schemas for convenient access
from runtime_allocator.schemas.labebe import (
    CommerceDecisionOutput,
    EvidenceBundleOutput,
    DtcCopyOutput,
    BossGalleryCardOutput,
    ProductEvalOutput,
)
from runtime_allocator.schemas.planning import (
    StrategyBriefOutput,
    StrategicPlanOutput,
    HrPolicyOutput,
    HrSensitiveReviewOutput,
    MeetingExtractionOutput,
    MeetingSummaryOutput,
    DocumentDraftOutput,
    DecisionMemoOutput,
)
from runtime_allocator.schemas.memory import (
    MemorySystemEvalOutput,
    MemoryBenchmarkOutput,
    MemoryComparisonOutput,
    MemoryRecommendationOutput,
)
from runtime_allocator.schemas.finbot import (
    TradeProposalOutput,
    RiskVetoOutput,
    FundamentalOutput,
)

__all__ = [
    # Labebe
    "CommerceDecisionOutput",
    "EvidenceBundleOutput",
    "DtcCopyOutput",
    "BossGalleryCardOutput",
    "ProductEvalOutput",
    # Planning
    "StrategyBriefOutput",
    "StrategicPlanOutput",
    "HrPolicyOutput",
    "HrSensitiveReviewOutput",
    "MeetingExtractionOutput",
    "MeetingSummaryOutput",
    "DocumentDraftOutput",
    "DecisionMemoOutput",
    # Memory
    "MemorySystemEvalOutput",
    "MemoryBenchmarkOutput",
    "MemoryComparisonOutput",
    "MemoryRecommendationOutput",
    # Finbot
    "TradeProposalOutput",
    "RiskVetoOutput",
    "FundamentalOutput",
]
