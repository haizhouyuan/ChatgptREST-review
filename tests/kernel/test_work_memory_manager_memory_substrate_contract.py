from __future__ import annotations

from chatgptrest.kernel.memory_manager import MemoryManager, MemoryRecord, MemorySource, MemoryTier
from chatgptrest.kernel.protocols import MemorySubstrate
from chatgptrest.kernel.work_memory_manager import WorkMemoryManager


class _FakeMemorySubstrate:
    def __init__(self) -> None:
        self.record = MemoryRecord(
            record_id="old-record",
            tier=MemoryTier.EPISODIC.value,
            category="decision_ledger",
            key="decision-old",
            value={
                "kind": "decision_ledger",
                "schema_version": "v1",
                "object_id": "decision-old",
                "decision_id": "decision-old",
                "statement": "旧决策",
                "domain": "planning",
                "confidence": 0.8,
                "review_status": "active",
                "source_refs": ["seed://old"],
                "valid_from": "2026-04-01T00:00:00+00:00",
            },
            confidence=0.8,
            source=MemorySource(type="system", agent="advisor").to_dict(),
        )
        self.staged: list[MemoryRecord] = []
        self.promoted: list[tuple[str, MemoryTier, str]] = []
        self.updated: list[tuple[str, dict, str, str]] = []

    def stage(self, record: MemoryRecord) -> str:
        if not record.record_id:
            record.record_id = "new-record"
        self.staged.append(record)
        return record.record_id

    def promote(self, record_id: str, target: MemoryTier, reason: str = "") -> bool:
        self.promoted.append((record_id, target, reason))
        return True

    def stage_and_promote(self, record: MemoryRecord, target: MemoryTier, reason: str = "") -> str:
        record_id = self.stage(record)
        self.promote(record_id, target, reason)
        return record_id

    def audit_trail(self, record_id: str) -> list[dict]:
        return [{"record_id": record_id, "action": "promote"}]

    def get_episodic(
        self,
        query: str = "",
        category: str = "",
        limit: int = 10,
        agent_id: str = "",
        session_id: str = "",
        role_id: str = "",
        account_id: str = "",
        thread_id: str = "",
        project_id: str = "",
    ) -> list[MemoryRecord]:
        _ = (query, category, limit, agent_id, session_id, role_id, account_id, thread_id, project_id)
        return []

    def get_by_key(self, key: str) -> MemoryRecord | None:
        if key == self.record.key:
            return self.record
        return None

    def update_record_value(
        self,
        record_id: str,
        value: dict,
        *,
        reason: str = "",
        agent: str = "system",
    ) -> bool:
        self.updated.append((record_id, value, reason, agent))
        self.record.value = value
        return True


def test_memory_manager_implements_memory_substrate_protocol() -> None:
    memory = MemoryManager(":memory:")
    assert isinstance(memory, MemorySubstrate)


def test_work_memory_manager_write_from_capture_works_with_fake_memory_substrate() -> None:
    memory = _FakeMemorySubstrate()
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="active_project",
        title="Hermes 接管前台",
        content="正在验证协议切分。",
        summary="验证中",
        payload={
            "kind": "active_project",
            "project_id": "hermes-cutover",
            "name": "Hermes 接管前台",
            "phase": "phase-3",
            "status": "validating",
            "review_status": "staged",
            "source_refs": ["task://001"],
        },
        source_ref="task://001",
        source_system="hermes",
        source_agent="hermes",
        role_id="planning",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-1",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    assert result.ok is True
    assert memory.staged
    assert memory.promoted


def test_work_memory_manager_supersede_uses_memory_lookup_and_update() -> None:
    memory = _FakeMemorySubstrate()
    manager = WorkMemoryManager(memory)

    superseded_record_id = manager._supersede_decision(  # noqa: SLF001
        previous_decision_id="decision-old",
        new_decision_id="decision-new",
        valid_to="2026-04-15T00:00:00+00:00",
    )

    assert superseded_record_id == "old-record"
    assert memory.updated
    _, updated_value, reason, _ = memory.updated[0]
    assert updated_value["review_status"] == "superseded"
    assert updated_value["superseded_by"] == "decision-new"
    assert "superseded by decision-new" in reason
