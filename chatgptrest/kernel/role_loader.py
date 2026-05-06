"""Role loader — YAML-based role configuration loading.

Loads RoleSpec definitions from ``config/agent_roles.yaml`` and provides
lookup by role name.

Usage::

    from chatgptrest.kernel.role_loader import load_roles, get_role

    roles = load_roles()          # Dict[str, RoleSpec]
    devops = get_role("devops")   # RoleSpec or None
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_RELPATH = "config/agent_roles.yaml"
_cached_roles: dict[str, Any] | None = None


def _find_config() -> Path:
    """Find agent_roles.yaml relative to the project root."""
    # Try relative to ChatgptREST root
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / _CONFIG_RELPATH
    if candidate.exists():
        return candidate
    # Try env override
    env_path = os.environ.get("CHATGPTREST_ROLES_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    raise FileNotFoundError(
        f"agent_roles.yaml not found at {candidate} or via $CHATGPTREST_ROLES_PATH"
    )


def load_roles(config_path: str | Path | None = None) -> dict[str, "RoleSpec"]:
    """Load role definitions from YAML. Returns {role_name: RoleSpec}.

    Results are cached after first load. Pass config_path to override.
    """
    global _cached_roles
    if _cached_roles is not None and config_path is None:
        return _cached_roles

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyYAML not installed — role loading disabled")
        return {}

    from chatgptrest.kernel.team_types import RoleSpec

    path = Path(config_path) if config_path else _find_config()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "roles" not in data:
        logger.warning("agent_roles.yaml missing 'roles' key")
        return {}

    roles: dict[str, RoleSpec] = {}
    for name, cfg in data["roles"].items():
        if not isinstance(cfg, dict):
            continue
        cfg["name"] = name
        if not cfg.get("memory_namespace"):
            cfg["memory_namespace"] = name  # Default: role name = namespace
        roles[name] = RoleSpec.from_dict(cfg)

    if config_path is None:
        _cached_roles = roles

    logger.info("Loaded %d role definitions from %s", len(roles), path)
    return roles


def get_role(name: str) -> "RoleSpec | None":
    """Get a specific role by name. Returns None if not found."""
    roles = load_roles()
    return roles.get(name)


def clear_cache() -> None:
    """Clear the cached roles (for testing)."""
    global _cached_roles
    _cached_roles = None
