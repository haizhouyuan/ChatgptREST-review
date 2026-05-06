"""Tests for 1A Role Pack — memory isolation, identity, and backward compat.

Required scenarios (codex-approved):
  1. cold start empty
  2. role isolation
  3. component identity preserved
  4. dedup merge doesn't lose role
  5. no-role backward compat
"""

from __future__ import annotations

import json
import tempfile

import pytest

from chatgptrest.kernel.memory_manager import (
    MemoryManager,
    MemoryRecord,
    MemorySource,
    MemoryTier,
)
from chatgptrest.kernel.role_context import with_role, get_current_role, get_current_role_name
from chatgptrest.kernel.team_types import RoleSpec
from chatgptrest.kernel.role_loader import load_roles, clear_cache


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mm(tmp_path):
    """Fresh in-memory MemoryManager for each test."""
    db_path = str(tmp_path / "test_memory.db")
    return MemoryManager(db_path=db_path)


def _make_record(category: str = "test", key: str = "", value: dict = None,
                 agent: str = "test_component", role: str = "",
                 confidence: float = 0.8) -> MemoryRecord:
    """Helper to create a MemoryRecord with explicit agent and role."""
    src = {"type": "system", "agent": agent}
    if role:
        src["role"] = role
    return MemoryRecord(
        category=category,
        key=key or f"test:{category}",
        value=value or {"data": f"test_{category}"},
        confidence=confidence,
        source=src,
    )


# ── Test 1: Cold start empty ─────────────────────────────────────

class TestColdStartEmpty:
    """New role should get empty results, not errors."""

    def test_episodic_cold_start(self, mm):
        """Querying role_id=devops with no records returns empty list."""
        result = mm.get_episodic(role_id="devops")
        assert result == []

    def test_semantic_cold_start(self, mm):
        """Querying role_id=research with no records returns empty list."""
        result = mm.get_semantic(role_id="research")
        assert result == []


# ── Test 2: Role isolation ───────────────────────────────────────

class TestRoleIsolation:
    """Records with role=devops should not appear in role=research queries."""

    def test_role_write_and_read(self, mm):
        """Records written with role=devops are retrievable with role_id=devops."""
        rec = _make_record(category="execution_feedback", agent="advisor", role="devops")
        mm.stage_and_promote(rec, MemoryTier.EPISODIC, "test")

        devops_results = mm.get_episodic(role_id="devops")
        assert len(devops_results) == 1
        src = json.loads(devops_results[0].source) if isinstance(devops_results[0].source, str) else devops_results[0].source
        assert src.get("role") == "devops"

    def test_cross_role_isolation(self, mm):
        """Records with role=devops are NOT returned when querying role_id=research."""
        rec = _make_record(category="execution_feedback", agent="advisor", role="devops")
        mm.stage_and_promote(rec, MemoryTier.EPISODIC, "test")

        research_results = mm.get_episodic(role_id="research")
        assert len(research_results) == 0

    def test_both_roles_independent(self, mm):
        """Each role sees only its own records."""
        rec_d = _make_record(category="ops_feedback", agent="openclaw", role="devops",
                             key="devops:ops1", value={"data": "devops_data"})
        rec_r = _make_record(category="research_result", agent="advisor", role="research",
                             key="research:res1", value={"data": "research_data"})

        mm.stage_and_promote(rec_d, MemoryTier.EPISODIC, "test")
        mm.stage_and_promote(rec_r, MemoryTier.EPISODIC, "test")

        assert len(mm.get_episodic(role_id="devops")) == 1
        assert len(mm.get_episodic(role_id="research")) == 1


# ── Test 3: Component identity preserved ─────────────────────────

class TestComponentIdentityPreserved:
    """source.agent must remain the component name, never overwritten by role."""

    def test_agent_and_role_coexist(self, mm):
        """Both source.agent and source.role are set correctly."""
        rec = _make_record(agent="advisor", role="devops")
        rid = mm.stage_and_promote(rec, MemoryTier.EPISODIC, "test")

        results = mm.get_episodic(role_id="devops")
        assert len(results) == 1
        src = json.loads(results[0].source) if isinstance(results[0].source, str) else results[0].source
        assert src["agent"] == "advisor"   # component identity preserved
        assert src["role"] == "devops"     # business role set

    def test_agent_filter_still_works_with_role(self, mm):
        """agent_id and role_id can be used together."""
        rec = _make_record(agent="advisor", role="devops")
        mm.stage_and_promote(rec, MemoryTier.EPISODIC, "test")

        # Both filters match
        assert len(mm.get_episodic(agent_id="advisor", role_id="devops")) == 1
        # Agent mismatch
        assert len(mm.get_episodic(agent_id="openclaw", role_id="devops")) == 0
        # Role mismatch
        assert len(mm.get_episodic(agent_id="advisor", role_id="research")) == 0


