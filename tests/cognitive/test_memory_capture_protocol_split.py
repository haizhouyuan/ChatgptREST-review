from __future__ import annotations

from dataclasses import dataclass

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.cognitive.memory_capture_service import MemoryCaptureItem, MemoryCaptureService
from chatgptrest.cognitive.runtime_adapters import MemoryRuntimeAdapter
from chatgptrest.kernel.memory_manager import MemoryManager
from chatgptrest.kernel.protocols import MemoryRuntimeDeps


@dataclass
class _GateResult:
    payload: dict

    def to_dict(self) -> dict:
        return dict(self.payload)


class _AllowAllPolicy:
    def run_quality_gate(self, context):  # noqa: ANN001
        _ = context
        return _GateResult({"allowed": True, "blocked_by": []})


class _EventBusCollector:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:  # noqa: ANN001
        self.events.append(event)


def _build_runtime(*, memory: MemoryManager, policy_engine, event_bus) -> AdvisorRuntime:
    return AdvisorRuntime(
        api=None,
        feishu=None,
        llm=None,
        outbox=None,
        observer=None,
        kb_registry=None,
        graph_app=None,
        advisor_fn=None,
        kb_hub=None,
        memory=memory,
        event_bus=event_bus,
        cc_executor=None,
        cc_native=None,
        evomap_knowledge_db=None,
        policy_engine=policy_engine,
        circuit_breaker=None,
        kb_scorer=None,
        gate_tuner=None,
        routing_fabric=None,
        writeback_service=None,
    )


def _capture_item() -> MemoryCaptureItem:
    return MemoryCaptureItem(
        title="迁移闭环记录",
        content="Hermes 接管前台的最小协议切分已完成一次真实验证。",
        summary="最小协议切分验证完成",
        session_id="sess-1",
        account_id="acct-1",
        agent_id="hermes",
        role_id="planning",
        thread_id="thread-1",
        source_system="hermes",
        source_ref="task://phase3/001",
        project_id="hermes-cutover",
    )


def test_memory_capture_runs_on_fake_protocol_object() -> None:
    memory = MemoryManager(":memory:")
    event_bus = _EventBusCollector()
    fake_runtime = type(
        "FakeMemoryRuntime",
        (),
        {"memory": memory, "policy_engine": _AllowAllPolicy(), "event_bus": event_bus},
    )()

    service = MemoryCaptureService(fake_runtime)
    result = service.capture([_capture_item()])

    assert result.ok is True
    assert result.results[0].ok is True
    assert memory.get_by_key("迁移闭环记录") is not None
    assert len(event_bus.events) == 1


def test_memory_runtime_adapter_projects_minimal_surface() -> None:
    memory = MemoryManager(":memory:")
    policy_engine = _AllowAllPolicy()
    event_bus = _EventBusCollector()
    runtime = _build_runtime(memory=memory, policy_engine=policy_engine, event_bus=event_bus)
    adapter = MemoryRuntimeAdapter.from_runtime(runtime)

    assert isinstance(adapter, MemoryRuntimeDeps)
    assert adapter.memory is memory
    assert adapter.policy_engine is policy_engine
    assert adapter.event_bus is event_bus

    result = MemoryCaptureService(adapter).capture([_capture_item()])
    assert result.ok is True
