"""Claim processing logic — IDs, status, matching, reversal detection, evolution.

Extracted from finbot.py to reduce monolith size and improve testability.
All functions are pure (no side effects, no I/O) except for time.time() calls.
"""
from __future__ import annotations

import time
from difflib import SequenceMatcher
from typing import Any

from chatgptrest.finbot_modules._helpers import (
    as_float,
    normalized_claim_text,
    slugify,
    stable_digest,
    text_value,
)


# ---------------------------------------------------------------------------
# Claim ID generation
# ---------------------------------------------------------------------------

def stable_claim_id(*, candidate_id: str, claim: str) -> str:
    return f"clm_{stable_digest({'candidate_id': candidate_id, 'claim': claim})}"


def stable_citation_id(*, source_id: str, source_name: str) -> str:
    return f"cit_{stable_digest({'source_id': source_id or slugify(source_name), 'name': source_name})}"


# ---------------------------------------------------------------------------
# Claim classification helpers
# ---------------------------------------------------------------------------

def support_confidence(evidence_grade: str, contribution_role: str) -> str:
    grade = text_value(evidence_grade).lower()
    role = text_value(contribution_role).lower()
    if grade in {"high", "strong"} or role == "anchor":
        return "high"
    if grade in {"medium", "moderate"} or role == "corroborating":
        return "medium"
    return "low"


def claim_kind_from_row(row: dict[str, Any]) -> str:
    importance = text_value(row.get("importance")).lower()
    if importance == "high":
        return "core"
    if importance == "medium":
        return "supporting"
    return "monitor"


def claim_status_from_row(row: dict[str, Any]) -> str:
    next_check = text_value(row.get("next_check"))
    return "active" if next_check else "formed"


def claim_load_bearing(row: dict[str, Any]) -> bool:
    importance = text_value(row.get("importance")).lower()
    return importance in {"critical", "high", "p0", "load_bearing"} or claim_kind_from_row(row) == "core"


def claim_relevance_label(row: dict[str, Any]) -> str:
    if claim_load_bearing(row):
        return "decision_blocker"
    if text_value(row.get("evidence_grade")).lower() in {"weak", "speculative"}:
        return "needs_proof"
    return "supporting"


def claim_falsification_condition(row: dict[str, Any], disconfirming_signals: list[str]) -> str:
    explicit = text_value(row.get("falsification_condition"))
    if explicit:
        return explicit
    importance = text_value(row.get("importance")).lower()
    if importance in {"critical", "high", "p0"} and disconfirming_signals:
        return disconfirming_signals[0]
    return text_value(row.get("next_check"))


# ---------------------------------------------------------------------------
# Semantic reversal detection
# ---------------------------------------------------------------------------

_DIRECTION_PAIRS: dict[str, str] = {
    "增长": "下滑", "增加": "减少", "上升": "下降", "上涨": "下跌",
    "提升": "下降", "扩张": "收缩", "加速": "放缓", "盈利": "亏损",
    "增持": "减持", "利好": "利空", "超预期": "不及预期", "买入": "卖出",
    "增强": "削弱", "改善": "恶化", "回升": "回落", "突破": "跌破",
    "高于": "低于", "看多": "看空", "乐观": "悲观", "领先": "落后",
    "扩大": "缩小", "加仓": "减仓", "推荐": "回避", "强劲": "疲软",
    "繁荣": "萎缩", "复苏": "衰退", "正增长": "负增长",
    "升级": "降级", "加码": "削减", "涨停": "跌停",
}

_DIRECTION_REVERSE: dict[str, str] = {v: k for k, v in _DIRECTION_PAIRS.items()}
_ALL_DIRECTION_WORDS: dict[str, str] = {**_DIRECTION_PAIRS, **_DIRECTION_REVERSE}


def has_semantic_reversal(text_a: str, text_b: str) -> bool:
    """Return True if two texts contain opposite directional words."""
    if not text_a or not text_b:
        return False
    for word, opposite in _ALL_DIRECTION_WORDS.items():
        if word in text_a and opposite in text_b:
            return True
    return False


# ---------------------------------------------------------------------------
# Claim matching and evolution
# ---------------------------------------------------------------------------

