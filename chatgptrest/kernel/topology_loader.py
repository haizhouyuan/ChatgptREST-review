"""Topology contract loader.

Loads the canonical topology definition from ``config/topology.yaml``
and provides lookups for agents, sidecars, external tools, and retired items.

Usage::

    from chatgptrest.kernel.topology_loader import load_topology, get_baseline_agent_ids

    topo = load_topology()
    agent_ids = get_baseline_agent_ids()       # e.g. {"main"}
    sidecar = get_sidecar("guardian")          # dict or None
    is_retired = is_retired_agent("chatgptrest-orch")  # True
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_RELPATH = "config/topology.yaml"
_cached_topology: "TopologySpec | None" = None


@dataclass(frozen=True)
class TopologySpec:
    """Parsed topology contract."""

    version: int
    baseline: str
    topologies: dict[str, dict[str, Any]]
    sidecars: dict[str, dict[str, Any]]
    external_tools: dict[str, dict[str, Any]]
    retired_agents: list[str]
    retired_notes: str = ""

    def baseline_agent_ids(self) -> set[str]:
        """Return agent IDs for the current baseline topology."""
        topo = self.topologies.get(self.baseline, {})
        return set(topo.get("agents", []))

    def all_topology_agent_ids(self) -> dict[str, set[str]]:
        """Return {topology_name: set(agent_ids)} for all defined topologies."""
        return {
            name: set(cfg.get("agents", []))
            for name, cfg in self.topologies.items()
        }


def _find_config() -> Path:
    """Find topology.yaml relative to the project root."""
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / _CONFIG_RELPATH
    if candidate.exists():
        return candidate
    env_path = os.environ.get("CHATGPTREST_TOPOLOGY_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    raise FileNotFoundError(
        f"topology.yaml not found at {candidate} or via $CHATGPTREST_TOPOLOGY_PATH"
    )


def _parse_topology(data: dict[str, Any]) -> TopologySpec:
    """Parse raw YAML dict into TopologySpec."""
    version = int(data.get("version", 1))
    baseline = str(data.get("baseline", "lean"))

    topologies: dict[str, dict[str, Any]] = {}
    for name, cfg in (data.get("topologies") or {}).items():
        if isinstance(cfg, dict):
            topologies[name] = cfg

    sidecars: dict[str, dict[str, Any]] = {}
    for name, cfg in (data.get("sidecars") or {}).items():
        if isinstance(cfg, dict):
            sidecars[name] = cfg

    external_tools: dict[str, dict[str, Any]] = {}
    for name, cfg in (data.get("external_tools") or {}).items():
        if isinstance(cfg, dict):
            external_tools[name] = cfg

    retired = data.get("retired") or {}
    retired_agents = [str(a) for a in (retired.get("agents") or []) if a]
    retired_notes = str(retired.get("notes") or "")

    # Validate baseline exists
    if baseline not in topologies:
        logger.warning(
            "topology.yaml baseline %r not found in topologies %s; "
            "falling back to first topology or empty",
            baseline,
            list(topologies.keys()),
        )

    return TopologySpec(
        version=version,
        baseline=baseline,
        topologies=topologies,
        sidecars=sidecars,
        external_tools=external_tools,
        retired_agents=retired_agents,
        retired_notes=retired_notes,
    )


def load_topology(config_path: str | Path | None = None) -> TopologySpec:
    """Load and validate topology.yaml. Cached after first load."""
    global _cached_topology
    if _cached_topology is not None and config_path is None:
        return _cached_topology

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyYAML not installed — topology loading disabled")
        return _fallback_topology()

    try:
        path = Path(config_path) if config_path else _find_config()
    except FileNotFoundError:
        logger.warning("topology.yaml not found — using built-in defaults")
        return _fallback_topology()

    if not path.exists():
        logger.warning("topology.yaml not found at %s — using built-in defaults", path)
        return _fallback_topology()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        logger.warning("topology.yaml is not a dict — using built-in defaults")
        return _fallback_topology()

    spec = _parse_topology(data)

    if config_path is None:
        _cached_topology = spec

    logger.info(
        "Loaded topology contract v%d baseline=%s agents=%s sidecars=%s from %s",
        spec.version,
        spec.baseline,
        sorted(spec.baseline_agent_ids()),
        sorted(spec.sidecars.keys()),
        path,
    )
    return spec


def _fallback_topology() -> TopologySpec:
    """Hardcoded fallback when topology.yaml is unavailable."""
    return TopologySpec(
        version=0,
        baseline="lean",
        topologies={"lean": {"agents": ["main"]}, "ops": {"agents": ["main", "maintagent"]}},
        sidecars={
            "guardian": {
                "wake_agent": "main",
                "wake_session": "main-guardian",
            }
        },
        external_tools={},
        retired_agents=[],
    )


def get_baseline() -> str:
    """Return the baseline topology name."""
    return load_topology().baseline


def get_baseline_agent_ids() -> set[str]:
    """Return agent IDs for the current baseline topology."""
    return load_topology().baseline_agent_ids()


def get_sidecar(name: str) -> dict[str, Any] | None:
    """Return sidecar config by name."""
    return load_topology().sidecars.get(name)


def is_retired_agent(agent_id: str) -> bool:
    """Check if an agent ID is in the retired list."""
    return str(agent_id) in load_topology().retired_agents


def clear_cache() -> None:
    """Clear the cached topology (for testing)."""
    global _cached_topology
    _cached_topology = None
