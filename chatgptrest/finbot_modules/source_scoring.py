"""Source quality scoring — compute trust scores and quality bands for information sources.

Pure scoring functions extracted from finbot.py. The I/O-heavy ledger update
logic stays in finbot.py because it depends on filesystem paths and JSON I/O.
"""
from __future__ import annotations

from typing import Any

from chatgptrest.finbot_modules._helpers import text_value


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def source_quality_score(record: dict[str, Any]) -> float:
    """Compute a 0-1 quality score for an information source.

    Weights:
      - accepted_route_count:       15%
      - validated_case_count:       15%
      - supported_claim_count:      20%
      - anchor_claim_count:         18%
      - load_bearing_claim_count:   17%
      - lead_support_count:         10%
      - theme_diversity:            10%
      - contradicted_claim_count:   -5% penalty
    """
    accepted = min(int(record.get("accepted_route_count") or 0), 20) / 20.0
    validated = min(int(record.get("validated_case_count") or 0), 10) / 10.0
    supported = min(int(record.get("supported_claim_count") or 0), 24) / 24.0
    anchor = min(int(record.get("anchor_claim_count") or 0), 12) / 12.0
    load_bearing = min(int(record.get("load_bearing_claim_count") or 0), 12) / 12.0
    lead_support = min(int(record.get("lead_support_count") or 0), 8) / 8.0
    contradiction_penalty = min(int(record.get("contradicted_claim_count") or 0), 10) / 10.0
    theme_diversity = min(len(record.get("theme_slugs") or []), 8) / 8.0
    score = (
        (0.15 * accepted)
        + (0.15 * validated)
        + (0.20 * supported)
        + (0.18 * anchor)
        + (0.17 * load_bearing)
        + (0.10 * lead_support)
        + (0.10 * theme_diversity)
        - (0.05 * contradiction_penalty)
    )
    return round(score, 3)


def source_quality_band(score: float) -> str:
    """Map a quality score to a human-readable band: core / useful / monitor / weak."""
    if score >= 0.75:
        return "core"
    if score >= 0.55:
        return "useful"
    if score >= 0.35:
        return "monitor"
    return "weak"


# ---------------------------------------------------------------------------
# Source classification helpers
# ---------------------------------------------------------------------------

def source_contribution_role(row: dict[str, Any]) -> str:
    """Determine the contribution role of a source in the research package."""
    role = text_value(row.get("contribution_role"))
    if role:
        return role
    # Infer from source type
    source_type = text_value(row.get("source_type")).lower()
    if source_type in {"primary_research", "company_filing", "annual_report"}:
        return "anchor"
    if source_type in {"industry_report", "broker_report", "sell_side"}:
        return "corroborating"
    return "supporting"


def source_focus(row: dict[str, Any]) -> str:
    """Summarize what aspect of the opportunity this source informs."""
    return text_value(row.get("focus") or row.get("information_role") or row.get("reason"))


def source_reason(row: dict[str, Any]) -> str:
    """Why this source is included in the scorecard."""
    return text_value(row.get("reason") or row.get("focus"))


def source_information_role(row: dict[str, Any]) -> str:
    """Classify the information type this source provides."""
    role = text_value(row.get("information_role"))
    if role:
        return role
    source_type = text_value(row.get("source_type")).lower()
    if "financial" in source_type or "finan" in source_type:
        return "financial_data"
    if "industry" in source_type:
        return "industry_context"
    return "general_intelligence"


# ---------------------------------------------------------------------------
# Elo-enhanced scoring
# ---------------------------------------------------------------------------

def enhanced_quality_score(
    record: dict[str, Any],
    elo_rating: float | None = None,
) -> float:
    """Quality score that blends static formula with Elo when available.

    If elo_rating is None, falls back to pure weighted formula.
    """
    from chatgptrest.finbot_modules.elo_scoring import blended_quality_score

    base = source_quality_score(record) * 100.0  # convert 0-1 to 0-100
    if elo_rating is not None:
        return round(blended_quality_score(base, elo_rating) / 100.0, 3)
    return round(base / 100.0, 3)


def source_keep_or_downgrade(
    record: dict[str, Any],
    elo_rating: float | None = None,
) -> dict[str, Any]:
    """Produce a keep/downgrade recommendation for the dashboard.

    Returns: {decision, reason, score, band, elo_confidence}
    """
    from chatgptrest.finbot_modules.elo_scoring import elo_confidence_label

    score = enhanced_quality_score(record, elo_rating)
    band = source_quality_band(score)
    contradicted = int(record.get("contradicted_claim_count") or 0)
    supported = int(record.get("supported_claim_count") or 0)

    elo_conf = elo_confidence_label(elo_rating) if elo_rating else "no_elo_data"

    if band == "weak" or (contradicted > supported and supported > 0):
        decision = "downgrade"
        reason = "Quality band is weak or contradictions exceed supported claims."
    elif band == "monitor" and elo_conf in {"skeptical", "unreliable"}:
        decision = "downgrade"
        reason = "Monitor-level source with declining Elo confidence."
    elif band in {"core", "useful"} and elo_conf in {"high_confidence", "moderate_confidence"}:
        decision = "keep"
        reason = f"Strong quality ({band}) with {elo_conf.replace('_', ' ')} Elo rating."
    else:
        decision = "keep_with_review"
        reason = f"Quality band: {band}. Elo: {elo_conf}. Recommend periodic review."

    return {
        "decision": decision,
        "reason": reason,
        "score": score,
        "band": band,
        "elo_confidence": elo_conf,
    }