# ── Test 4: Dedup merge doesn't lose role ────────────────────────

class TestDedupMergePreservesRole:
    """When dedup triggers an UPDATE, the source (including role) must be updated."""

    def test_dedup_preserves_role_on_merge(self, mm):
        """Second write with same fingerprint should preserve/update role in source."""
        rec1 = _make_record(category="test_dedup", agent="advisor", role="devops",
                            value={"data": "same_content"})
        rid1 = mm.stage_and_promote(rec1, MemoryTier.EPISODIC, "first write")

        # Same content (same fingerprint) → triggers dedup merge
        rec2 = _make_record(category="test_dedup", agent="advisor", role="devops",
                            value={"data": "same_content"})
        rec2.confidence = 0.95  # update confidence
        rid2 = mm.stage_and_promote(rec2, MemoryTier.EPISODIC, "dedup merge")

        # Should be same record (deduped)
        assert rid1 == rid2

        # Role must be preserved after dedup
        results = mm.get_episodic(role_id="devops")
        assert len(results) == 1
        src = json.loads(results[0].source) if isinstance(results[0].source, str) else results[0].source
        assert src.get("role") == "devops"
        assert src.get("agent") == "advisor"

    def test_dedup_updates_role_if_changed(self, mm):
        """If role changes on same-fingerprint record, identity scope should prevent dedup."""
        rec1 = _make_record(category="test_dedup2", agent="advisor", role="",
                            value={"data": "initially_no_role"})
        rid1 = mm.stage_and_promote(rec1, MemoryTier.EPISODIC, "no role initially")

        # Same content but now with role
        rec2 = _make_record(category="test_dedup2", agent="advisor", role="devops",
                            value={"data": "initially_no_role"})
        rid2 = mm.stage_and_promote(rec2, MemoryTier.EPISODIC, "added role")

        assert rid1 != rid2

        results = mm.get_episodic(role_id="devops")
        assert len(results) == 1
        all_results = mm.get_episodic(category="test_dedup2")
        assert len(all_results) == 2


# ── Test 5: No-role backward compat ──────────────────────────────

class TestNoRoleBackwardCompat:
    """Records without role should be visible when no role_id filter is applied."""

    def test_no_role_returns_all(self, mm):
        """Querying without role_id returns records regardless of role."""
        rec_with = _make_record(category="cat1", agent="a", role="devops",
                                key="k1", value={"d": "1"})
        rec_without = _make_record(category="cat2", agent="b", role="",
                                   key="k2", value={"d": "2"})
        mm.stage_and_promote(rec_with, MemoryTier.EPISODIC, "with role")
        mm.stage_and_promote(rec_without, MemoryTier.EPISODIC, "without role")

        # No role filter → both records
        all_results = mm.get_episodic()
        assert len(all_results) == 2

    def test_roleless_records_invisible_to_role_query(self, mm):
        """Records without role are NOT returned when role_id is specified."""
        rec = _make_record(category="legacy", agent="openclaw", role="")
        mm.stage_and_promote(rec, MemoryTier.EPISODIC, "legacy record")

        assert len(mm.get_episodic(role_id="devops")) == 0
        assert len(mm.get_episodic()) == 1


# ── Test 6: contextvars auto-inject ──────────────────────────────

