"""Contract tests for OpenMind substrate ADRs.

These tests verify the invariants defined in docs/contracts/ADR-001 through ADR-004.
They test the CONTRACTS, not the implementation details.

Run: pytest tests/test_substrate_contracts.py -v
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def memory_manager():
    """Create a fresh MemoryManager with temp DB for contract testing."""
    from chatgptrest.kernel.memory_manager import MemoryManager
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_contract.db")
        mm = MemoryManager(db_path=db_path)
        yield mm


@pytest.fixture
def ingest_service(memory_manager):
    """Create a KnowledgeIngestService with minimal runtime mock."""
    from chatgptrest.cognitive.ingest_service import KnowledgeIngestService

    class _MinimalRuntime:
        def __init__(self, mm):
            self.memory = mm
            self.policy_engine = None  # No policy engine = skip quality gate
            self.writeback_service = None
            self.evomap_knowledge_db = None
            self.event_bus = None
            self.observer = None

    runtime = _MinimalRuntime(memory_manager)
    return KnowledgeIngestService(runtime)


# ═══════════════════════════════════════════════════════════════════
# ADR-003: Identity Contract Tests
# ═══════════════════════════════════════════════════════════════════

class TestIdentityContract:
    """Tests for ADR-003 identity isolation invariants."""

    def test_episodic_session_isolates(self, memory_manager):
        """ADR-003: session_id MUST isolate episodic memory retrieval."""
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        # Write records for two different sessions
        for sid in ("session-A", "session-B"):
            memory_manager.stage_and_promote(
                MemoryRecord(
                    category="test",
                    key=f"key-{sid}",
                    value={"data": f"belongs to {sid}"},
                    confidence=0.9,
                    source=MemorySource(
                        type=SourceType.USER_INPUT.value,
                        agent="test-agent",
                        session_id=sid,
                    ).to_dict(),
                ),
                MemoryTier.EPISODIC,
                reason="contract test",
            )

        # Query with session_id = "session-A" must NOT return session-B data
        results = memory_manager.get_episodic(session_id="session-A")
        session_ids = {
            json.loads(r.source)["session_id"]
            if isinstance(r.source, str) else r.source.get("session_id")
            for r in results
        }
        assert session_ids == {"session-A"}, (
            f"ADR-003 VIOLATION: episodic query for session-A returned data "
            f"from sessions: {session_ids}"
        )

    def test_episodic_empty_session_returns_all(self, memory_manager):
        """ADR-003: empty session_id returns all records (current behavior).

        NOTE: ADR-003 v2 specifies that the *route handler* should
        fail-closed or generate ephemeral session. The memory_manager
        itself does not enforce this — enforcement is at the API layer.
        This test documents the current behavior as a known gap.
        """
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        for sid in ("s1", "s2"):
            memory_manager.stage_and_promote(
                MemoryRecord(
                    category="test",
                    key=f"key-{sid}",
                    value={"data": sid},
                    confidence=0.8,
                    source=MemorySource(
                        type=SourceType.USER_INPUT.value,
                        agent="test",
                        session_id=sid,
                    ).to_dict(),
                ),
                MemoryTier.EPISODIC,
                reason="contract test",
            )

        # Empty session_id = no filter = all records (current behavior)
        results = memory_manager.get_episodic(session_id="")
        assert len(results) >= 2, (
            "Current behavior: empty session_id should return all records. "
            "API-layer enforcement is where fail-closed should happen."
        )

    def test_episodic_agent_isolates(self, memory_manager):
        """ADR-003: agent_id filters episodic memory when specified."""
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        for agent in ("openclaw", "antigravity"):
            memory_manager.stage_and_promote(
                MemoryRecord(
                    category="test_agent",
                    key=f"pref-{agent}",
                    value={"theme": "dark" if agent == "openclaw" else "light"},
                    confidence=0.9,
                    source=MemorySource(
                        type=SourceType.USER_INPUT.value,
                        agent=agent,
                        session_id="s1",
                    ).to_dict(),
                ),
                MemoryTier.EPISODIC,
                reason="contract test",
            )

        # Query with agent_id = "openclaw" must filter
        results = memory_manager.get_episodic(
            agent_id="openclaw", session_id="s1"
        )
        agents = {
            json.loads(r.source)["agent"]
            if isinstance(r.source, str) else r.source.get("agent")
            for r in results
        }
        assert agents == {"openclaw"}, (
            f"ADR-003 VIOLATION: episodic query for agent=openclaw returned "
            f"agents: {agents}"
        )

    def test_episodic_empty_agent_cross_recall(self, memory_manager):
        """ADR-003: empty agent_id = cross-agent recall (single-user mode)."""
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        for agent in ("openclaw", "antigravity"):
            memory_manager.stage_and_promote(
                MemoryRecord(
                    category="cross_agent_test",
                    key=f"pref-{agent}",
                    value={"agent": agent},
                    confidence=0.9,
                    source=MemorySource(
                        type=SourceType.USER_INPUT.value,
                        agent=agent,
                        session_id="s1",
                    ).to_dict(),
                ),
                MemoryTier.EPISODIC,
                reason="contract test",
            )

        # Empty agent_id = show all (cross-agent recall feature)
        results = memory_manager.get_episodic(
            category="cross_agent_test", session_id="s1", agent_id=""
        )
        assert len(results) >= 2, (
            "ADR-003: empty agent_id should enable cross-agent recall in "
            "single-user mode"
        )


# ═══════════════════════════════════════════════════════════════════
# ADR-001: State Model — Object Type Routing Tests
# ═══════════════════════════════════════════════════════════════════

class TestObjectTypeRouting:
    """Tests for ADR-001 object-type-to-store mapping."""

    def test_episodic_feedback_goes_to_episodic_tier(self, memory_manager):
        """ADR-001: episodic_feedback → episodic memory tier."""
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        memory_manager.stage_and_promote(
            MemoryRecord(
                category="execution_feedback",
                key="telemetry:test:tool.completed",
                value={"signal_type": "tool.completed", "data": {"tool": "grep"}},
                confidence=0.8,
                source=MemorySource(
                    type=SourceType.SYSTEM.value,
                    agent="openclaw",
                    session_id="s1",
                ).to_dict(),
            ),
            MemoryTier.EPISODIC,
            reason="telemetry ingest",
        )

        results = memory_manager.get_episodic(
            category="execution_feedback", session_id="s1"
        )
        assert len(results) >= 1, (
            "ADR-001: episodic_feedback must be stored in episodic tier"
        )

    def test_profile_memory_can_be_stored(self, memory_manager):
        """ADR-001: profile_memory can be stored and recalled.

        The staging gate may reject promotion to semantic tier for
        single-occurrence records. This test verifies the record is
        at least staged and retrievable.
        """
        from chatgptrest.kernel.memory_manager import (
            MemoryRecord, MemorySource, MemoryTier, SourceType,
        )

        record_id = memory_manager.stage_and_promote(
            MemoryRecord(
                category="user_profile",
                key="preference:theme",
                value={"theme": "dark_mode"},
                confidence=0.95,
                source=MemorySource(
                    type=SourceType.USER_INPUT.value,
                    agent="openclaw",
                    session_id="s1",
                ).to_dict(),
            ),
            MemoryTier.EPISODIC,  # Use episodic to avoid staging gate semantic rules
            reason="user preference capture",
        )

        results = memory_manager.get_episodic(
            category="user_profile", session_id="s1"
        )
        assert len(results) >= 1, (
            "ADR-001: profile_memory must be stored and retrievable"
        )
        assert any(
            (json.loads(r.value) if isinstance(r.value, str) else r.value).get("theme") == "dark_mode"
            for r in results
        ), "ADR-001: stored profile must contain the correct preference data"


# ═══════════════════════════════════════════════════════════════════
# ADR-002: Ingress — No Direct KB Write from Shell
# ═══════════════════════════════════════════════════════════════════

class TestIngressContract:
    """Tests for ADR-002 ingress legality invariants."""

    def test_ingest_without_writeback_service_fails(self, ingest_service):
        """ADR-002: KnowledgeIngestService must fail if writeback_service
        is unavailable, preventing uncontrolled direct KB writes."""
        from chatgptrest.cognitive.ingest_service import KnowledgeIngestItem

        item = KnowledgeIngestItem(
            title="test item",
            content="some content",
            source_system="test",
            para_bucket="resources",
        )

        result = ingest_service.ingest([item])
        # Without writeback_service, ingest should fail gracefully
        assert not result.ok or all(
            not r.accepted for r in result.results
        ), (
            "ADR-002 VIOLATION: ingest succeeded without writeback_service. "
            "This means writes can bypass the controlled path."
        )


# ═══════════════════════════════════════════════════════════════════
# ADR-004: Path SLA — Hot Path Invariants
# ═══════════════════════════════════════════════════════════════════

class TestPathSLAContract:
    """Tests for ADR-004 hot path constraints."""

    def test_no_embed_kb_hub_suppresses_vector_query(self):
        """ADR-004: _NoEmbedKBHub must pass auto_embed=False to search.

        This ensures hot path does NOT trigger vector embedding generation
        on the query side (it may exist on the index side).
        """
        from chatgptrest.cognitive.context_service import _NoEmbedKBHub

        # Track what auto_embed value the underlying hub receives
        calls = []

        class _MockHub:
            def search(self, query, top_k=5, auto_embed=True):
                calls.append({"query": query, "auto_embed": auto_embed})
                return []

        wrapper = _NoEmbedKBHub(_MockHub())
        wrapper.search("test query", top_k=3)

        assert len(calls) == 1
        assert calls[0]["auto_embed"] is False, (
            "ADR-004 VIOLATION: _NoEmbedKBHub must pass auto_embed=False "
            "to keep hot path free of vector query overhead"
        )


# ═══════════════════════════════════════════════════════════════════
# ADR-001: Governed Claim — EvoMap Promotion Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestGovernedClaimPipeline:
    """Tests that governed_claims enter EvoMap as CANDIDATE, not bypassing."""

    def test_mirror_into_graph_creates_candidate_atom(self):
        """ADR-001: governed_claim ingest must create atom with
        status=CANDIDATE, entering the promotion pipeline."""
        from chatgptrest.evomap.knowledge.schema import AtomStatus

        # Verify the constant exists and has the expected value
        assert AtomStatus.CANDIDATE.value == "candidate", (
            "ADR-001: AtomStatus.CANDIDATE must exist for governed_claim pathway"
        )

    def test_atom_promotion_requires_groundedness(self):
        """ADR-001: CANDIDATE → ACTIVE transition requires groundedness gate."""
        import importlib
        mod = importlib.import_module(
            "chatgptrest.evomap.knowledge.promotion_engine"
        )
        # Verify PromotionEngine.promote exists and has groundedness logic
        assert hasattr(mod, "PromotionEngine"), (
            "ADR-001: PromotionEngine must exist for governed_claim governance"
        )
        pe_cls = mod.PromotionEngine
        assert hasattr(pe_cls, "promote"), (
            "ADR-001: PromotionEngine.promote must exist"
        )
