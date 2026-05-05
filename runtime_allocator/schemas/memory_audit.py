"""Schemas for Memory Audit Agent output.

All memory audit outputs are review-queue candidates, NOT canonical memory.
They default to review_state="pending" and MUST include source provenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PushbackCategory(str, Enum):
    OUTPUT_PREFERENCE = "output_preference"
    AUTHORITY_BOUNDARY = "authority_boundary"
    MODEL_LANE_POLICY = "model_lane_policy"
    OTHER = "other"


class TargetMemoryLayer(str, Enum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    AUTHORITY = "authority"


class ReviewState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserConstraintCard(BaseModel):
    """A user pushback or constraint extracted from session history."""

    source_path: str = Field(description="Path to transcript or log file")
    source_line_or_span: str = Field(description="Line number or text span")
    session_id: str = Field(description="Session that produced this constraint")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence")
    category: PushbackCategory = PushbackCategory.OTHER
    constraint_text: str = Field(description="The actual constraint wording")
    review_state: ReviewState = ReviewState.PENDING


class AgentFailurePattern(BaseModel):
    """A recurring failure pattern observed across sessions."""

    source_path: str = Field(description="Path to session log or error log")
    source_line_or_span: str = Field(description="Line number or text span")
    session_id: str = Field(description="Most recent session where observed")
    confidence: float = Field(ge=0.0, le=1.0)
    pattern_name: str = Field(description="Short identifier for the pattern")
    description: str = Field(description="What happened and why")
    affected_task_classes: list[str] = Field(default_factory=list)
    review_state: ReviewState = ReviewState.PENDING


class MemoryDeltaCandidate(BaseModel):
    """A proposed memory write, pending review. NEVER written to canonical stores directly."""

    source_path: str = Field(description="Path to source material")
    source_line_or_span: str = Field(description="Line number or text span")
    session_id: str = Field(description="Origin session")
    confidence: float = Field(ge=0.0, le=1.0)
    target_layer: TargetMemoryLayer = TargetMemoryLayer.WORKING
    key: str = Field(description="Memory key / identifier")
    value: str = Field(description="Memory value / content")
    review_state: ReviewState = ReviewState.PENDING
