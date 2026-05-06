"""Peer snapshot and valuation discipline module.

Provides peer comparison and valuation discipline for finbot expression/decision lanes.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from chatgptrest.finbot_modules._helpers import text_value

log = logging.getLogger(__name__)


def _fetch_peer_data_from_env(symbol: str) -> list[dict[str, Any]]:
    """Fetch peer data from environment providers.

    Checks for:
    - FMP_API_KEY (Financial Modeling Prep)
    - ALPHA_VANTAGE_API_KEY

    Returns list of peer data dicts or empty list if unavailable.
    """
    peers = []

    # Check for FMP
    fmp_key = os.environ.get("FMP_API_KEY")
    if fmp_key:
        try:
            # Note: In production, would make actual API call
            # For now, return empty with indication that provider exists
            log.info(f"FMP available but API call not implemented in peer_snapshot")
        except Exception as e:
            log.warning(f"FMP peer fetch failed: {e}")

    # Check for Alpha Vantage
    av_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if av_key:
        try:
            log.info(f"Alpha Vantage available but API call not implemented in peer_snapshot")
        except Exception as e:
            log.warning(f"Alpha Vantage peer fetch failed: {e}")

    return peers


def extract_valuation_driver_from_narrative(narrative: str | None) -> str:
    """Extract valuation driver from expression lane narrative.

    Looks for key phrases that indicate what drives valuation:
    - revenue growth, earnings, cash flow
    - market share, user growth
    - tech leadership, moat
    - turnaround potential, restructuring
    """
    if not narrative:
        return ""

    narrative_lower = narrative.lower()

    # Priority drivers to look for
    drivers = []

    if any(kw in narrative_lower for kw in ["revenue", "sales", "top-line", "growth"]):
        drivers.append("revenue_growth")
    if any(kw in narrative_lower for kw in ["earnings", "eps", "profit", "bottom-line"]):
        drivers.append("earnings_growth")
    if any(kw in narrative_lower for kw in ["cash flow", "fcf", "free cash"]):
        drivers.append("cash_flow")
    if any(kw in narrative_lower for kw in ["market share", "user", "customer", "adoption"]):
        drivers.append("user_growth")
    if any(kw in narrative_lower for kw in ["moat", "competitive advantage", "tech leadership", "patent"]):
        drivers.append("competitive_moat")
    if any(kw in narrative_lower for kw in ["turnaround", "restructuring", "cost cut"]):
        drivers.append("turnaround")
    if any(kw in narrative_lower for kw in ["dividend", "buyback", "capital return"]):
        drivers.append("capital_return")
    if any(kw in narrative_lower for kw in ["asset", "book value", "NAV", "revaluation"]):
        drivers.append("asset_value")

    return ", ".join(drivers) if drivers else ""


def build_peer_snapshot(
    *,
    candidate_id: str,
    leader_expression: str | None = None,
    valuation_frame: dict[str, Any] | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Build peer snapshot artifact for expression/decision lanes.

    Args:
        candidate_id: The opportunity/candidate identifier
        leader_expression: The leading expression from expression lane
        valuation_frame: The valuation frame from expression lane
        symbol: Optional ticker symbol for API lookups

    Returns:
        Peer snapshot dict with schema:
        {
            "generated_at": float,
            "candidate_id": str,
            "leader_expression": str,
            "valuation_driver": str,
            "peers": [...],
            "reverse_dcf_hint": str,
            "distance_to_action_override": str
        }
    """
    ts = time.time()

    # Extract valuation driver from narrative
    valuation_driver = extract_valuation_driver_from_narrative(leader_expression)
    if not valuation_driver and valuation_frame:
        valuation_driver = text_value(
            valuation_frame.get("key_variable")
            or valuation_frame.get("current_view")
            or valuation_frame.get("base_case")
        )

    # Try to fetch real peer data
    peer_data = []
    if symbol:
        peer_data = _fetch_peer_data_from_env(symbol)

    # Build peers list - either from API or mark as unavailable
    if peer_data:
        peers = [
            {
                "symbol": p.get("symbol", ""),
                "name": p.get("name", ""),
                "role": p.get("role", "peer"),
                "market_truth": p.get("market_truth", {}),
                "why_comparable": p.get("why_comparable", ""),
                "valuation_gap_note": p.get("valuation_gap_note", ""),
            }
            for p in peer_data
        ]
    else:
        # No peer data available - explicitly mark as unavailable
        peers = []
        log.info(f"No peer data available for {candidate_id} - peer snapshot will be sparse")

    # Generate reverse DCF hint if we have valuation info
    reverse_dcf_hint = ""
    if valuation_frame:
        # Check if there's a target price vs current price that suggests
        # implied growth expectations
        target_price = valuation_frame.get("target_price") or valuation_frame.get("price_target")
        current_price = None
        if valuation_frame.get("market_truth"):
            current_price = valuation_frame["market_truth"].get("price")

        if target_price and current_price:
            try:
                tp = float(target_price) if isinstance(target_price, (int, float)) else float(target_price.replace(",", ""))
                cp = float(current_price) if isinstance(current_price, (int, float)) else float(current_price.replace(",", ""))
                if cp > 0:
                    upside = (tp - cp) / cp * 100
                    if upside > 50:
                        reverse_dcf_hint = f"Market implies >50% upside - check if implied growth is realistic"
                    elif upside < 0:
                        reverse_dcf_hint = f"Market implies downside - check for hidden assets or turnaround"
            except (ValueError, TypeError):
                pass

    return {
        "generated_at": ts,
        "candidate_id": candidate_id,
        "leader_expression": text_value(leader_expression),
        "valuation_driver": valuation_driver,
        "peers": peers,
        "reverse_dcf_hint": reverse_dcf_hint,
        "distance_to_action_override": "",
    }
