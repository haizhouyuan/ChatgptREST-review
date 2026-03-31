from __future__ import annotations

import threading
from typing import Any

from chatgptrest.advisor import graph as graph_mod
from chatgptrest.advisor.runtime import (
    AdvisorRuntime,
    _invoke_graph_app,
    get_advisor_runtime,
    get_advisor_runtime_if_ready,
    is_advisor_runtime_ready,
    reset_advisor_runtime,
)
from chatgptrest.cognitive.telemetry_service import TelemetryEventInput, TelemetryIngestService
from chatgptrest.kernel.event_bus import TraceEvent


def _dummy_runtime(**overrides: Any) -> AdvisorRuntime:
    payload: dict[str, Any] = {
        "api": None,
        "feishu": None,
        "llm": "llm",
        "outbox": None,
        "observer": "observer",
        "kb_registry": "registry",
        "graph_app": None,
        "advisor_fn": None,
        "kb_hub": None,
        "memory": None,
        "event_bus": None,
        "cc_executor": None,
        "cc_native": None,
        "evomap_knowledge_db": None,
        "policy_engine": "policy",
        "circuit_breaker": None,
        "kb_scorer": None,
        "gate_tuner": None,
        "routing_fabric": None,
        "writeback_service": None,
    }
    payload.update(overrides)
    return AdvisorRuntime(**payload)


def test_invoke_graph_app_binds_runtime_for_graph_services() -> None:
    graph_mod.reset_services()
    seen: dict[str, Any] = {}

    class DummyApp:
        def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
            seen["svc"] = graph_mod._svc(payload)
            seen["config"] = config
            return {"ok": True}

    runtime = _dummy_runtime()

    result = _invoke_graph_app(
        app=DummyApp(),
        runtime=runtime,
        payload={"trace_id": "trace-1"},
        thread_id="trace-1",
    )

    assert result == {"ok": True}
    assert seen["svc"] is runtime
    assert seen["config"]["configurable"]["thread_id"] == "trace-1"
    assert graph_mod._svc({}) is not runtime


def test_runtime_ready_helpers_track_reset_boundary(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    reset_advisor_runtime()
    assert is_advisor_runtime_ready() is False
    assert get_advisor_runtime_if_ready() is None

    runtime = get_advisor_runtime()
    assert is_advisor_runtime_ready() is True
    assert get_advisor_runtime_if_ready() is runtime

    reset_advisor_runtime()
    assert is_advisor_runtime_ready() is False
    assert get_advisor_runtime_if_ready() is None


def test_reset_advisor_runtime_stops_watcher_closes_resources_and_clears_registry(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENMIND_ENABLE_ROUTING_WATCHER", "1")

    reset_advisor_runtime()
    runtime = get_advisor_runtime()

    assert runtime.routing_fabric is not None
    assert getattr(runtime.routing_fabric, "_watcher", None) is not None
    assert len(runtime.event_bus._subscribers) >= 2
    assert len(runtime.kb_registry._callbacks) >= 1
    assert graph_mod._svc({}).llm_connector is not None

    reset_advisor_runtime()

    assert getattr(runtime.routing_fabric, "_watcher", None) is None
    assert runtime.event_bus._subscribers == []
    assert runtime.event_bus._closed is True
    assert runtime.outbox._closed is True
    assert runtime.kb_hub._closed is True
    assert getattr(runtime.memory._local, "conn", None) is None
    assert getattr(runtime.kb_registry._local, "conn", None) is None
    assert runtime.observer._connections == []
    assert runtime.evomap_knowledge_db._conn is None
    assert runtime.kb_registry._callbacks == []
    assert graph_mod._svc({}).llm_connector is None


def test_evomap_extractors_are_disabled_by_default(monkeypatch) -> None:
    started_names: list[str] = []
    original_thread = threading.Thread

    class RecordingThread(original_thread):
        def start(self) -> None:
            started_names.append(self.name)

    monkeypatch.delenv("OPENMIND_ENABLE_EVOMAP_EXTRACTORS", raising=False)
    monkeypatch.setattr("chatgptrest.advisor.runtime.threading.Thread", RecordingThread)

    reset_advisor_runtime()
    get_advisor_runtime()
    reset_advisor_runtime()

    assert "EvoMapExtractor" not in started_names


def test_evomap_startup_rescore_is_disabled_by_default(monkeypatch) -> None:
    called = {"rescore": 0}

    def _fake_rescore(*args, **kwargs):
        called["rescore"] += 1

    monkeypatch.delenv("OPENMIND_ENABLE_EVOMAP_STARTUP_RESCORE", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setattr(
        "chatgptrest.evomap.knowledge.retrieval.rescore_all_atoms",
        _fake_rescore,
    )

    reset_advisor_runtime()
    get_advisor_runtime()
    reset_advisor_runtime()

    assert called["rescore"] == 0


def test_runtime_wires_activity_ingest_for_live_telemetry(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(tmp_path / "evomap_knowledge.db"))
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", str(tmp_path / "events.db"))
    monkeypatch.setenv("OPENMIND_KB_DB", str(tmp_path / "kb_registry.db"))
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(tmp_path / "kb_search.db"))
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", str(tmp_path / "kb_vectors.db"))
    monkeypatch.setenv("OPENMIND_MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("OPENMIND_DB_PATH", str(tmp_path / "effects.db"))
    monkeypatch.setenv("OPENMIND_DEDUP_DB", str(tmp_path / "dedup.db"))
    monkeypatch.setenv("OPENMIND_CHECKPOINT_DB", str(tmp_path / "checkpoint.db"))

    reset_advisor_runtime()
    runtime = get_advisor_runtime()
    telemetry = TelemetryIngestService(runtime)

    try:
        result = telemetry.ingest(
            trace_id="trace-live-ev",
            session_id="session-live-ev",
            events=[
                TelemetryEventInput(
                    event_type="tool.completed",
                    source="codex",
                    task_ref="task-live-ev",
                    repo_name="ChatgptREST",
                    repo_path="/vol1/1000/projects/ChatgptREST",
                    agent_name="codex",
                    provider="openai",
                    model="gpt-5",
                    data={"tool": "pytest", "ok": True},
                )
            ],
        )
        assert result.ok is True

        live_atom = runtime.evomap_knowledge_db.connect().execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question = ?",
            ("activity: tool.completed",),
        ).fetchone()[0]
        assert live_atom == 1

        closeout_result = telemetry.ingest(
            trace_id="trace-closeout-archive-live",
            session_id="session-closeout-archive-live",
            events=[
                TelemetryEventInput(
                    event_type="agent.task.closeout",
                    source="workflow/task-closeout",
                    data={
                        "event_type": "agent.task.closeout",
                        "schema_version": "openmind-v3-agent-ops-v1",
                        "ts": "2026-03-10T22:30:00+08:00",
                        "task_ref": "task-archive-live",
                        "repo": {
                            "path": "/vol1/1000/projects/ChatgptREST",
                            "name": "ChatgptREST",
                            "branch": "main",
                        },
                        "agent": {"name": "codex"},
                        "closeout": {
                            "status": "completed",
                            "summary": "Archive envelope reached live EvoMap ingest",
                        },
                    },
                    task_ref="task-archive-live",
                    repo_name="ChatgptREST",
                    repo_path="/vol1/1000/projects/ChatgptREST",
                    agent_name="codex",
                    provider="openai",
                    model="gpt-5",
                )
            ],
        )
        assert closeout_result.ok is True

        closeout_live_atom = runtime.evomap_knowledge_db.connect().execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question = ?",
            ("task result: task-archive-live by codex",),
        ).fetchone()[0]
        assert closeout_live_atom == 1

        runtime.event_bus.emit(
            TraceEvent.create(
                source="maint",
                event_type="agent.task.closeout",
                trace_id="trace-closeout-ev",
                session_id="session-closeout-ev",
                data={
                    "task_id": "task-closeout-ev",
                    "task_ref": "task-closeout-ev",
                    "agent_id": "codex",
                    "summary": "Validated live EV telemetry wiring",
                    "status": "completed",
                    "repo_name": "ChatgptREST",
                    "repo_path": "/vol1/1000/projects/ChatgptREST",
                },
            )
        )
        closeout_atom = runtime.evomap_knowledge_db.connect().execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question = ?",
            ("task result: task-closeout-ev by codex",),
        ).fetchone()[0]
        assert closeout_atom == 1
    finally:
        reset_advisor_runtime()


