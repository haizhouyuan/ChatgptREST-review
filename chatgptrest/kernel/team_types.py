"""Team types — validated data contracts for agent team dispatch.

Replaces the opaque ``dict[str, dict]`` team payload with structured,
validated types that enable team-level learning and scorecard tracking.

Key types:
  - RoleSpec: definition of a single role within a team
  - TeamSpec: complete team composition with deterministic team_id
  - TeamRunRecord: per-execution record linking spec → task → result
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class RoleSpec:
    """Definition of a single role within an agent team.

    Attributes:
        name: Short identifier for the role (e.g. "reviewer", "devops").
        description: Human-readable description of what this role does.
        prompt: System prompt or instruction text for the role.
        tools: List of allowed tool names. Empty means "all tools".
        model: Model alias or full name (e.g. "sonnet", "claude-3-5-sonnet").
        memory_namespace: Role namespace for memory isolation (maps to source.role).
        kb_scope_tags: Soft-hint tags for KB scoping (used by ContextResolver).
        runtime: Runtime hint for this role (codex_subagent/openclaw_session/etc).
        agent_type: Runtime-specific subtype (explorer/default/worker/etc).
        write_access: Human-readable write policy hint.
        output_schema: Named output contract for the role.
        metadata: Extra runtime metadata retained by the team control plane.
    """
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "sonnet"
    memory_namespace: str = ""
    kb_scope_tags: list[str] = field(default_factory=list)
    runtime: str = ""
    agent_type: str = ""
    write_access: str = ""
    output_schema: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoleSpec":
        """Create a RoleSpec from a dict. Extra keys are ignored."""
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            prompt=str(data.get("prompt", "")),
            tools=list(data.get("tools", [])),
            model=str(data.get("model", "sonnet")),
            memory_namespace=str(data.get("memory_namespace", "")),
            kb_scope_tags=list(data.get("kb_scope_tags", [])),
            runtime=str(data.get("runtime", "")),
            agent_type=str(data.get("agent_type", "")),
            write_access=str(data.get("write_access", "")),
            output_schema=str(data.get("output_schema", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )


def _compute_team_id(roles: list[RoleSpec]) -> str:
    """Compute a deterministic team_id from role definitions.

    The hash is based on sorted (name, model) pairs so that:
    - Same set of roles → same team_id regardless of list order
    - Different roles/models → different team_id
    """
    parts = sorted(f"{r.name}:{r.model}" for r in roles)
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class TeamSpec:
    """Validated team composition.

    The ``team_id`` is deterministic: the same set of roles produces the
    same hash, enabling scorecard aggregation across runs.

    Attributes:
        team_id: Deterministic hash computed from roles. Auto-set if empty.
        roles: List of role definitions.
        output_contract: Optional dict describing expected output shape.
        success_criteria: Optional dict defining pass/fail conditions.
        metadata: Runtime metadata like topology_id/execution_mode/gates.
    """
    roles: list[RoleSpec] = field(default_factory=list)
    team_id: str = ""
    output_contract: dict[str, Any] = field(default_factory=dict)
    success_criteria: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.team_id and self.roles:
            self.team_id = _compute_team_id(self.roles)

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "roles": [r.to_dict() for r in self.roles],
            "output_contract": self.output_contract,
            "success_criteria": self.success_criteria,
            "metadata": self.metadata,
        }

    def to_agents_json(self) -> dict[str, dict]:
        """Convert to the legacy agents_json format for backward compat.

        Returns a dict mapping role name → role config, which is what
        the CC CLI ``--agents`` flag expects.
        """
        result: dict[str, dict] = {}
        for role in self.roles:
            entry: dict[str, Any] = {
                "description": role.description,
                "prompt": role.prompt,
                "model": role.model,
            }
            if role.tools:  # only include tools if non-empty
                entry["tools"] = role.tools
            result[role.name] = entry
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeamSpec":
        """Create a TeamSpec from a dict.

        Supports two formats:
        1. Full format: {"roles": [...], "team_id": "...", "output_contract": ...}
        2. Legacy format: {"role_name": {"description": ..., "model": ...}, ...}
           (auto-detects when keys are not known TeamSpec fields)
        """
        _known_keys = {"roles", "team_id", "output_contract", "success_criteria", "metadata"}

        if isinstance(data.get("roles"), list):
            # Full format
            roles = [RoleSpec.from_dict(r) for r in data["roles"]]
            return cls(
                roles=roles,
                team_id=data.get("team_id", ""),
                output_contract=data.get("output_contract", {}),
                success_criteria=data.get("success_criteria", {}),
                metadata=dict(data.get("metadata", {}) or {}),
            )

        # Legacy format: treat each key as a role name
        if data and not data.keys() <= _known_keys:
            roles = []
            for name, cfg in data.items():
                if isinstance(cfg, dict):
                    cfg_copy = dict(cfg)
                    cfg_copy["name"] = name
                    roles.append(RoleSpec.from_dict(cfg_copy))
            return cls(roles=roles)

        # Fallback: empty TeamSpec
        return cls()


@dataclass
class TeamRunRecord:
    """Per-execution record linking team spec to task result.

    Created at dispatch entry, completed after execution. Used to
    feed the scorecard aggregation layer.

    Attributes:
        team_run_id: Unique UUID for this run.
        team_spec: The TeamSpec used.
        trace_id: Link to the broader execution trace.
        task_type: Task type dispatched.
        repo: Repository context (if known).
        started_at: Unix timestamp of dispatch start.
        completed_at: Unix timestamp of dispatch end (0 if not yet complete).
        result_ok: Whether the execution succeeded.
        elapsed_seconds: Total wall-clock time.
        quality_score: Quality score from result evaluation.
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens consumed.
        cost_usd: Total cost in USD.
        role_outcomes: Per-role outcome dict: {role_name: {ok, latency, ...}}.
    """
    team_run_id: str = ""
    team_spec: TeamSpec | None = None
    trace_id: str = ""
    task_type: str = ""
    repo: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    result_ok: bool = False
    elapsed_seconds: float = 0.0
    quality_score: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cost_usd: float = 0.0
    role_outcomes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.team_run_id:
            self.team_run_id = f"trun_{uuid.uuid4().hex[:12]}"
        if self.started_at == 0.0:
            self.started_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.team_spec:
            d["team_spec"] = self.team_spec.to_dict()
        return d
