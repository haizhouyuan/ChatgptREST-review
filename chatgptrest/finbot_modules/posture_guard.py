"""Deterministic posture gating for finbot research packages."""
from __future__ import annotations

import time
from typing import Any

from chatgptrest.finbot_modules._helpers import text_value

_POSTURE_ORDER = {
    "watch": 0,
    "review": 0,
    "prepare_candidate": 1,
    "deepen_now": 2,
    "starter": 3,
    "invest_now": 4,
}


def _importance_rank(value: Any) -> int:
    text = text_value(value).lower()
    if text in {"critical", "p0", "load_bearing"}:
        return 0
    if text == "high":
        return 1
    if text == "medium":
        return 2
    return 3


def _select_target_claim_ids(claim_objects: list[dict[str, Any]], *, limit: int = 3) -> list[str]:
    load_bearing = [row for row in claim_objects if bool(row.get("is_load_bearing"))]
    ranked = sorted(
        load_bearing or claim_objects,
        key=lambda row: (_importance_rank(row.get("importance")), text_value(row.get("claim_id"))),
    )
    return [text_value(row.get("claim_id")) for row in ranked[: max(1, limit)] if text_value(row.get("claim_id"))]


def _cap_posture(current: str, cap: str) -> str:
    current_rank = _POSTURE_ORDER.get(text_value(current).lower(), 0)
    cap_rank = _POSTURE_ORDER.get(text_value(cap).lower(), 0)
    return current if current_rank <= cap_rank else cap


def _has_material_counterevidence(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        stance = text_value(row.get("stance")).lower()
        excerpt = text_value(row.get("excerpt"))
        if stance and stance != "no_refute_found" and excerpt:
            return True
    return False


def evaluate_posture_guard(
    *,
    package_payload: dict[str, Any],
    claim_evidence_bindings: dict[str, Any],
    counterevidence_packets: dict[str, Any],
) -> dict[str, Any]:
    tier = text_value(package_payload.get("tier"))
    current_decision = text_value(package_payload.get("current_decision") or "watch")
    claim_objects = list(package_payload.get("claim_objects") or [])
    claim_ids = _select_target_claim_ids(claim_objects)
    bindings_by_claim: dict[str, list[dict[str, Any]]] = {}
    for row in claim_evidence_bindings.get("bindings") or []:
        claim_id = text_value(row.get("claim_id"))
        if claim_id:
            bindings_by_claim.setdefault(claim_id, []).append(dict(row))
    packets_by_claim: dict[str, list[dict[str, Any]]] = {}
    for row in counterevidence_packets.get("packets") or []:
        claim_id = text_value(row.get("claim_id"))
        if claim_id:
            packets_by_claim.setdefault(claim_id, []).append(dict(row))

    missing_evidence = [
        claim_id
        for claim_id in claim_ids
        if not [
            row
            for row in bindings_by_claim.get(claim_id, [])
            if not bool(row.get("missing_primary_evidence"))
        ]
    ]
    missing_counterevidence = [
        claim_id
        for claim_id in claim_ids
        if not _has_material_counterevidence(packets_by_claim.get(claim_id, []))
    ]

    blocked_reasons: list[str] = []
    max_allowed_posture = current_decision or "watch"
    if missing_evidence:
        blocked_reasons.append("Load-bearing claims still lack exact primary evidence.")
        max_allowed_posture = _cap_posture(max_allowed_posture, "watch")
    if missing_counterevidence:
        blocked_reasons.append("Skeptic lane has not attached claim-level counterevidence yet.")
        max_allowed_posture = _cap_posture(max_allowed_posture, "prepare_candidate")
    if tier == "free-tier":
        if _POSTURE_ORDER.get(text_value(max_allowed_posture).lower(), 0) > _POSTURE_ORDER["prepare_candidate"]:
            blocked_reasons.append("Free tier cannot emit final investment posture.")
        max_allowed_posture = _cap_posture(max_allowed_posture, "prepare_candidate")

    promotion_packet = dict(package_payload.get("promotion_packet") or {})
    first_hand_sources = list(promotion_packet.get("first_hand_source_to_check") or [])
    promote_to_paid = False
    if tier == "free-tier":
        promote_to_paid = bool(promotion_packet.get("promote_bool")) and bool(first_hand_sources)
        if not first_hand_sources:
            blocked_reasons.append("No first-hand source queued for paid promotion.")

    return {
        "generated_at": time.time(),
        "candidate_id": text_value(package_payload.get("candidate_id")),
        "raw_current_decision": current_decision,
        "max_allowed_posture": max_allowed_posture,
        "promote_to_paid": promote_to_paid,
        "blocked_reasons": blocked_reasons,
        "missing_evidence": missing_evidence,
        "missing_counterevidence": missing_counterevidence,
    }
