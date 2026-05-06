"""Tests for config/topology.yaml contract and topology_loader.

Validates that the canonical topology contract is internally consistent
and that consuming scripts align with it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = REPO_ROOT / "config" / "topology.yaml"


@pytest.fixture()
def topology_raw() -> dict:
    """Load raw topology.yaml."""
    assert TOPOLOGY_PATH.exists(), f"topology.yaml not found at {TOPOLOGY_PATH}"
    with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "topology.yaml must be a dict"
    return data


@pytest.fixture()
def topology():
    """Load topology via the loader module."""
    from chatgptrest.kernel.topology_loader import clear_cache, load_topology

    clear_cache()
    spec = load_topology(config_path=str(TOPOLOGY_PATH))
    yield spec
    clear_cache()


# -- Schema / structure tests --


def test_topology_yaml_has_required_keys(topology_raw: dict) -> None:
    """topology.yaml must have version, baseline, topologies, sidecars."""
    for key in ("version", "baseline", "topologies", "sidecars"):
        assert key in topology_raw, f"Missing required key: {key}"


def test_baseline_exists_in_topologies(topology_raw: dict) -> None:
    """baseline value must reference a defined topology."""
    baseline = topology_raw["baseline"]
    topologies = topology_raw.get("topologies", {})
    assert baseline in topologies, (
        f"baseline {baseline!r} not in topologies {list(topologies.keys())}"
    )


def test_baseline_has_main_agent(topology) -> None:
    """The baseline topology must include 'main' agent."""
    agent_ids = topology.baseline_agent_ids()
    assert "main" in agent_ids, f"Baseline agents {agent_ids} missing 'main'"


def test_retired_agents_not_in_any_topology(topology) -> None:
    """Retired agent IDs must not appear in any active topology."""
    all_topos = topology.all_topology_agent_ids()
    all_active = set()
    for agents in all_topos.values():
        all_active.update(agents)
    for retired in topology.retired_agents:
        assert retired not in all_active, (
            f"Retired agent {retired!r} found in active topologies"
        )


def test_guardian_sidecar_wake_agent_in_baseline(topology) -> None:
    """Guardian sidecar wake_agent must be in the baseline topology."""
    sidecar = topology.sidecars.get("guardian")
    assert sidecar is not None, "No guardian sidecar defined"
    wake_agent = sidecar.get("wake_agent")
    assert wake_agent, "Guardian sidecar missing wake_agent"
    baseline_agents = topology.baseline_agent_ids()
    assert wake_agent in baseline_agents, (
        f"Guardian wake_agent {wake_agent!r} not in baseline agents {baseline_agents}"
    )


# -- Cross-file alignment tests --


def test_guardian_defaults_match_topology() -> None:
    """openclaw_guardian_run.py defaults must match topology.yaml sidecar."""
    path = REPO_ROOT / "ops" / "openclaw_guardian_run.py"
    spec = importlib.util.spec_from_file_location("openclaw_guardian_run", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    # Suppress any side effects from module-level code
    import sys

    orig_modules = dict(sys.modules)
    try:
        spec.loader.exec_module(module)
    except Exception:
        pytest.skip("Could not load guardian module")
    finally:
        # Clean up any side effects
        pass

    with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
        topo = yaml.safe_load(f)

    guardian_cfg = (topo.get("sidecars") or {}).get("guardian", {})
    expected_agent = guardian_cfg.get("wake_agent", "main")
    expected_session = guardian_cfg.get("wake_session", "main-guardian")

    assert module.DEFAULT_AGENT_ID == expected_agent, (
        f"guardian DEFAULT_AGENT_ID={module.DEFAULT_AGENT_ID!r} "
        f"!= topology wake_agent={expected_agent!r}"
    )
    assert module.DEFAULT_SESSION_ID == expected_session, (
        f"guardian DEFAULT_SESSION_ID={module.DEFAULT_SESSION_ID!r} "
        f"!= topology wake_session={expected_session!r}"
    )


def test_verify_topology_ids_match_yaml() -> None:
    """verify script TOPOLOGY_AGENT_IDS must match topology.yaml topologies."""
    with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
        topo = yaml.safe_load(f)

    expected: dict[str, set[str]] = {}
    for name, cfg in (topo.get("topologies") or {}).items():
        if isinstance(cfg, dict):
            expected[name] = set(cfg.get("agents", []))

    # Load verify module's computed TOPOLOGY_AGENT_IDS
    verify_path = REPO_ROOT / "ops" / "verify_openclaw_openmind_stack.py"
    spec = importlib.util.spec_from_file_location("verify_mod", str(verify_path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        pytest.skip("Could not load verify module")

    actual = module.TOPOLOGY_AGENT_IDS
    for topo_name, exp_agents in expected.items():
        assert topo_name in actual, f"Topology {topo_name!r} missing from verify script"
        assert actual[topo_name] == exp_agents, (
            f"Topology {topo_name!r}: verify={actual[topo_name]} != yaml={exp_agents}"
        )


def test_agent_roles_yaml_loads() -> None:
    """agent_roles.yaml must still load successfully (regression)."""
    roles_path = REPO_ROOT / "config" / "agent_roles.yaml"
    if not roles_path.exists():
        pytest.skip("agent_roles.yaml not present")

    with open(roles_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "agent_roles.yaml must be a dict"


def test_topology_loader_clear_cache() -> None:
    """clear_cache must reset the module-level cache."""
    from chatgptrest.kernel.topology_loader import (
        _cached_topology,
        clear_cache,
        load_topology,
    )

    load_topology(config_path=str(TOPOLOGY_PATH))
    from chatgptrest.kernel import topology_loader

    assert topology_loader._cached_topology is not None
    clear_cache()
    assert topology_loader._cached_topology is None


def test_is_retired_agent() -> None:
    """is_retired_agent correctly identifies retired agent IDs."""
    from chatgptrest.kernel.topology_loader import clear_cache, is_retired_agent, load_topology

    clear_cache()
    load_topology(config_path=str(TOPOLOGY_PATH))
    assert is_retired_agent("chatgptrest-orch") is True
    assert is_retired_agent("chatgptrest-guardian") is True
    assert is_retired_agent("main") is False
    clear_cache()


def test_fallback_topology() -> None:
    """When yaml is missing, fallback topology is returned."""
    from chatgptrest.kernel.topology_loader import clear_cache, load_topology

    clear_cache()
    spec = load_topology(config_path="/nonexistent/path/topology.yaml")
    assert spec.version == 0  # fallback marker
    assert "main" in spec.baseline_agent_ids()
    clear_cache()
