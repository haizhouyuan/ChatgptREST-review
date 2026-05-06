from __future__ import annotations

import hashlib
from typing import Any, Mapping


CRYSTALLIZED_LEARNING_SCHEMA_VERSION = "openmind-learning-crystal-v1"
INTERACTION_LEARNING_MIN_SUPPORT = 2
CRYSTALLIZED_LEARNING_PROJECTION_MODE = "shadow"
CRYSTALLIZED_LEARNING_INVALIDATION_SLA = (
    "No later than the next thread-scoped interaction-learning load and packet compile after a newer stable winner is persisted."
)
_STABLE_PREFERENCE_KEYS = (
    "raw_ingress_mode",
    "quality_bar",
    "preferred_executor_family",
    "closure_style",
    "brevity_preference",
    "depth_preference",
    "focus_preference",
    "reply_first_preference",
)
_CRYSTAL_DENYLIST_KEYS = (
    "owner",
    "goal",
    "non_goals",
    "project_ref",
    "project_context",
    "planning_base",
    "frozen_facts",
    "style_rules",
    "authority_docs",
    "current_phase",
    "current_phase_framing",
    "last_reviewed_at",
    "quality_gate",
    "planning_profile",
    "required_sections",
)
_NON_PREFERENCE_PAYLOAD_KEYS = {
    "account_id",
    "thread_id",
    "project_id",
    "last_session_id",
    "record_id",
    "key",
    "kind",
    "source_message",
    "_preference_meta",
}


def _normalized_counts(raw_counts: Mapping[str, Any] | None) -> dict[str, int]:
    return {
        str(raw_key).strip(): int(raw_value or 0)
        for raw_key, raw_value in dict(raw_counts or {}).items()
        if str(raw_key).strip()
    }


def _detected_preference_keys(payload: Mapping[str, Any], meta: Mapping[str, Any]) -> list[str]:
    keys = {
        str(key).strip()
        for key in list(payload.keys()) + list(meta.keys())
        if str(key).strip()
        and str(key).strip() not in _NON_PREFERENCE_PAYLOAD_KEYS
        and not str(key).strip().startswith("_")
    }
    return sorted(keys)


def crystallized_learning_receipt(crystal: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(crystal or {})
    stable_preferences = dict(payload.get("stable_preferences") or {})
    governance = dict(payload.get("governance") or {})
    supersession = dict(payload.get("supersession") or {})
    return {
        "applied": bool(stable_preferences),
        "projection_mode": str(governance.get("projection_mode") or "").strip(),
        "support_threshold": int(payload.get("support_threshold") or INTERACTION_LEARNING_MIN_SUPPORT),
        "stable_preference_keys": sorted(str(key).strip() for key in stable_preferences if str(key).strip()),
        "superseded_count": int(supersession.get("superseded_count") or 0),
        "denied_preference_count": len(list(governance.get("denied_preference_keys") or [])),
        "shadow_required": bool(dict(payload.get("shadow_observation") or {}).get("required_before_wider_reuse")),
    }


def build_interaction_learning_crystal(
    learning_payload: Mapping[str, Any] | None,
    *,
    min_support: int = INTERACTION_LEARNING_MIN_SUPPORT,
) -> dict[str, Any] | None:
    payload = dict(learning_payload or {})
    meta = dict(payload.get("_preference_meta") or {})
    stable_preferences: dict[str, str] = {}
    support: dict[str, Any] = {}
    superseded: list[dict[str, Any]] = []
    detected_preference_keys = _detected_preference_keys(payload, meta)
    denied_preference_keys = [
        key
        for key in detected_preference_keys
        if key in _CRYSTAL_DENYLIST_KEYS or key not in _STABLE_PREFERENCE_KEYS
    ]
    for key in _STABLE_PREFERENCE_KEYS:
        value = str(payload.get(key) or "").strip()
        pref_meta = dict(meta.get(key) or {})
        counts = _normalized_counts(pref_meta.get("counts"))
        winner_count = int(counts.get(value) or 0)
        if not value or winner_count < int(min_support or INTERACTION_LEARNING_MIN_SUPPORT):
            continue
        stable_preferences[key] = value
        second_place_count = max(
            (int(alt_count or 0) for alt_key, alt_count in counts.items() if alt_key != value),
            default=0,
        )
        alternatives = {
            alt_key: alt_count
            for alt_key, alt_count in counts.items()
            if alt_key != value and int(alt_count or 0) > 0
        }
        support[key] = {
            "winner": value,
            "winner_count": winner_count,
            "support_threshold": int(min_support or INTERACTION_LEARNING_MIN_SUPPORT),
            "winner_margin": winner_count - second_place_count,
            "second_place_count": second_place_count,
            "alternatives": alternatives,
            "last_source_message": str(pref_meta.get("last_source_message") or "").strip(),
        }
        for alt_key, alt_count in sorted(alternatives.items(), key=lambda item: (-int(item[1] or 0), item[0])):
            if int(alt_count or 0) < int(min_support or INTERACTION_LEARNING_MIN_SUPPORT):
                continue
            superseded.append(
                {
                    "key": key,
                    "value": alt_key,
                    "support_count": int(alt_count or 0),
                    "status": "superseded_by_newer_winner",
                }
            )
    if not stable_preferences:
        return None

    source_record_id = str(payload.get("record_id") or "").strip()
    source_key = str(payload.get("key") or "").strip()
    scope = {
        "account_id": str(payload.get("account_id") or "").strip(),
        "thread_id": str(payload.get("thread_id") or "").strip(),
        "project_id": str(payload.get("project_id") or "").strip(),
        "last_session_id": str(payload.get("last_session_id") or "").strip(),
    }
    crystal_seed = "|".join(
        part
        for part in (
            source_record_id,
            source_key,
            ",".join(f"{key}={stable_preferences[key]}" for key in sorted(stable_preferences)),
        )
        if part
    )
    crystal_id = hashlib.sha1(crystal_seed.encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": CRYSTALLIZED_LEARNING_SCHEMA_VERSION,
        "crystal_id": crystal_id,
        "source_type": "interaction_learning",
        "source_record_id": source_record_id,
        "source_key": source_key,
        "scope": scope,
        "stable_preferences": stable_preferences,
        "support_threshold": int(min_support or INTERACTION_LEARNING_MIN_SUPPORT),
        "support": support,
        "provenance": {
            "record_id": source_record_id,
            "thread_key": source_key,
            "source_type": "interaction_learning",
            "detected_preference_keys": detected_preference_keys,
        },
        "governance": {
            "projection_mode": CRYSTALLIZED_LEARNING_PROJECTION_MODE,
            "allowlist": list(_STABLE_PREFERENCE_KEYS),
            "denylist": list(_CRYSTAL_DENYLIST_KEYS),
            "denied_preference_keys": denied_preference_keys,
            "support_threshold_change_requires_signoff": True,
            "cached_projection_risk": "none_detected_in_packet_compile_path",
        },
        "supersession": {
            "superseded_preferences": superseded,
            "superseded_count": len(superseded),
        },
        "invalidation": {
            "mode": "superseded_by_newer_interaction_learning_record",
            "key": source_key,
            "rule": "A newer interaction-learning record for the same key with a different stable winner supersedes this crystal.",
            "sla": CRYSTALLIZED_LEARNING_INVALIDATION_SLA,
        },
        "shadow_observation": {
            "required_before_wider_reuse": True,
            "status": "shadow_observe_only",
        },
        "precedence_note": "Advisory only. Never override the authority anchor with crystallized learning.",
    }
