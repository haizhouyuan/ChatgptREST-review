"""Primary data / source enrichment module.

Provides enrichment from official disclosures and primary sources
to strengthen claim evidence bindings and counterevidence packets.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from chatgptrest.finbot_modules._helpers import text_value

log = logging.getLogger(__name__)


# Source types for primary data
SOURCE_TYPE_SEC_FILING = "sec_filing"
SOURCE_TYPE_EARNINGS_CALL = "earnings_call"
SOURCE_TYPE_PRESS_RELEASE = "press_release"
SOURCE_TYPE_CONFERENCE = "conference"
SOURCE_TYPE_REGULATORY = "regulatory_filing"


def _fetch_sec_filings(symbol: str) -> list[dict[str, Any]]:
    """Fetch recent SEC filings for symbol.

    Checks for FMP_API_KEY or returns empty list.
    """
    filings = []

    fmp_key = os.environ.get("FMP_API_KEY")
    if fmp_key:
        try:
            # Would call FMP SEC filings API here
            # For now, log and return empty placeholder
            log.info(f"Would fetch SEC filings for {symbol} via FMP")
        except Exception as e:
            log.warning(f"SEC filing fetch failed: {e}")

    return filings


def _analyze_filing_for_evidence(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze SEC filings for relevant evidence excerpts.

    Extracts relevant excerpts that could support or weaken claims.
    """
    evidence_items = []

    for filing in filings:
        # Look for specific sections that contain investment-relevant info
        # - MD&A (Management Discussion)
        # - Risk Factors
        # - Forward-looking statements
        # - Business outlook

        filing_type = filing.get("type", "")
        content = filing.get("content", "")

        # Categorize by relevance
        if "10-K" in filing_type or "10-Q" in filing_type:
            # Annual/quarterly reports - high value
            evidence_items.append({
                "source_id": filing.get("filing_id", ""),
                "source_type": SOURCE_TYPE_SEC_FILING,
                "filing_type": filing_type,
                "section": "md_and_a",
                "relevance": "high" if "md&a" in content.lower() else "medium",
                "excerpt": "",  # Would extract actual content
                "key_points": [],
            })

        if "8-K" in filing_type:
            # Current reports - material events
            evidence_items.append({
                "source_id": filing.get("filing_id", ""),
                "source_type": SOURCE_TYPE_SEC_FILING,
                "filing_type": filing_type,
                "section": "current_event",
                "relevance": "high",
                "excerpt": "",
                "key_points": [],
            })

    return evidence_items


def build_primary_data_packet(
    *,
    candidate_id: str,
    symbol: str | None = None,
    claim_evidence_bindings: list[dict[str, Any]] | None = None,
    counterevidence_packets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build primary data enrichment packet.

    Fetches official disclosures and primary sources to enrich:
    - claim_evidence_bindings
    - counterevidence_packets
    - promotion gate decisions

    Args:
        candidate_id: The opportunity/candidate identifier
        symbol: Optional ticker symbol
        claim_evidence_bindings: Existing claim evidence bindings to enrich
        counterevidence_packets: Existing counterevidence packets

    Returns:
        Primary data packet with schema:
        {
            "generated_at": float,
            "candidate_id": str,
            "primary_sources_found": bool,
            "sec_filings": [...],
            "earnings_calls": [...],
            "official_press_releases": [...],
            "enriched_claim_bindings": [...],
            "enriched_counterevidence": [...],
            "promotion_enrichment": {
                "has_official_disclosure": bool,
                "first_hand_anchor_found": bool,
                "promotion_recommendation": str
            }
        }
    """
    ts = time.time()

    # Use candidate_id as symbol if not provided
    if not symbol:
        symbol = candidate_id

    # Fetch primary sources
    sec_filings = _fetch_sec_filings(symbol)

    # Analyze for evidence
    filing_evidence = _analyze_filing_for_evidence(sec_filings)

    # Check for official press releases (would check news API)
    press_releases = []

    # Build enrichment result
    has_official = bool(sec_filings or press_releases)

    # Enrich claim bindings if provided
    enriched_bindings = []
    if claim_evidence_bindings:
        for binding in claim_evidence_bindings:
            # Check if any binding can be strengthened with primary data
            binding_source = text_value(binding.get("source_id", "")).lower()

            enriched = dict(binding)
            enriched["primary_data_enriched"] = False
            enriched["primary_source_excerpts"] = []

            # If we have SEC filings, try to match
            if filing_evidence:
                # Simple matching - in production would do more sophisticated matching
                enriched["primary_data_enriched"] = True
                enriched["primary_source_excerpts"] = filing_evidence[:2]  # Attach up to 2

            enriched_bindings.append(enriched)

    # Enrich counterevidence if provided
    enriched_counter = []
    if counterevidence_packets:
        for pkt in counterevidence_packets:
            enriched = dict(pkt)
            enriched["primary_data_enriched"] = False

            # Counterevidence often comes from risk factors in filings
            if filing_evidence:
                risk_items = [f for f in filing_evidence if f.get("section") == "risk_factors"]
                if risk_items:
                    enriched["primary_data_enriched"] = True
                    enriched["primary_source_excerpts"] = risk_items[:1]

            enriched_counter.append(enriched)

    # Promotion gate enrichment
    promotion_enrichment = {
        "has_official_disclosure": has_official,
        "first_hand_anchor_found": bool(filing_evidence),
        "promotion_recommendation": "",
    }

    # Recommend promotion based on primary data
    if has_official and filing_evidence:
        promotion_enrichment["promotion_recommendation"] = "strong_promote"
    elif has_official:
        promotion_enrichment["promotion_recommendation"] = "neutral_promote"
    else:
        promotion_enrichment["promotion_recommendation"] = "no_primary_data"

    return {
        "generated_at": ts,
        "candidate_id": candidate_id,
        "symbol": symbol,
        "primary_sources_found": has_official,
        "sec_filings": sec_filings,
        "filing_evidence": filing_evidence,
        "earnings_calls": [],  # Would be filled by transcript_provider
        "official_press_releases": press_releases,
        "enriched_claim_bindings": enriched_bindings,
        "enriched_counterevidence": enriched_counter,
        "promotion_enrichment": promotion_enrichment,
    }
