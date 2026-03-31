"""Counterevidence packet builders for skeptic lane consumption."""
from __future__ import annotations

import time
from typing import Any

from chatgptrest.finbot_modules._helpers import slugify, text_value


def _importance_rank(value: Any) -> int:
    text = text_value(value).lower()
    if text in {"critical", "p0", "load_bearing"}:
        return 0
    if text == "high":
        return 1
    if text == "medium":
        return 2
    return 3


def _select_target_claims(claim_objects: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    load_bearing = [row for row in claim_objects if bool(row.get("is_load_bearing"))]
    ranked = sorted(
        load_bearing or claim_objects,
        key=lambda row: (_importance_rank(row.get("importance")), text_value(row.get("claim_id"))),
    )
    return ranked[: max(1, limit)]


def _supporting_counter_source(
    *,
    source_scorecard: list[dict[str, Any]],
    kol_summary: dict[str, Any] | None,
) -> dict[str, str]:
    for row in source_scorecard:
        role = text_value(row.get("contribution_role")).lower()
        if role in {"corroborating", "derived"}:
            return {
                "source_id": text_value(row.get("source_id")) or slugify(text_value(row.get("name"))),
                "source_name": text_value(row.get("name")),
                "detail_href": text_value(row.get("detail_href")),
                "artifact_id": f"artifact:{slugify(text_value(row.get('source_id')) or text_value(row.get('name')))}",
            }
    suite_slug = text_value((kol_summary or {}).get("suite_slug"))
    if suite_slug:
        return {
            "source_id": f"kol_suite:{suite_slug}",
            "source_name": "KOL suite",
            "detail_href": "",
            "artifact_id": f"artifact:{slugify(suite_slug)}",
        }
    return {
        "source_id": "skeptic_lane",
        "source_name": "Skeptic lane",
        "detail_href": "",
        "artifact_id": "artifact:skeptic-lane",
    }


def build_counterevidence_packets(
    *,
    candidate_id: str,
    claim_objects: list[dict[str, Any]],
    risk_register: list[dict[str, Any]],
    disconfirming_signals: list[str],
    source_scorecard: list[dict[str, Any]],
    kol_summary: dict[str, Any] | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    target_claims = _select_target_claims(claim_objects, limit=limit)
    base_source = _supporting_counter_source(source_scorecard=source_scorecard, kol_summary=kol_summary)
    counter_rows: list[str] = []
    for row in risk_register:
        risk = text_value(row.get("risk"))
        if risk:
            detail = " | ".join(part for part in [risk, text_value(row.get("what_confirms")), text_value(row.get("what_refutes"))] if part)
            counter_rows.append(detail)
    counter_rows.extend(text_value(row) for row in disconfirming_signals if text_value(row))
    packets: list[dict[str, Any]] = []
    for idx, claim in enumerate(target_claims):
        claim_id = text_value(claim.get("claim_id"))
        excerpt = counter_rows[idx] if idx < len(counter_rows) else ""
        stance = "weaken" if excerpt else "no_refute_found"
        packets.append(
            {
                "claim_id": claim_id,
                "source_id": base_source["source_id"],
                "source_name": base_source["source_name"],
                "artifact_id": base_source["artifact_id"],
                "detail_href": base_source["detail_href"],
                "excerpt": excerpt,
                "stance": stance,
                "confidence": "medium" if excerpt else "low",
            }
        )
    return {
        "generated_at": time.time(),
        "candidate_id": candidate_id,
        "packets": packets,
    }
