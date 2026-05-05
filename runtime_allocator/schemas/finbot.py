"""Finbot task output schemas (3 types)."""

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


class TradeProposalOutput(TaskOutputBase):
    """finbot_trade_proposal output."""
    symbol: str
    action: str = Field(pattern="^(buy|sell|hold|reduce|increase)$")
    quantity: Optional[int] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    rationale: list[str]
    risks: list[RiskItem]


class RiskVetoOutput(TaskOutputBase):
    """finbot_risk_veto output."""
    symbol: str
    veto_reason: str
    severity: str = Field(pattern="^(high|medium|low)$")
    mitigation_suggestions: list[str]


class FundamentalOutput(TaskOutputBase):
    """finbot_fundamental output."""
    symbol: str
    summary: str
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Key financial metrics (PE, PB, ROE, etc.)"
    )
    outlook: str = Field(pattern="^(bullish|bearish|neutral)$")
