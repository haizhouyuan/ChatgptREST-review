from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chatgptrest.providers.registry import provider_spec_for_provider_id

EXECUTION_LANES: frozenset[str] = frozenset(
    {
        "local",
        "web_standard",
        "web_premium",
        "deep_research",
        "coding_agent",
        "compat_legacy",
    }
)

AUTOMATION_ALLOWED_EXECUTION_LANES: frozenset[str] = frozenset({"web_standard", "web_premium", "deep_research"})
PREMIUM_EXECUTION_LANES: frozenset[str] = frozenset({"web_premium", "deep_research"})
_EXECUTION_LANE_ALIASES: dict[str, str] = {
    "web": "web_standard",
    "standard": "web_standard",
    "premium": "web_premium",
    "premium_web": "web_premium",
    "premiumweb": "web_premium",
    "research": "deep_research",
    "deepresearch": "deep_research",
    "deep-research": "deep_research",
    "legacy": "compat_legacy",
}


def normalize_requested_execution_lane(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = _EXECUTION_LANE_ALIASES.get(raw, raw)
    return normalized if normalized in EXECUTION_LANES else ""


def execution_lane_allowed_for_automation(lane: str | None) -> bool:
    return str(lane or "").strip().lower() in AUTOMATION_ALLOWED_EXECUTION_LANES


def execution_lane_is_premium(lane: str | None) -> bool:
    return str(lane or "").strip().lower() in PREMIUM_EXECUTION_LANES


def effective_execution_lane_for_web_request(
    *,
    provider_id: str | None,
    effective_preset: str | None,
    deep_research: bool | None,
) -> str:
    if bool(deep_research):
        return "deep_research"
    preset = str(effective_preset or "").strip().lower()
    if preset in {"deep_research", "research"}:
        return "deep_research"
    spec = provider_spec_for_provider_id(provider_id)
    if spec is not None and preset in spec.premium_presets:
        return "web_premium"
    if preset.startswith("pro") or preset.startswith("thinking"):
        return "web_premium"
    return "web_standard"


def execution_governance_selection_source(value: Any) -> str:
    raw = str(value or "").strip()
    return raw or "caller_declared"


def rewrite_source_for_reason(reason: Any) -> str | None:
    raw = str(reason or "").strip()
    return "provider_capability_matrix" if raw else None


def load_result_payload(*, artifacts_dir: Path, job_id: str) -> dict[str, Any]:
    try:
        payload = json.loads((artifacts_dir / "jobs" / str(job_id) / "result.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_runtime_fallback(payload: dict[str, Any] | None) -> dict[str, Any]:
    obj = dict(payload or {})
    fallback = obj.get("fallback")
    if isinstance(fallback, dict):
        return {
            "fallback_from": str(fallback.get("from_preset") or "").strip() or None,
            "fallback_to": str(fallback.get("to_preset") or "").strip() or None,
            "fallback_reason": str(fallback.get("reason") or "").strip() or None,
        }
    fallback_from = str(obj.get("_fallback_from") or "").strip() or None
    fallback_to = str(obj.get("_fallback_preset") or "").strip() or None
    fallback_reason = str(obj.get("_fallback_reason") or "").strip() or None
    if fallback_to and not fallback_reason:
        fallback_reason = "runtime_preset_fallback"
    return {
        "fallback_from": fallback_from,
        "fallback_to": fallback_to,
        "fallback_reason": fallback_reason,
    }
