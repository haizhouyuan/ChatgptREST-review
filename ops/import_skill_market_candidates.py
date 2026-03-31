from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.kernel.market_gate import get_capability_gap_recorder

DEFAULT_SOURCES_PATH = REPO_ROOT / "ops" / "policies" / "skill_market_sources_v1.json"


def resolve_market_sources_path(raw: str = "") -> Path:
    candidate = str(raw or "").strip() or os.environ.get("CHATGPTREST_SKILL_MARKET_SOURCES_PATH", "").strip()
    return Path(candidate).expanduser().resolve() if candidate else DEFAULT_SOURCES_PATH


def load_market_sources(path: str = "") -> dict[str, Any]:
    return json.loads(resolve_market_sources_path(path).read_text(encoding="utf-8"))


def list_market_sources(path: str = "") -> list[dict[str, Any]]:
    payload = load_market_sources(path)
    return [dict(item) for item in payload.get("sources") or []]


def _fetch_manifest_bytes(uri: str) -> bytes:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme in {"", "file"}:
        local_path = Path(parsed.path if parsed.scheme == "file" else uri).expanduser().resolve()
        return local_path.read_bytes()
    with urllib.request.urlopen(uri, timeout=30) as response:  # noqa: S310 - allowlisted source only
        return response.read()


def _canonical_origin(source_market: str, source_uri: str) -> tuple[str, str]:
    return source_market.strip(), source_uri.strip()


def _validate_manifest_uri(source: dict[str, Any], manifest_uri: str) -> str:
    candidate = str(manifest_uri or source.get("manifest_uri") or "").strip()
    if not candidate:
        raise ValueError("manifest_uri_required")
    allowed_prefixes = [str(item).strip() for item in source.get("allowed_uri_prefixes") or [] if str(item).strip()]
    if allowed_prefixes and not any(candidate.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(f"manifest_uri_not_allowlisted:{candidate}")
    return candidate


def _existing_candidate_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    recorder = get_capability_gap_recorder()
    rows = recorder.list_market_candidates(limit=1000)
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        origin = (row.skill_id.strip(), row.source_market.strip(), row.source_uri.strip())
        index[origin] = row.to_dict()
    return index


def import_market_source(
    source_id: str,
    *,
    manifest_uri: str = "",
    allow_disabled: bool = False,
    policy_path: str = "",
) -> dict[str, Any]:
    sources = {str(item.get("source_id") or "").strip(): item for item in list_market_sources(policy_path)}
    source = dict(sources.get(source_id) or {})
    if not source:
        raise KeyError(f"unknown_source_id:{source_id}")
    if not source.get("enabled") and not allow_disabled:
        raise ValueError(f"source_disabled:{source_id}")
    manifest_ref = _validate_manifest_uri(source, manifest_uri)
    manifest = json.loads(_fetch_manifest_bytes(manifest_ref).decode("utf-8"))
    candidates = list(manifest.get("candidates") or [])
    recorder = get_capability_gap_recorder()
    existing = _existing_candidate_index()
    imported: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    for raw in candidates:
        skill_id = str(raw.get("skill_id") or "").strip()
        source_uri = str(raw.get("source_uri") or "").strip()
        capability_ids = [str(item).strip() for item in raw.get("capability_ids") or [] if str(item).strip()]
        if not skill_id or not source_uri or not capability_ids:
            raise ValueError(f"invalid_candidate_record:{raw}")
        source_market = str(raw.get("source_market") or source.get("source_market") or "").strip()
        origin = _canonical_origin(source_market, source_uri)
        dedupe_key = (skill_id, origin[0], origin[1])
        if dedupe_key in existing:
            skipped_existing.append(existing[dedupe_key])
            continue
        evidence = dict(raw.get("evidence") or {})
        evidence.update(
            {
                "source_id": source_id,
                "source_kind": str(source.get("kind") or ""),
                "source_trust_level": str(source.get("trust_level") or ""),
                "manifest_uri": manifest_ref,
            }
        )
        candidate = recorder.register_market_candidate(
            skill_id=skill_id,
            source_market=source_market,
            source_uri=source_uri,
            capability_ids=capability_ids,
            linked_gap_id=str(raw.get("linked_gap_id") or "").strip(),
            summary=str(raw.get("summary") or "").strip(),
            evidence=evidence,
        )
        imported.append(candidate.to_dict())
        existing[dedupe_key] = candidate.to_dict()
    return {
        "source_id": source_id,
        "manifest_uri": manifest_ref,
        "imported_count": len(imported),
        "skipped_existing_count": len(skipped_existing),
        "imported": imported,
        "skipped_existing": skipped_existing,
    }
