"""Claim evidence binding helpers.

Bind load-bearing claims to concrete source/artifact excerpts when available.
This module is intentionally pure: no filesystem or network I/O.
"""
from __future__ import annotations

import hashlib
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
        key=lambda row: (
            _importance_rank(row.get("importance")),
            text_value(row.get("claim_id")),
        ),
    )
    return ranked[: max(1, limit)]


def _source_lookup(source_scorecard: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in source_scorecard:
        source_id = text_value(row.get("source_id"))
        source_name = text_value(row.get("name"))
        if source_id:
            by_id[source_id] = dict(row)
        if source_name:
            by_name[source_name.lower()] = dict(row)
    return by_id, by_name


def _source_row(
    source: dict[str, Any],
    *,
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = text_value(source.get("source_id"))
    source_name = text_value(source.get("name"))
    if source_id and source_id in by_id:
        return {**by_id[source_id], **source}
    if source_name and source_name.lower() in by_name:
        return {**by_name[source_name.lower()], **source}
    return dict(source)


def _primaryness(row: dict[str, Any]) -> str:
    contribution_role = text_value(row.get("contribution_role")).lower()
    source_type = text_value(row.get("source_type")).lower()
    trust_tier = text_value(row.get("source_trust_tier")).lower()
    if contribution_role == "anchor" or trust_tier == "anchor" or source_type == "official_disclosure":
        return "primary"
    return "secondary"


def _best_excerpt(claim_row: dict[str, Any], source_row: dict[str, Any]) -> tuple[str, bool, str]:
    exact = (
        text_value(source_row.get("exact_quote"))
        or text_value(source_row.get("exact_excerpt"))
        or text_value(source_row.get("excerpt"))
        or text_value(source_row.get("evidence_excerpt"))
        or text_value(claim_row.get("exact_quote"))
        or text_value(claim_row.get("exact_excerpt"))
        or text_value(claim_row.get("excerpt"))
    )
    if exact:
        return exact, True, "exact_quote"
    fallback = (
        text_value(source_row.get("evidence_snippet"))
        or text_value(source_row.get("focus"))
        or text_value(source_row.get("reason"))
        or text_value(claim_row.get("support_note"))
    )
    if fallback:
        return fallback, False, "derived_summary"
    return "", False, ""


def _excerpt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def build_claim_evidence_bindings(
    *,
    candidate_id: str,
    claim_objects: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
    source_scorecard: list[dict[str, Any]],
    limit: int = 3,
) -> dict[str, Any]:
    claim_rows = {
        text_value(row.get("claim_id")): dict(row)
        for row in claim_ledger
        if text_value(row.get("claim_id"))
    }
    by_id, by_name = _source_lookup(source_scorecard)
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in _select_target_claims(claim_objects, limit=limit):
        claim_id = text_value(claim.get("claim_id"))
        if not claim_id:
            continue
        claim_row = {**claim, **claim_rows.get(claim_id, {})}
        supporting_sources = list(claim_row.get("supporting_sources") or [])
        if not supporting_sources:
            bindings.append(
                {
                    "claim_id": claim_id,
                    "source_id": "",
                    "source_name": "",
                    "artifact_id": f"claim:{slugify(claim_id)}",
                    "detail_href": "",
                    "excerpt": "",
                    "excerpt_hash": "",
                    "excerpt_origin": "",
                    "is_exact_excerpt": False,
                    "stance": "support",
                    "primaryness": "primary",
                    "missing_primary_evidence": True,
                }
            )
            continue
        wrote_binding = False
        for raw_source in supporting_sources:
            source = _source_row(dict(raw_source), by_id=by_id, by_name=by_name)
            source_id = text_value(source.get("source_id")) or slugify(text_value(source.get("name")))
            edge_key = f"{claim_id}:{source_id}"
            if edge_key in seen:
                continue
            seen.add(edge_key)
            excerpt, is_exact, excerpt_origin = _best_excerpt(claim_row, source)
            primaryness = _primaryness(source)
            missing_primary = primaryness == "primary" and not is_exact
            bindings.append(
                {
                    "claim_id": claim_id,
                    "source_id": source_id,
                    "source_name": text_value(source.get("name")),
                    "artifact_id": f"artifact:{slugify(source_id or text_value(source.get('name')))}",
                    "detail_href": text_value(source.get("detail_href")),
                    "excerpt": excerpt,
                    "excerpt_hash": _excerpt_hash(excerpt),
                    "excerpt_origin": excerpt_origin,
                    "is_exact_excerpt": is_exact,
                    "stance": "support",
                    "primaryness": primaryness,
                    "missing_primary_evidence": missing_primary,
                }
            )
            wrote_binding = True
        if not wrote_binding:
            bindings.append(
                {
                    "claim_id": claim_id,
                    "source_id": "",
                    "source_name": "",
                    "artifact_id": f"claim:{slugify(claim_id)}",
                    "detail_href": "",
                    "excerpt": "",
                    "excerpt_hash": "",
                    "excerpt_origin": "",
                    "is_exact_excerpt": False,
                    "stance": "support",
                    "primaryness": "primary",
                    "missing_primary_evidence": True,
                }
            )
    return {
        "generated_at": time.time(),
        "candidate_id": candidate_id,
        "bindings": bindings,
    }
