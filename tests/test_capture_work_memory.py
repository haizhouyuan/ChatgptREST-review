from __future__ import annotations

from types import SimpleNamespace

from chatgptrest.cognitive.memory_capture_service import MemoryCaptureItem, MemoryCaptureService
from chatgptrest.kernel.memory_manager import MemoryManager


class _FakeBus:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> bool:
        self.events.append(event)
        return True


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        memory=MemoryManager(":memory:"),
        policy_engine=None,
        event_bus=_FakeBus(),
    )


def test_memory_capture_service_dispatches_work_memory_categories() -> None:
    runtime = _runtime()
    service = MemoryCaptureService(runtime)

    result = service.capture(
        [
            MemoryCaptureItem(
                title="Project state",
                content="Project moved into execution.",
                summary="Project moved into execution.",
                trace_id="trace-work-memory",
                session_id="sess-1",
                account_id="acct-1",
                agent_id="advisor",
                role_id="planning",
                thread_id="thread-1",
                source_system="advisor_agent",
                source_ref="doc://project-state",
                category="active_project",
                object_payload={
                    "project_id": "prj-001",
                    "name": "Alpha",
                    "phase": "execution",
                    "status": "active",
                    "review_status": "approved",
                },
            )
        ]
    )

    item = result.results[0]
    assert item.ok is True
    assert item.category == "active_project"
    assert item.tier == "episodic"
    assert item.work_memory["kind"] == "active_project"
    assert item.review_status == "approved"
    assert item.active is True
    assert runtime.event_bus.events[-1].event_type == "memory.capture"


def test_memory_capture_service_returns_blocked_receipt_for_invalid_work_memory() -> None:
    runtime = _runtime()
    service = MemoryCaptureService(runtime)

    result = service.capture(
        [
            MemoryCaptureItem(
                title="Decision",
                content="Freeze the new baseline.",
                trace_id="trace-work-memory-blocked",
                session_id="sess-1",
                account_id="acct-1",
                agent_id="advisor",
                role_id="planning",
                thread_id="thread-1",
                source_system="advisor_agent",
                source_ref="",
                category="decision_ledger",
                object_payload={
                    "decision_id": "dec-001",
                    "statement": "Freeze the new baseline.",
                    "domain": "planning",
                },
            )
        ]
    )

    item = result.results[0]
    assert item.ok is False
    assert item.blocked_by == ["missing_source_refs"]
    assert item.promotion_state == "blocked_validation"
    assert runtime.event_bus.events[-1].event_type == "memory.capture.blocked"
