from __future__ import annotations

from types import SimpleNamespace

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.cognitive.graph_service import GraphQueryOptions, GraphQueryService
from chatgptrest.cognitive.runtime_adapters import GraphRuntimeAdapter
from chatgptrest.kernel.protocols import GraphRuntimeDeps


def _build_runtime(*, evomap_knowledge_db) -> AdvisorRuntime:
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
        memory=None,
        event_bus=None,
        cc_executor=None,
        cc_native=None,
        evomap_knowledge_db=evomap_knowledge_db,
        policy_engine=None,
        circuit_breaker=None,
        kb_scorer=None,
        gate_tuner=None,
        routing_fabric=None,
        writeback_service=None,
    )


def test_graph_query_service_runs_on_fake_protocol_object() -> None:
    fake_runtime = SimpleNamespace(evomap_knowledge_db=None)

    result = GraphQueryService(fake_runtime).query(
        GraphQueryOptions(
            query="Hermes 主线",
            scopes=("business",),
            limit=5,
        )
    )

    assert result.ok is True
    assert result.nodes == []
    assert result.edges == []
    assert result.degraded_sources == ["personal_graph"]
    assert result.metadata["family_router"]["resolved_families"] == ["business"]


def test_graph_runtime_adapter_projects_minimal_surface() -> None:
    runtime = _build_runtime(evomap_knowledge_db=None)
    adapter = GraphRuntimeAdapter.from_runtime(runtime)

    assert isinstance(adapter, GraphRuntimeDeps)
    assert adapter.evomap_knowledge_db is None

    result = GraphQueryService(adapter).query(
        GraphQueryOptions(
            query="Hermes 主线",
            scopes=("business",),
            limit=5,
        )
    )

    assert result.ok is True
    assert result.degraded_sources == ["personal_graph"]
