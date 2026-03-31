#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_expected_reviewers(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviewers = payload.get("reviewers") if isinstance(payload, dict) else None
    if not isinstance(reviewers, list):
        return []
    result: list[str] = []
    for item in reviewers:
        if not isinstance(item, dict):
            continue
        reviewer = str(item.get("reviewer") or "").strip()
        if reviewer:
            result.append(reviewer)
    return sorted(dict.fromkeys(result))


def _candidate_names(payload: dict[str, Any], stem: str) -> list[str]:
    names: list[str] = []
    for scope in (payload, payload.get("meta") if isinstance(payload.get("meta"), dict) else None):
        if not isinstance(scope, dict):
            continue
        for key in ("reviewer", "reviewer_name", "reviewer_id", "lane", "lane_id"):
            value = str(scope.get(key) or "").strip()
            if value:
                names.append(value)
    if stem:
        names.append(stem)
    return names


def resolve_reviewer_name(path: Path, payload: dict[str, Any], expected_reviewers: list[str] | None = None) -> str:
    expected = [str(item).strip() for item in (expected_reviewers or []) if str(item).strip()]
    stem = path.stem.strip()
    candidates = _candidate_names(payload, stem)

    for candidate in candidates:
        if candidate in expected:
            return candidate

    if expected:
        lowered = {item.lower(): item for item in expected}
        haystacks = [candidate.lower() for candidate in candidates if candidate]
        matches = []
        for lower_name, canonical in lowered.items():
            if any(lower_name in hay for hay in haystacks):
                matches.append(canonical)
        matches = sorted(dict.fromkeys(matches))
        if len(matches) == 1:
            return matches[0]

    return candidates[0] if candidates else stem
