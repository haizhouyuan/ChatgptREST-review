"""Elo-like dynamic source confidence scoring.

Adapts the chess Elo rating system to track source reliability over time:
- Sources start at 1500 (neutral)
- Validated claims boost rating, contradicted claims lower it
- K-factor controls sensitivity (higher = more reactive)
- Blends with the existing weighted quality_score for overall assessment
"""
from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_RATING = 1500.0
K_FACTOR = 32.0
# Outcome scores: 1.0 = validated, 0.0 = contradicted, 0.5 = neutral
OUTCOME_SCORES = {"validated": 1.0, "contradicted": 0.0, "neutral": 0.5}

# Blend weights for combined score
WEIGHTED_FORMULA_WEIGHT = 0.6
ELO_WEIGHT = 0.4

# Rating boundaries for normalization (maps 1000-2000 → 0.0-1.0)
RATING_FLOOR = 1000.0
RATING_CEILING = 2000.0


def expected_score(rating_a: float, rating_b: float = DEFAULT_RATING) -> float:
    """Calculate expected score using logistic Elo formula.

    E_A = 1 / (1 + 10^((R_B - R_A) / 400))
    """
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def elo_update(
    current_rating: float,
    outcome: str,
    *,
    k: float = K_FACTOR,
    opponent_rating: float = DEFAULT_RATING,
) -> float:
    """Apply a single Elo update based on a claim outcome.

    Args:
        current_rating: Source's current Elo rating.
        outcome: One of 'validated', 'contradicted', 'neutral'.
        k: K-factor controlling update magnitude.
        opponent_rating: Reference rating (default 1500 = market baseline).

    Returns:
        Updated rating.
    """
    actual = OUTCOME_SCORES.get(outcome, 0.5)
    exp = expected_score(current_rating, opponent_rating)
    new_rating = current_rating + k * (actual - exp)
    # Clamp to reasonable bounds
    return max(RATING_FLOOR * 0.5, min(RATING_CEILING * 1.5, new_rating))


def batch_elo_update(
    current_rating: float,
    outcomes: list[str],
    *,
    k: float = K_FACTOR,
) -> float:
    """Apply multiple successive Elo updates.

    Args:
        current_rating: Starting rating.
        outcomes: List of outcome strings ('validated', 'contradicted', 'neutral').
        k: K-factor for each update.

    Returns:
        Final rating after all updates.
    """
    rating = current_rating
    for outcome in outcomes:
        rating = elo_update(rating, outcome, k=k)
    return rating


def normalize_elo(rating: float) -> float:
    """Normalize Elo rating to 0.0-1.0 scale.

    Maps RATING_FLOOR to 0.0, RATING_CEILING to 1.0, with clamping.
    """
    if rating <= RATING_FLOOR:
        return 0.0
    if rating >= RATING_CEILING:
        return 1.0
    return (rating - RATING_FLOOR) / (RATING_CEILING - RATING_FLOOR)


def blended_quality_score(
    weighted_score: float,
    elo_rating: float,
    *,
    weighted_w: float = WEIGHTED_FORMULA_WEIGHT,
    elo_w: float = ELO_WEIGHT,
) -> float:
    """Blend static weighted quality score with Elo-based dynamic score.

    Args:
        weighted_score: Score from source_quality_score() (0-100 scale).
        elo_rating: Current Elo rating (1000-2000 scale).
        weighted_w: Weight for static score (default 0.6).
        elo_w: Weight for Elo score (default 0.4).

    Returns:
        Blended score on 0-100 scale.
    """
    elo_normalized = normalize_elo(elo_rating) * 100.0
    return weighted_w * weighted_score + elo_w * elo_normalized


def elo_trend_label(
    current_rating: float,
    previous_rating: float | None = None,
) -> str:
    """Determine trend label from Elo rating change.

    Returns: 'improving', 'stable', 'declining', or 'new'.
    """
    if previous_rating is None:
        return "new"
    delta = current_rating - previous_rating
    if delta > 20:
        return "improving"
    if delta < -20:
        return "declining"
    return "stable"


def elo_confidence_label(rating: float) -> str:
    """Human-readable confidence label from Elo rating."""
    if rating >= 1700:
        return "high_confidence"
    if rating >= 1550:
        return "moderate_confidence"
    if rating >= 1400:
        return "low_confidence"
    if rating >= 1250:
        return "skeptical"
    return "unreliable"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def load_elo_ledger(ledger_path: Path) -> dict[str, dict[str, Any]]:
    """Load the Elo rating ledger from disk.

    Returns dict mapping source_id to {rating, updated_at, outcome_history}.
    """
    if not ledger_path.exists():
        return {}
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to load Elo ledger %s: %s", ledger_path, exc)
    return {}


def save_elo_ledger(ledger_path: Path, ledger: dict[str, dict[str, Any]]) -> None:
    """Save the Elo rating ledger to disk."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = ledger_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(ledger_path)


def update_source_elo(
    ledger: dict[str, dict[str, Any]],
    source_id: str,
    outcomes: list[str],
    *,
    k: float = K_FACTOR,
) -> dict[str, Any]:
    """Update a single source's Elo rating in the ledger.

    Returns the updated entry.
    """
    entry = ledger.get(source_id, {})
    previous_rating = entry.get("rating", DEFAULT_RATING)
    new_rating = batch_elo_update(previous_rating, outcomes, k=k)

    # Keep recent outcome history (last 50)
    history = list(entry.get("outcome_history", []))
    for outcome in outcomes:
        history.append({"outcome": outcome, "ts": time.time()})
    history = history[-50:]

    entry = {
        "rating": round(new_rating, 2),
        "previous_rating": round(previous_rating, 2),
        "updated_at": time.time(),
        "trend_label": elo_trend_label(new_rating, previous_rating),
        "confidence_label": elo_confidence_label(new_rating),
        "outcome_count": len(history),
        "outcome_history": history,
    }
    ledger[source_id] = entry
    return entry
