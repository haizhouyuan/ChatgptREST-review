"""Tests for chatgptrest.kernel — ArtifactStore, PolicyEngine, EventBus."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from chatgptrest.kernel.artifact_store import ArtifactStore, Artifact
from chatgptrest.kernel.policy_engine import PolicyEngine, QualityContext
from chatgptrest.kernel.event_bus import EventBus, TraceEvent


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def artifact_store(tmp_dir):
    store = ArtifactStore(
        base_dir=tmp_dir / "artifacts",
        db_path=tmp_dir / "artifacts.db",
    )
    yield store
    store.close()


@pytest.fixture
def event_bus(tmp_dir):
    bus = EventBus(db_path=tmp_dir / "events.db")
    yield bus
    bus.close()


@pytest.fixture
def event_bus_memory():
    """EventBus without persistence (in-memory only)."""
    return EventBus(db_path=None)


@pytest.fixture
def policy_engine():
    return PolicyEngine()


# ══════════════════════════════════════════════════════════════════
# ArtifactStore tests
# ══════════════════════════════════════════════════════════════════


class TestArtifactStore:

    def test_store_and_get(self, artifact_store):
        content = "# Research Results\n\nSome findings."
        art = artifact_store.store(
            content, task_id="t1", step_id="s1", producer="test",
        )
        assert art.artifact_id
        assert art.content_type == "text/markdown"
        assert art.task_id == "t1"
        assert art.producer == "test"

        retrieved = artifact_store.get(art.artifact_id)
        assert retrieved is not None
        assert retrieved.artifact_id == art.artifact_id

    def test_content_addressable(self, artifact_store):
        """Same content → same artifact_id (dedup)."""
        content = "identical content"
        a1 = artifact_store.store(content, task_id="t1", step_id="s1", producer="p1")
        a2 = artifact_store.store(content, task_id="t2", step_id="s2", producer="p2")
        assert a1.artifact_id == a2.artifact_id

    def test_different_content_different_id(self, artifact_store):
        a1 = artifact_store.store("content A", task_id="t1", step_id="s1", producer="p1")
        a2 = artifact_store.store("content B", task_id="t1", step_id="s1", producer="p1")
        assert a1.artifact_id != a2.artifact_id

    def test_get_content_and_verify(self, artifact_store):
        content = "verify me please"
        art = artifact_store.store(content, task_id="t1", step_id="s1", producer="test")
        got = artifact_store.get_content(art.artifact_id)
        assert got == content

    def test_get_nonexistent(self, artifact_store):
        assert artifact_store.get("nonexistent_hash") is None

    def test_get_content_nonexistent(self, artifact_store):
        assert artifact_store.get_content("nonexistent_hash") is None

    def test_list_by_task(self, artifact_store):
        artifact_store.store("doc1", task_id="task_A", step_id="s1", producer="p1")
        artifact_store.store("doc2", task_id="task_A", step_id="s2", producer="p2")
        artifact_store.store("doc3", task_id="task_B", step_id="s1", producer="p1")
        results = artifact_store.list_by_task("task_A")
        assert len(results) == 2
        assert all(r.task_id == "task_A" for r in results)

    def test_provenance_split(self, artifact_store):
        """Same content from different tasks → 1 artifact, 2 productions."""
        content = "shared knowledge"
        artifact_store.store(content, task_id="t1", step_id="s1", producer="p1")
        artifact_store.store(content, task_id="t2", step_id="s2", producer="p2")

        # First writer wins for the artifact row
        art = artifact_store.get(ArtifactStore.compute_id(content))
        assert art is not None

        # Both tasks can find it
        list_t1 = artifact_store.list_by_task("t1")
        list_t2 = artifact_store.list_by_task("t2")
        assert len(list_t1) == 1
        assert len(list_t2) == 1
        assert list_t1[0].artifact_id == list_t2[0].artifact_id

    def test_bytes_content(self, artifact_store):
        content = b"\x89PNG\r\n\x1a\n binary data"
        art = artifact_store.store(
            content, task_id="t1", step_id="s1", producer="img",
            content_type="image/png",
        )
        got = artifact_store.get_content(art.artifact_id)
        assert got == content

    def test_security_label(self, artifact_store):
        art = artifact_store.store(
            "secret", task_id="t1", step_id="s1", producer="p1",
            security_label="confidential",
        )
        assert art.security_label == "confidential"

    def test_evidence_refs(self, artifact_store):
        art = artifact_store.store(
            "with refs", task_id="t1", step_id="s1", producer="p1",
            evidence_refs=["ref1", "ref2"],
        )
        assert art.evidence_refs == ["ref1", "ref2"]
        got = artifact_store.get(art.artifact_id)
        assert got.evidence_refs == ["ref1", "ref2"]

    def test_to_dict_from_dict(self):
        art = Artifact(
            artifact_id="abc123", content_type="text/plain", content_path="/tmp/x",
            task_id="t1", step_id="s1", producer="test",
        )
        d = art.to_dict()
        art2 = Artifact.from_dict(d)
        assert art2.artifact_id == art.artifact_id


# ══════════════════════════════════════════════════════════════════
# PolicyEngine tests
# ══════════════════════════════════════════════════════════════════


class TestPolicyEngine:

    def test_fail_closed_unknown_label(self, policy_engine):
        result = policy_engine.check_security("hello", "top_secret")
        assert not result.allowed
        assert "Unknown label" in result.reason

    def test_allowed_labels(self, policy_engine):
        for label in ("public", "internal", "confidential"):
            result = policy_engine.check_security("safe text", label)
            assert result.allowed, f"Label {label} should be allowed"

    def test_pii_detection_email(self, policy_engine):
        result = policy_engine.check_security("Contact user@example.com", "internal")
        assert not result.allowed
        assert "email" in result.reason

    def test_pii_detection_phone_cn(self, policy_engine):
        result = policy_engine.check_security("Call 13812345678", "internal")
        assert not result.allowed
        assert "phone_cn" in result.reason

    def test_pii_detection_api_key(self, policy_engine):
        result = policy_engine.check_security('api_key = "sk-abc123def456ghi789"', "internal")
        assert not result.allowed
        assert "api_key" in result.reason

    def test_delivery_internal_to_external_blocked(self, policy_engine):
        result = policy_engine.check_delivery_label("internal", "external")
        assert not result.allowed

    def test_delivery_public_to_external_ok(self, policy_engine):
        result = policy_engine.check_delivery_label("public", "external")
        assert result.allowed

    def test_cost_within_budget(self, policy_engine):
        result = policy_engine.check_cost(1000, "default")
        assert result.allowed

    def test_cost_over_budget(self, policy_engine):
        result = policy_engine.check_cost(200_000, "default")
        assert not result.allowed

    def test_execution_failed_always_blocked(self, policy_engine):
        result = policy_engine.check_execution_business(False, True, "internal")
        assert not result.allowed

    def test_business_failed_external_blocked(self, policy_engine):
        result = policy_engine.check_execution_business(True, False, "external")
        assert not result.allowed

    def test_business_failed_internal_allowed(self, policy_engine):
        result = policy_engine.check_execution_business(True, False, "internal")
        assert result.allowed

    def test_claim_evidence_external_no_claims_blocked(self, policy_engine):
        result = policy_engine.check_claim_evidence([], "external", "high")
        assert not result.allowed

    def test_claim_evidence_with_refs_ok(self, policy_engine):
        claims = [{"text": "claim1", "evidence_refs": ["ref1"]}]
        result = policy_engine.check_claim_evidence(claims, "external", "high")
        assert result.allowed

    def test_quality_gate_all_pass(self, policy_engine):
        ctx = QualityContext(
            audience="internal",
            security_label="internal",
            content="Clean text with no sensitive data.",
            estimated_tokens=100,
        )
        result = policy_engine.run_quality_gate(ctx)
        assert result.allowed
        assert len(result.blocked_by) == 0

    def test_quality_gate_security_blocks(self, policy_engine):
        ctx = QualityContext(
            audience="internal",
            security_label="internal",
            content="Contact user@example.com for info",
            estimated_tokens=100,
        )
        result = policy_engine.run_quality_gate(ctx)
        assert not result.allowed
        assert "security" in result.blocked_by

    def test_quality_gate_empty_content_blocks(self, policy_engine):
        ctx = QualityContext(
            audience="internal",
            security_label="internal",
            content="",
        )
        result = policy_engine.run_quality_gate(ctx)
        assert not result.allowed
        assert "structure" in result.blocked_by

    # ── T0.3 fail-closed tests ───────────────────────────────────

    def test_confidential_to_external_blocked(self, policy_engine):
        """Critical: confidential → external MUST be blocked (fail-closed)."""
        result = policy_engine.check_delivery_label("confidential", "external")
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_delivery_unknown_label_blocked(self, policy_engine):
        """Unknown security labels must be blocked (fail-closed)."""
        result = policy_engine.check_delivery_label("top_secret", "internal")
        assert not result.allowed
        assert "fail-closed" in result.reason.lower()

    def test_confidential_to_internal_allowed(self, policy_engine):
        """Confidential → internal should be allowed."""
        result = policy_engine.check_delivery_label("confidential", "internal")
        assert result.allowed


# ══════════════════════════════════════════════════════════════════
# EventBus tests
# ══════════════════════════════════════════════════════════════════


class TestEventBus:

    def test_emit_and_query(self, event_bus):
        event = TraceEvent.create(
            source="advisor", event_type="advisor.route_selected",
            data={"route": "full_funnel"},
        )
        event_bus.emit(event)
        results = event_bus.query(trace_id=event.trace_id)
        assert len(results) == 1
        assert results[0].event_type == "advisor.route_selected"
        assert results[0].data["route"] == "full_funnel"

    def test_subscriber_called(self, event_bus):
        received = []
        event_bus.subscribe(lambda e: received.append(e))
        event = TraceEvent.create(
            source="funnel", event_type="funnel.stage_completed",
            data={"stage": "explore"},
        )
        event_bus.emit(event)
        assert len(received) == 1
        assert received[0].event_type == "funnel.stage_completed"

    def test_subscriber_error_does_not_propagate(self, event_bus):
        def bad_handler(e):
            raise RuntimeError("boom")
        event_bus.subscribe(bad_handler)
        event = TraceEvent.create(source="test", event_type="test.event")
        # Should not raise
        event_bus.emit(event)

    def test_idempotent_emit(self, event_bus):
        event = TraceEvent.create(source="test", event_type="test.dedup")
        event_bus.emit(event)
        event_bus.emit(event)  # duplicate
        results = event_bus.query(event_type="test.dedup")
        assert len(results) == 1

    def test_replay(self, event_bus):
        trace_id = "trace-123"
        for i in range(5):
            event_bus.emit(TraceEvent.create(
                source="funnel", event_type=f"funnel.stage_{i}",
                trace_id=trace_id,
            ))
        events = event_bus.replay(trace_id)
        assert len(events) == 5
        assert events[0].event_type == "funnel.stage_0"
        assert events[4].event_type == "funnel.stage_4"

    def test_query_by_source(self, event_bus):
        event_bus.emit(TraceEvent.create(source="advisor", event_type="a.x"))
        event_bus.emit(TraceEvent.create(source="funnel", event_type="f.x"))
        results = event_bus.query(source="advisor")
        assert len(results) == 1
        assert results[0].source == "advisor"

    def test_in_memory_mode(self, event_bus_memory):
        received = []
        event_bus_memory.subscribe(lambda e: received.append(e))
        event_bus_memory.emit(TraceEvent.create(source="test", event_type="t.x"))
        assert len(received) == 1
        # Query returns empty because no persistence
        assert event_bus_memory.query(source="test") == []

    def test_unsubscribe(self, event_bus):
        received = []
        handler = lambda e: received.append(e)
        event_bus.subscribe(handler)
        event_bus.emit(TraceEvent.create(source="test", event_type="t.1"))
        assert len(received) == 1
        event_bus.unsubscribe(handler)
        event_bus.emit(TraceEvent.create(source="test", event_type="t.2"))
        assert len(received) == 1  # handler not called

    def test_trace_event_create(self):
        event = TraceEvent.create(
            source="kb",
            event_type="kb.artifact_ingested",
            data={"artifact_id": "abc"},
            session_id="sess-1",
        )
        assert event.source == "kb"
        assert event.event_type == "kb.artifact_ingested"
        assert event.session_id == "sess-1"
        assert len(event.event_id) == 32
        assert len(event.trace_id) == 32

    def test_trace_event_to_dict(self):
        event = TraceEvent.create(source="test", event_type="test.x")
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["source"] == "test"
        assert d["event_type"] == "test.x"

    # ── T0.2 robustness tests ────────────────────────────────────

    def test_close_then_emit_raises(self, event_bus):
        """After close(), emit() must raise RuntimeError."""
        event_bus.close()
        event = TraceEvent.create(source="test", event_type="test.post_close")
        with pytest.raises(RuntimeError, match="closed"):
            event_bus.emit(event)

    def test_duplicate_event_id_returns_false(self, event_bus):
        """Duplicate event_id emit returns False (idempotent)."""
        event = TraceEvent.create(source="test", event_type="test.dedup_bool")
        first = event_bus.emit(event)
        assert first is True
        second = event_bus.emit(event)
        assert second is False

    def test_close_idempotent(self, event_bus):
        """Calling close() multiple times must not raise."""
        event_bus.close()
        event_bus.close()  # should not raise
        event_bus.close()  # should not raise


# ══════════════════════════════════════════════════════════════════
# New persistence and provenance tests (T0.1)
# ══════════════════════════════════════════════════════════════════


class TestArtifactStorePersistence:

    def test_save_persists_after_reconnect(self, tmp_dir):
        """Test that data persists after closing and reopening the store."""
        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"

        # First session: store an artifact
        store1 = ArtifactStore(base_dir=base_dir, db_path=db_path)
        content = "# Persistent Data\n\nThis should survive restart."
        art1 = store1.store(content, task_id="t1", step_id="s1", producer="test")
        store1.close()

        # Second session: reopen and verify data exists
        store2 = ArtifactStore(base_dir=base_dir, db_path=db_path)
        retrieved = store2.get(art1.artifact_id)
        assert retrieved is not None
        assert retrieved.artifact_id == art1.artifact_id

        # Verify content is also persisted
        retrieved_content = store2.get_content(art1.artifact_id)
        assert retrieved_content == content
        store2.close()

    def test_multiple_productions_preserved(self, tmp_dir):
        """Test that multiple productions of the same content are all preserved."""
        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"
        store = ArtifactStore(base_dir=base_dir, db_path=db_path)

        content = "shared content"

        # Produce same content from different tasks/producers
        art1 = store.store(content, task_id="task_A", step_id="step1", producer="producer_X")
        art2 = store.store(content, task_id="task_B", step_id="step2", producer="producer_Y")
        art3 = store.store(content, task_id="task_C", step_id="step3", producer="producer_Z")

        # All should have same artifact_id (content-addressable)
        assert art1.artifact_id == art2.artifact_id == art3.artifact_id

        # Get all production records for this artifact
        productions = store.get_productions(art1.artifact_id)
        assert len(productions) == 3

        # Verify each production is distinct
        producers = {p["producer"] for p in productions}
        task_ids = {p["task_id"] for p in productions}
        assert producers == {"producer_X", "producer_Y", "producer_Z"}
        assert task_ids == {"task_A", "task_B", "task_C"}
        store.close()

    def test_production_history_queryable(self, tmp_dir):
        """Test that production history can be queried by task."""
        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"
        store = ArtifactStore(base_dir=base_dir, db_path=db_path)

        # Store multiple artifacts for the same task
        store.store("artifact 1", task_id="research_task", step_id="s1", producer="p1")
        store.store("artifact 2", task_id="research_task", step_id="s2", producer="p2")
        store.store("artifact 3", task_id="research_task", step_id="s3", producer="p3")

        # Query production history for this task
        history = store.get_production_history("research_task")
        assert len(history) == 3

        # Verify ordering (most recent first)
        step_ids = [h["step_id"] for h in history]
        assert step_ids == ["s3", "s2", "s1"]
        store.close()

    def test_save_atomic_on_failure(self, tmp_dir):
        """Test that failed operations don't corrupt the database."""
        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"
        store = ArtifactStore(base_dir=base_dir, db_path=db_path)

        # Store a valid artifact first
        art1 = store.store("valid content", task_id="t1", step_id="s1", producer="p1")

        # Try to get a non-existent artifact (should not affect DB)
        nonexistent = store.get("nonexistent_hash_12345")
        assert nonexistent is None

        # Verify original artifact still exists
        retrieved = store.get(art1.artifact_id)
        assert retrieved is not None
        assert retrieved.artifact_id == art1.artifact_id

        # Verify production count is correct
        productions = store.get_productions(art1.artifact_id)
        assert len(productions) == 1
        store.close()

    def test_concurrent_productions(self, tmp_dir):
        """Test that concurrent productions are handled correctly."""
        import threading

        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"
        store = ArtifactStore(base_dir=base_dir, db_path=db_path)

        results = []
        errors = []

        def produce_content(task_id):
            try:
                art = store.store(f"content for {task_id}", task_id=task_id, step_id="s1", producer="concurrent")
                results.append(art.artifact_id)
            except Exception as e:
                errors.append(str(e))

        # Run multiple threads concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=produce_content, args=(f"task_{i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed without errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

        # All artifact_ids should be unique (different content)
        assert len(set(results)) == 5
        store.close()

    def test_content_persistence_with_different_types(self, tmp_dir):
        """Test persistence with various content types."""
        base_dir = tmp_dir / "artifacts"
        db_path = tmp_dir / "artifacts.db"

        # Store artifact
        store1 = ArtifactStore(base_dir=base_dir, db_path=db_path)
        art = store1.store(
            '{"key": "value"}',
            task_id="t1",
            step_id="s1",
            producer="test",
            content_type="application/json",
        )
        store1.close()

        # Reopen and verify
        store2 = ArtifactStore(base_dir=base_dir, db_path=db_path)
        retrieved = store2.get(art.artifact_id)
        assert retrieved is not None
        assert retrieved.content_type == "application/json"

        content = store2.get_content(art.artifact_id)
        assert content == '{"key": "value"}'
        store2.close()
