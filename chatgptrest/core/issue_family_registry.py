from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = REPO_ROOT / "docs" / "issue_family_registry.json"


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _text_fragments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for key, inner in sorted(value.items(), key=lambda item: str(item[0])):
            out.extend(_text_fragments(key))
            out.extend(_text_fragments(inner))
        return out
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for inner in value:
            out.extend(_text_fragments(inner))
        return out
    text = str(value).strip()
    return [text] if text else []


@lru_cache(maxsize=1)
def load_issue_family_registry() -> list[dict[str, Any]]:
    if not _REGISTRY_PATH.exists():
        return []
    try:
        payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    families = payload.get("families") if isinstance(payload, dict) else None
    if not isinstance(families, list):
        return []
    out: list[dict[str, Any]] = []
    for family in families:
        if not isinstance(family, dict):
            continue
        family_id = _normalize(family.get("family_id"))
        family_label = str(family.get("family_label") or "").strip()
        if not family_id or not family_label:
            continue
        match = family.get("match") if isinstance(family.get("match"), dict) else {}
        kinds = [_normalize(x) for x in match.get("kinds") or [] if _normalize(x)]
        any_terms = [_normalize(x) for x in match.get("any_terms") or [] if _normalize(x)]
        all_terms = [_normalize(x) for x in match.get("all_terms") or [] if _normalize(x)]
        out.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "kinds": kinds,
                "any_terms": any_terms,
                "all_terms": all_terms,
            }
        )
    return out


def match_issue_family(issue: dict[str, Any]) -> tuple[str | None, str | None]:
    kind = _normalize(issue.get("kind"))
    haystack = _normalize(
        " ".join(
            _text_fragments(
                [
                    issue.get("title"),
                    issue.get("symptom"),
                    issue.get("raw_error"),
                    issue.get("family_id"),
                    issue.get("family_label"),
                    issue.get("tags") or [],
                    issue.get("metadata") or {},
                ]
            )
        )
    )
    for family in load_issue_family_registry():
        if family["kinds"] and kind not in family["kinds"]:
            continue
        if family["all_terms"] and not all(term in haystack for term in family["all_terms"]):
            continue
        if family["any_terms"] and not any(term in haystack for term in family["any_terms"]):
            continue
        return str(family["family_id"]), str(family["family_label"])
    return None, None