def match_previous_claim(row: dict[str, Any], previous_claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Match a claim row against previous claims, detecting evolution."""
    current_norm = normalized_claim_text(row.get("claim"))
    if not current_norm:
        return {}
    exact = next(
        (
            item
            for item in previous_claims
            if normalized_claim_text(item.get("claim_text")) == current_norm
        ),
        None,
    )
    if exact:
        return dict(exact)
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    current_kind = text_value(row.get("claim_kind") or claim_kind_from_row(row))
    for item in previous_claims:
        if current_kind and text_value(item.get("claim_kind")) and text_value(item.get("claim_kind")) != current_kind:
            continue
        ratio = SequenceMatcher(None, current_norm, normalized_claim_text(item.get("claim_text"))).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = item
    if best is not None and best_ratio >= 0.72:
        best_text = normalized_claim_text(best.get("claim_text"))
        if has_semantic_reversal(current_norm, best_text):
            return {**dict(best), "_match_status": "contradicted"}
        return dict(best)
    return {}


# ---------------------------------------------------------------------------
# Claim annotation and object building
# ---------------------------------------------------------------------------

def annotate_claim_rows(*, candidate_id: str, claim_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate raw claim rows with IDs, kinds, and status."""
    annotated: list[dict[str, Any]] = []
    for row in claim_ledger:
        claim_text = text_value(row.get("claim"))
        if not claim_text:
            continue
        annotated.append(
            {
                **row,
                "claim_id": text_value(row.get("claim_id")) or stable_claim_id(candidate_id=candidate_id, claim=claim_text),
                "claim_kind": text_value(row.get("claim_kind")) or claim_kind_from_row(row),
                "status": text_value(row.get("status")) or claim_status_from_row(row),
                "supersedes_claim_id": text_value(row.get("supersedes_claim_id")),
            }
        )
    return annotated


def build_claim_objects(
    *,
    candidate_id: str,
    claim_ledger: list[dict[str, Any]],
    previous_payload: dict[str, Any] | None,
    disconfirming_signals: list[str],
) -> list[dict[str, Any]]:
    """Build structured claim objects with evolution tracking."""
    rows = annotate_claim_rows(candidate_id=candidate_id, claim_ledger=claim_ledger)
    previous_claims = list((previous_payload or {}).get("claim_objects") or [])
    claim_objects: list[dict[str, Any]] = []
    for row in rows:
        previous = match_previous_claim(row, previous_claims)
        now = time.time()
        first_seen_at = as_float(previous.get("first_seen_at")) or as_float((previous_payload or {}).get("generated_at")) or now
        previous_claim_id = text_value(previous.get("claim_id"))
        claim_id = row["claim_id"]
        evolution_status = "new"
        if previous.get("_match_status") == "contradicted":
            evolution_status = "contradicted"
        elif previous and normalized_claim_text(previous.get("claim_text")) == normalized_claim_text(row.get("claim")):
            evolution_status = "persistent"
        elif previous_claim_id and previous_claim_id != claim_id:
            evolution_status = "reframed"
        falsification_cond = claim_falsification_condition(row, disconfirming_signals)
        is_load_bearing = claim_load_bearing(row)
        claim_objects.append(
            {
                "claim_id": claim_id,
                "claim_text": text_value(row.get("claim")),
                "claim_kind": text_value(row.get("claim_kind")),
                "status": text_value(row.get("status")),
                "evidence_grade": text_value(row.get("evidence_grade")),
                "importance": text_value(row.get("importance")),
                "why_it_matters": text_value(row.get("why_it_matters")),
                "next_check": text_value(row.get("next_check")),
                "support_note": text_value(row.get("support_note")),
                "falsification_condition": falsification_cond,
                "is_load_bearing": is_load_bearing,
                "decision_relevance": claim_relevance_label(row),
                "first_seen_at": first_seen_at,
                "last_seen_at": now,
                "evolution_status": evolution_status,
                "supersedes_claim_id": text_value(row.get("supersedes_claim_id")) or (previous_claim_id if evolution_status == "reframed" else ""),
            }
        )
    return claim_objects