class TestContextVarsAutoInject:
    """stage() should auto-inject source.role from contextvars."""

    def test_auto_inject_from_contextvars(self, mm):
        """When with_role is active, stage() auto-injects source.role."""
        role = RoleSpec(name="devops", memory_namespace="devops")

        rec = MemoryRecord(
            category="auto_inject_test",
            key="auto:1",
            value={"data": "via_contextvars"},
            confidence=0.7,
            source={"type": "system", "agent": "test_component"},
        )

        with with_role(role):
            mm.stage_and_promote(rec, MemoryTier.EPISODIC, "auto inject")

        results = mm.get_episodic(role_id="devops")
        assert len(results) == 1
        src = json.loads(results[0].source) if isinstance(results[0].source, str) else results[0].source
        assert src["role"] == "devops"
        assert src["agent"] == "test_component"

    def test_no_contextvars_no_inject(self, mm):
        """Without with_role, source.role stays empty."""
        rec = MemoryRecord(
            category="no_inject_test",
            key="no:1",
            value={"data": "no_contextvars"},
            confidence=0.7,
            source={"type": "system", "agent": "test_component"},
        )

        mm.stage_and_promote(rec, MemoryTier.EPISODIC, "no inject")

        results = mm.get_episodic()
        assert len(results) == 1
        src = json.loads(results[0].source) if isinstance(results[0].source, str) else results[0].source
        assert src.get("role", "") == ""

    def test_explicit_role_not_overwritten(self, mm):
        """If source already has role set, contextvars should not overwrite it."""
        role = RoleSpec(name="research", memory_namespace="research")

        rec = MemoryRecord(
            category="explicit_role_test",
            key="explicit:1",
            value={"data": "explicit_role"},
            confidence=0.7,
            source={"type": "system", "agent": "advisor", "role": "devops"},
        )

        with with_role(role):
            # Active role is research, but record already has role=devops
            mm.stage_and_promote(rec, MemoryTier.EPISODIC, "explicit role")

        results = mm.get_episodic(role_id="devops")
        assert len(results) == 1  # preserved original role


# ── Test 7: RoleSpec and loader ──────────────────────────────────

class TestRoleSpecAndLoader:
    """RoleSpec has the new fields and loader can parse YAML."""

    def test_rolespec_new_fields(self):
        """RoleSpec should have memory_namespace and kb_scope_tags."""
        role = RoleSpec(
            name="devops",
            memory_namespace="devops",
            kb_scope_tags=["chatgptrest", "ops"],
        )
        assert role.memory_namespace == "devops"
        assert role.kb_scope_tags == ["chatgptrest", "ops"]
        d = role.to_dict()
        assert d["memory_namespace"] == "devops"
        assert d["kb_scope_tags"] == ["chatgptrest", "ops"]

    def test_rolespec_from_dict(self):
        """RoleSpec.from_dict handles the new fields."""
        data = {
            "name": "research",
            "memory_namespace": "research",
            "kb_scope_tags": ["finagent"],
        }
        role = RoleSpec.from_dict(data)
        assert role.memory_namespace == "research"
        assert role.kb_scope_tags == ["finagent"]

    def test_rolespec_backward_compat(self):
        """RoleSpec.from_dict with old-style dict (no new fields) still works."""
        data = {"name": "legacy", "model": "haiku"}
        role = RoleSpec.from_dict(data)
        assert role.memory_namespace == ""
        assert role.kb_scope_tags == []

    def test_load_roles_from_yaml(self, tmp_path):
        """load_roles can parse a YAML config file."""
        yaml_content = """
roles:
  testdev:
    description: "Test devops"
    memory_namespace: testdev
    kb_scope_tags: [ops]
"""
        config = tmp_path / "test_roles.yaml"
        config.write_text(yaml_content)
        clear_cache()

        roles = load_roles(config_path=str(config))
        assert "testdev" in roles
        assert roles["testdev"].memory_namespace == "testdev"
        assert roles["testdev"].kb_scope_tags == ["ops"]


# ── Test 8: MemorySource dataclass ───────────────────────────────

class TestMemorySourceDataclass:
    """MemorySource should preserve identity dimensions with safe defaults."""

    def test_memorysource_role_field(self):
        src = MemorySource(agent="advisor", role="devops")
        assert src.role == "devops"
        assert src.agent == "advisor"
        d = src.to_dict()
        assert d["role"] == "devops"
        assert d["agent"] == "advisor"

    def test_memorysource_default_role_empty(self):
        src = MemorySource(agent="advisor")
        assert src.role == ""
        assert src.account_id == ""
        assert src.thread_id == ""

    def test_memorysource_backward_compat(self):
        """Creating MemorySource without role (positional args) still works."""
        src = MemorySource(type="system", agent="test")
        assert src.role == ""
        assert src.agent == "test"

    def test_memorysource_account_and_thread_fields(self):
        src = MemorySource(agent="openclaw", role="devops", account_id="acct-1", thread_id="thr-1")
        d = src.to_dict()
        assert d["account_id"] == "acct-1"
        assert d["thread_id"] == "thr-1"
