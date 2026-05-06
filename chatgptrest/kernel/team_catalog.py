"""Team catalog loading for Codex/OpenClaw team runtime.

Loads:
  - role catalog (`config/codex_subagents.yaml`)
  - topology catalog (`config/team_topologies.yaml`)
  - gate catalog (`config/team_gates.yaml`)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.kernel.team_types import RoleSpec, TeamSpec

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - repo already depends on PyYAML elsewhere
        raise RuntimeError("PyYAML is required for team catalog loading") from exc
    with path.open("r", encoding="utf-8") as f:
        parsed = yaml.safe_load(f) or {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class CatalogRole:
    role_id: str
    description: str = ""
    prompt: str = ""
    runtime: str = "codex_subagent"
    agent_type: str = "default"
    model: str = "sonnet"
    tools: list[str] = field(default_factory=list)
    write_access: str = ""
    output_schema: str = ""
    memory_namespace: str = ""
    kb_scope_tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_role_spec(self) -> RoleSpec:
        return RoleSpec(
            name=self.role_id,
            description=self.description,
            prompt=self.prompt,
            tools=list(self.tools),
            model=self.model,
            memory_namespace=self.memory_namespace or self.role_id,
            kb_scope_tags=list(self.kb_scope_tags),
            runtime=self.runtime,
            agent_type=self.agent_type,
            write_access=self.write_access,
            output_schema=self.output_schema,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dict(cls, role_id: str, data: dict[str, Any]) -> "CatalogRole":
        return cls(
            role_id=str(role_id),
            description=str(data.get("description", "")),
            prompt=str(data.get("prompt", "")),
            runtime=str(data.get("runtime", "codex_subagent") or "codex_subagent"),
            agent_type=str(data.get("agent_type", "default") or "default"),
            model=str(data.get("model", "sonnet") or "sonnet"),
            tools=list(data.get("tools", []) or []),
            write_access=str(data.get("write_access", "")),
            output_schema=str(data.get("output_schema", "")),
            memory_namespace=str(data.get("memory_namespace", "")),
            kb_scope_tags=list(data.get("kb_scope_tags", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class TeamTopology:
    topology_id: str
    description: str = ""
    role_ids: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    execution_mode: str = "parallel"
    synthesis_role: str = ""
    max_concurrent: int = 3
    gate_ids: list[str] = field(default_factory=list)
    output_contract: dict[str, Any] = field(default_factory=dict)
    success_criteria: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, topology_id: str, data: dict[str, Any]) -> "TeamTopology":
        return cls(
            topology_id=str(topology_id),
            description=str(data.get("description", "")),
            role_ids=list(data.get("roles", []) or []),
            task_types=list(data.get("task_types", []) or []),
            execution_mode=str(data.get("execution_mode", "parallel") or "parallel"),
            synthesis_role=str(data.get("synthesis_role", "")),
            max_concurrent=int(data.get("max_concurrent", 3) or 3),
            gate_ids=list(data.get("gate_ids", []) or []),
            output_contract=dict(data.get("output_contract", {}) or {}),
            success_criteria=dict(data.get("success_criteria", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class TeamGate:
    gate_id: str
    description: str = ""
    trigger: str = ""
    threshold: float = 0.0
    roles: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, gate_id: str, data: dict[str, Any]) -> "TeamGate":
        return cls(
            gate_id=str(gate_id),
            description=str(data.get("description", "")),
            trigger=str(data.get("trigger", "")),
            threshold=float(data.get("threshold", 0.0) or 0.0),
            roles=list(data.get("roles", []) or []),
            markers=[str(v) for v in (data.get("markers", []) or [])],
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class TeamCatalogBundle:
    roles: dict[str, CatalogRole] = field(default_factory=dict)
    topologies: dict[str, TeamTopology] = field(default_factory=dict)
    gates: dict[str, TeamGate] = field(default_factory=dict)

    def build_team_spec(self, topology_id: str) -> TeamSpec:
        topology = self.topologies.get(str(topology_id))
        if topology is None:
            return TeamSpec()
        roles: list[RoleSpec] = []
        for role_id in topology.role_ids:
            role = self.roles.get(str(role_id))
            if role is None:
                continue
            roles.append(role.to_role_spec())
        metadata = {
            "topology_id": topology.topology_id,
            "execution_mode": topology.execution_mode,
            "synthesis_role": topology.synthesis_role,
            "max_concurrent": topology.max_concurrent,
            "gate_ids": list(topology.gate_ids),
        }
        metadata.update(dict(topology.metadata))
        return TeamSpec(
            roles=roles,
            output_contract=dict(topology.output_contract),
            success_criteria=dict(topology.success_criteria),
            metadata=metadata,
        )

    def recommend_topology(self, task_type: str) -> TeamTopology | None:
        wanted = str(task_type or "").strip()
        if not wanted:
            return None
        for topology in self.topologies.values():
            if wanted in topology.task_types:
                return topology
        for topology in self.topologies.values():
            if "*" in topology.task_types:
                return topology
        return None

    def gate_defs_for_spec(self, spec: TeamSpec) -> list[TeamGate]:
        gate_ids = list((spec.metadata or {}).get("gate_ids", []) or [])
        return [self.gates[gid] for gid in gate_ids if gid in self.gates]


def load_team_catalog(
    *,
    role_path: str | Path | None = None,
    topology_path: str | Path | None = None,
    gate_path: str | Path | None = None,
) -> TeamCatalogBundle:
    role_file = Path(role_path) if role_path else (_PROJECT_ROOT / "config" / "codex_subagents.yaml")
    topology_file = Path(topology_path) if topology_path else (_PROJECT_ROOT / "config" / "team_topologies.yaml")
    gate_file = Path(gate_path) if gate_path else (_PROJECT_ROOT / "config" / "team_gates.yaml")

    role_doc = _load_yaml(role_file) if role_file.exists() else {}
    topology_doc = _load_yaml(topology_file) if topology_file.exists() else {}
    gate_doc = _load_yaml(gate_file) if gate_file.exists() else {}

    roles = {
        str(role_id): CatalogRole.from_dict(str(role_id), cfg)
        for role_id, cfg in (role_doc.get("roles", {}) or {}).items()
        if isinstance(cfg, dict)
    }
    topologies = {
        str(topology_id): TeamTopology.from_dict(str(topology_id), cfg)
        for topology_id, cfg in (topology_doc.get("topologies", {}) or {}).items()
        if isinstance(cfg, dict)
    }
    gates = {
        str(gate_id): TeamGate.from_dict(str(gate_id), cfg)
        for gate_id, cfg in (gate_doc.get("gates", {}) or {}).items()
        if isinstance(cfg, dict)
    }
    return TeamCatalogBundle(roles=roles, topologies=topologies, gates=gates)
