"""Tests for chatgptrest/kernel/team_types.py — TeamSpec contracts."""

import pytest
from chatgptrest.kernel.team_types import RoleSpec, TeamSpec, TeamRunRecord


# ── RoleSpec ──────────────────────────────────────────────────────

class TestRoleSpec:
    def test_basic_creation(self):
        r = RoleSpec(name="reviewer", description="Reviews code")
        assert r.name == "reviewer"
        assert r.model == "sonnet"  # default
        assert r.tools == []

    def test_from_dict(self):
        r = RoleSpec.from_dict({
            "name": "architect",
            "description": "System design",
            "model": "opus",
            "tools": ["read_file", "grep"],
        })
        assert r.name == "architect"
        assert r.model == "opus"
        assert r.tools == ["read_file", "grep"]

    def test_roundtrip(self):
        r = RoleSpec(name="coder", model="sonnet", tools=["bash"])
        d = r.to_dict()
        r2 = RoleSpec.from_dict(d)
        assert r2.name == r.name
        assert r2.model == r.model
        assert r2.tools == r.tools

    def test_runtime_metadata_fields(self):
        r = RoleSpec.from_dict({
            "name": "implementer",
            "runtime": "codex_subagent",
            "agent_type": "worker",
            "write_access": "scoped",
            "output_schema": "implementation_report_v1",
            "metadata": {"lane": "writer"},
        })
        assert r.runtime == "codex_subagent"
        assert r.agent_type == "worker"
        assert r.write_access == "scoped"
        assert r.output_schema == "implementation_report_v1"
        assert r.metadata["lane"] == "writer"


# ── TeamSpec ──────────────────────────────────────────────────────

class TestTeamSpec:
    def test_deterministic_team_id(self):
        roles = [
            RoleSpec(name="reviewer", model="sonnet"),
            RoleSpec(name="architect", model="opus"),
        ]
        t1 = TeamSpec(roles=roles)
        t2 = TeamSpec(roles=list(reversed(roles)))
        # Same roles (different order) → same team_id
        assert t1.team_id == t2.team_id
        assert len(t1.team_id) == 16

    def test_different_roles_different_id(self):
        t1 = TeamSpec(roles=[RoleSpec(name="a", model="sonnet")])
        t2 = TeamSpec(roles=[RoleSpec(name="b", model="sonnet")])
        assert t1.team_id != t2.team_id

    def test_from_dict_full_format(self):
        data = {
            "roles": [
                {"name": "lead", "model": "opus"},
                {"name": "reviewer", "model": "sonnet"},
            ],
            "output_contract": {"type": "review"},
        }
        spec = TeamSpec.from_dict(data)
        assert len(spec.roles) == 2
        assert spec.roles[0].name == "lead"
        assert spec.output_contract == {"type": "review"}
        assert spec.team_id  # auto-computed

    def test_from_dict_legacy_format(self):
        """Legacy format: {"role_name": {"model": "...", "description": "..."}}"""
        data = {
            "reviewer": {"description": "Reviews code", "model": "sonnet"},
            "architect": {"description": "Designs", "model": "opus"},
        }
        spec = TeamSpec.from_dict(data)
        assert len(spec.roles) == 2
        role_names = {r.name for r in spec.roles}
        assert "reviewer" in role_names
        assert "architect" in role_names

    def test_to_agents_json(self):
        spec = TeamSpec(roles=[
            RoleSpec(name="lead", model="opus", prompt="Lead the team"),
            RoleSpec(name="coder", model="sonnet", tools=["bash"]),
        ])
        aj = spec.to_agents_json()
        assert "lead" in aj
        assert aj["lead"]["model"] == "opus"
        assert aj["coder"]["tools"] == ["bash"]

    def test_empty_spec(self):
        spec = TeamSpec()
        assert spec.team_id == ""
        assert spec.roles == []

    def test_roundtrip(self):
        spec = TeamSpec(roles=[
            RoleSpec(name="agent", model="sonnet"),
        ], output_contract={"format": "json"}, metadata={"topology_id": "review_triad"})
        d = spec.to_dict()
        spec2 = TeamSpec.from_dict(d)
        assert spec2.team_id == spec.team_id
        assert len(spec2.roles) == 1
        assert spec2.metadata["topology_id"] == "review_triad"


# ── TeamRunRecord ─────────────────────────────────────────────────

class TestTeamRunRecord:
    def test_auto_fields(self):
        r = TeamRunRecord()
        assert r.team_run_id.startswith("trun_")
        assert r.started_at > 0

    def test_with_spec(self):
        spec = TeamSpec(roles=[RoleSpec(name="r", model="sonnet")])
        r = TeamRunRecord(team_spec=spec, trace_id="tr_001", task_type="review")
        assert r.team_spec.team_id == spec.team_id
        assert r.trace_id == "tr_001"

    def test_to_dict(self):
        spec = TeamSpec(roles=[RoleSpec(name="r", model="sonnet")])
        r = TeamRunRecord(team_spec=spec, result_ok=True, cost_usd=0.05)
        d = r.to_dict()
        assert d["result_ok"] is True
        assert d["cost_usd"] == 0.05
        assert "team_id" in d["team_spec"]
