from __future__ import annotations

from types import SimpleNamespace

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.cognitive.context_service import ContextResolveOptions, ContextResolver
from chatgptrest.cognitive.runtime_adapters import ContextRuntimeAdapter
from chatgptrest.kernel.memory_manager import MemoryManager, MemoryRecord, MemorySource, MemoryTier
from chatgptrest.kernel.protocols import ContextRuntimeDeps


def _active_project_record() -> MemoryRecord:
    return MemoryRecord(
        category="active_project",
        key="active_project:hermes-cutover",
        value={
            "kind": "active_project",
            "schema_version": "v1",
            "object_id": "hermes-cutover",
            "review_status": "active",
            "source_refs": ["spec://task"],
            "project_id": "hermes-cutover",
            "name": "Hermes 接管前台",
            "phase": "phase-3",
            "status": "validating",
            "blockers": ["等待 research_diagnosis 闭环"],
            "next_steps": ["继续跑真实模板"],
            "key_files": ["docs/runtime.md"],
            "owner": "codex",
        },
        confidence=0.9,
        source=MemorySource(
            type="system",
            agent="advisor",
            role="planning",
            session_id="sess-1",
            account_id="acct-1",
            thread_id="thread-1",
            project_id="hermes-cutover",
        ).to_dict(),
    )


def _build_runtime(*, memory: MemoryManager) -> AdvisorRuntime:
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
        event_bus=None,
        cc_executor=None,
        cc_native=None,
        evomap_knowledge_db=None,
        policy_engine=None,
        circuit_breaker=None,
        kb_scorer=None,
        gate_tuner=None,
        routing_fabric=None,
        writeback_service=None,
    )


def test_context_resolver_runs_on_fake_protocol_object() -> None:
    memory = MemoryManager(":memory:")
    memory.stage_and_promote(_active_project_record(), MemoryTier.EPISODIC, "test")
    fake_runtime = SimpleNamespace(memory=memory, kb_hub=None, evomap_knowledge_db=None)

    resolver = ContextResolver(fake_runtime)
    result = resolver.resolve(
        ContextResolveOptions(
            query="当前迁移主线阻塞是什么",
            session_id="sess-1",
            account_id="acct-1",
            role_id="planning",
            thread_id="thread-1",
            project_id="hermes-cutover",
            sources=("memory",),
        )
    )

    assert result.ok is True
    assert any(block.source_type == "work_memory_active" for block in result.context_blocks)
    active_block = next(block for block in result.context_blocks if block.source_type == "work_memory_active")
    assert "Active Project Map" in active_block.text
    assert "Hermes 接管前台" in active_block.text


def test_context_runtime_adapter_projects_minimal_surface() -> None:
    memory = MemoryManager(":memory:")
    memory.stage_and_promote(_active_project_record(), MemoryTier.EPISODIC, "test")
    runtime = _build_runtime(memory=memory)
    adapter = ContextRuntimeAdapter.from_runtime(runtime)

    assert isinstance(adapter, ContextRuntimeDeps)
    assert adapter.memory is memory
    assert adapter.kb_hub is None
    assert adapter.evomap_knowledge_db is None

    result = ContextResolver(adapter).resolve(
        ContextResolveOptions(
            query="当前迁移主线阻塞是什么",
            session_id="sess-1",
            account_id="acct-1",
            role_id="planning",
            thread_id="thread-1",
            project_id="hermes-cutover",
            sources=("memory",),
        )
    )
    assert result.ok is True