def test_runtime_wires_skill_platform_components_and_closes_gap_recorder(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    reset_advisor_runtime()
    runtime = get_advisor_runtime()

    assert runtime.skill_registry is not None
    assert runtime.bundle_resolver is not None
    assert runtime.capability_gap_recorder is not None
    assert runtime.quarantine_gate is not None
    assert runtime.skill_registry.authority.owner == "ChatgptREST/OpenMind"
    assert runtime.quarantine_gate.check_trust("chatgptrest-call") is True

    resolution = runtime.bundle_resolver.resolve_for_agent(
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
    )
    assert resolution.status == "unmet_capabilities"

    gaps = runtime.capability_gap_recorder.promote_unmet(
        trace_id="trace-runtime-skill-gap",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        unmet_capabilities=[item.to_dict() for item in resolution.unmet_capabilities],
        suggested_agent=resolution.suggested_agent or "",
    )
    assert len(gaps) == 1
    assert runtime.capability_gap_recorder.fetch_gaps(status="open")[0].gap_id == gaps[0].gap_id

    reset_advisor_runtime()

    assert runtime.capability_gap_recorder._connections == []


def test_runtime_telemetry_replay_uses_upstream_event_id_for_idempotency(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(tmp_path / "evomap_knowledge.db"))
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", str(tmp_path / "events.db"))
    monkeypatch.setenv("OPENMIND_KB_DB", str(tmp_path / "kb_registry.db"))
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(tmp_path / "kb_search.db"))
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", str(tmp_path / "kb_vectors.db"))
    monkeypatch.setenv("OPENMIND_MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("OPENMIND_DB_PATH", str(tmp_path / "effects.db"))
    monkeypatch.setenv("OPENMIND_DEDUP_DB", str(tmp_path / "dedup.db"))
    monkeypatch.setenv("OPENMIND_CHECKPOINT_DB", str(tmp_path / "checkpoint.db"))

    reset_advisor_runtime()
    runtime = get_advisor_runtime()
    telemetry = TelemetryIngestService(runtime)

    try:
        for _ in range(2):
            result = telemetry.ingest(
                trace_id="trace-replay-idempotent",
                session_id="session-replay-idempotent",
                events=[
                    TelemetryEventInput(
                        event_type="team.run.created",
                        source="openclaw",
                        event_id="external-123",
                        task_ref="issue-200/p0",
                        repo_name="ChatgptREST",
                        repo_path="/vol1/1000/projects/ChatgptREST",
                        agent_name="codex",
                        data={"status": "started"},
                    )
                ],
            )
            assert result.ok is True

        trace_events = runtime.event_bus.query(trace_id="trace-replay-idempotent")
        assert len(trace_events) == 1
        assert trace_events[0].event_id == "external-123"
        assert trace_events[0].data["upstream_event_id"] == "external-123"

        live_atom = runtime.evomap_knowledge_db.connect().execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question = ?",
            ("activity: team.run.created",),
        ).fetchone()[0]
        assert live_atom == 1
    finally:
        reset_advisor_runtime()
