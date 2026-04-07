"""Promotion packet builders for finbotfree and theme batch outputs."""
from __future__ import annotations

import time
from typing import Any

from chatgptrest.finbot_modules._helpers import text_value


def _first_hand_sources(source_scorecard: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in source_scorecard:
        source_type = text_value(row.get("source_type")).lower()
        contribution_role = text_value(row.get("contribution_role")).lower()
        trust_tier = text_value(row.get("source_trust_tier")).lower()
        if source_type != "official_disclosure" and contribution_role != "anchor" and trust_tier != "anchor":
            continue
        rows.append(
            {
                "source_id": text_value(row.get("source_id")),
                "name": text_value(row.get("name")),
                "detail_href": text_value(row.get("detail_href")),
            }
        )
    return rows[:3]


def build_promotion_packet(
    *,
    logical_key: str,
    candidate_id: str,
    thesis_name: str,
    current_decision: str,
    why_now: str,
    source_scorecard: list[dict[str, Any]],
    novelty_hint: list[str],
    blocked_by: list[str] | None = None,
    tier: str = "",
) -> dict[str, Any]:
    first_hand = _first_hand_sources(source_scorecard)
    decision = text_value(current_decision).lower()
    promote = bool(first_hand) and decision in {"prepare_candidate", "deepen_now", "starter"}
    return {
        "generated_at": time.time(),
        "logical_key": logical_key,
        "candidate_id": candidate_id,
        "thesis_name": thesis_name,
        "why_now": text_value(why_now),
        "first_hand_source_to_check": first_hand,
        "novelty_hint": [text_value(row) for row in novelty_hint if text_value(row)][:4],
        "promote_bool": promote,
        "blocked_by": [text_value(row) for row in (blocked_by or []) if text_value(row)],
        "tier": tier,
    }
