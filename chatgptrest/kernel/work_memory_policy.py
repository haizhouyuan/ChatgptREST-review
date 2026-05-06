"""Declarative governance loader for durable work-memory objects."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_RELPATH = "config/work_memory_governance.yaml"
_cached_policy: "WorkMemoryGovernancePolicy | None" = None


@dataclass(frozen=True)
class WorkMemoryGovernancePolicy:
    version: int
    approval_policy: str
    allow_approved_sources: frozenset[str]
    require_identity_fields: tuple[str, ...]
    require_provenance_quality: str


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _find_config() -> Path:
    candidate = _project_root() / _CONFIG_RELPATH
    if candidate.exists():
        return candidate
    env_path = os.environ.get("CHATGPTREST_WORK_MEMORY_GOVERNANCE_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
    raise FileNotFoundError(
        f"work-memory governance config not found at {candidate} "
        "or via $CHATGPTREST_WORK_MEMORY_GOVERNANCE_PATH"
    )


def load_work_memory_governance(config_path: str | Path | None = None) -> WorkMemoryGovernancePolicy:
    global _cached_policy
    if _cached_policy is not None and config_path is None:
        return _cached_policy

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyYAML not installed — using fallback work-memory governance policy")
        return _fallback_policy()

    try:
        path = Path(config_path) if config_path else _find_config()
    except FileNotFoundError:
        logger.warning("work-memory governance config missing — using fallback policy")
        return _fallback_policy()

    if not path.exists():
        logger.warning("work-memory governance config not found at %s — using fallback policy", path)
        return _fallback_policy()

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        logger.warning("work-memory governance config is not a mapping — using fallback policy")
        return _fallback_policy()

    approval = raw.get("approval") if isinstance(raw.get("approval"), dict) else {}
    policy = WorkMemoryGovernancePolicy(
        version=int(raw.get("version", 1) or 1),
        approval_policy=str(approval.get("policy_name") or "allowlisted_source_complete_identity").strip()
        or "allowlisted_source_complete_identity",
        allow_approved_sources=frozenset(
            str(item).strip().lower()
            for item in list(approval.get("allow_approved_sources") or [])
            if str(item).strip()
        ),
        require_identity_fields=tuple(
            str(item).strip()
            for item in list(approval.get("require_identity_fields") or ["account_id", "role_id"])
            if str(item).strip()
        ),
        require_provenance_quality=str(approval.get("require_provenance_quality") or "complete").strip().lower()
        or "complete",
    )

    if config_path is None:
        _cached_policy = policy
    return policy


def clear_work_memory_governance_cache() -> None:
    global _cached_policy
    _cached_policy = None


def _fallback_policy() -> WorkMemoryGovernancePolicy:
    return WorkMemoryGovernancePolicy(
        version=0,
        approval_policy="allowlisted_source_complete_identity",
        allow_approved_sources=frozenset(
            {
                "advisor_agent",
                "openclaw",
                "codex",
                "claude_code",
                "antigravity",
                "manual_review",
            }
        ),
        require_identity_fields=("account_id", "role_id"),
        require_provenance_quality="complete",
    )
