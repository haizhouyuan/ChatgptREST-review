from __future__ import annotations

import json
from types import SimpleNamespace

from chatgptrest.advisor import graph as graph_mod
from chatgptrest.kernel.policy_engine import PolicyEngine


class _DummyFunnelApp:
    def compile(self):
        return self

    def invoke(self, payload: dict[str, str]) -> dict[str, object]:
        return {
            "status": "complete",
            "problem_statement": payload["user_message"],
            "project_card": {"title": "Agent Dashboard"},
            "tasks": [{"title": "Build dashboard"}],
            "recommended_option": "ship dashboard",
            "gate_a_pass": True,
            "gate_b_pass": True,
        }


class _DummyDispatcher:
    last_outbox = None

    def __init__(self, *, outbox=None, llm_fn=None):
        type(self).last_outbox = outbox
        self._llm_fn = llm_fn

    def build_context_package(self, funnel_result: dict[str, object], *, trace_id: str = "", advisor_rationale: str = ""):
        return {"trace_id": trace_id, "advisor_rationale": advisor_rationale, "funnel_result": funnel_result}

    def dispatch(self, ctx: dict[str, object]) -> dict[str, object]:
        return {
            "status": "dispatched",
            "trace_id": ctx["trace_id"],
            "result": {
                "session_id": "sess-123",
                "task_count": 1,
                "project_dir": "/vol1/1000/projects/demo-agent-dashboard",
                "deliverables": [
                    "/vol1/1000/projects/demo-agent-dashboard/README.md",
                    "/home/yuanhaizhou/.openmind/projects/demo-agent-dashboard/project_card.json",
                ],
                "code_files": ["/tmp/demo-agent-dashboard/app.py"],
            },
        }


def test_execute_funnel_kb_writeback_sanitizes_dispatch_paths(monkeypatch) -> None:
    import chatgptrest.advisor.dispatch as dispatch_mod
    import chatgptrest.advisor.funnel_graph as funnel_graph_mod

    captured: dict[str, str] = {}

    monkeypatch.setattr(funnel_graph_mod, "build_funnel_graph", lambda: _DummyFunnelApp())
    monkeypatch.setattr(dispatch_mod, "AgentDispatcher", _DummyDispatcher)
    def _capture_writeback(**kwargs):
        captured["content"] = kwargs["content"]
        return {"success": True}

    monkeypatch.setattr(graph_mod, "_kb_writeback_and_record", _capture_writeback)

    runtime = SimpleNamespace(
        llm_connector=None,
        evomap_observer=None,
        kb_registry=None,
        event_bus=None,
        outbox=object(),
        model_router=None,
        writeback_service=None,
    )
    state = {
        "user_message": "开发一个Agent团队管理Dashboard功能",
        "trace_id": "trace-funnel-1",
        "route_rationale": "BUILD_FEATURE intent",
    }

    with graph_mod.bind_runtime_services(runtime):
        result = graph_mod.execute_funnel(state)

    content = captured["content"]
    payload = json.loads(content)
    dispatch_summary = payload["dispatch_summary"]

    assert "/vol1/" not in content
    assert "/home/" not in content
    assert "/tmp/" not in content
    assert dispatch_summary["status"] == "dispatched"
    assert "project_dir" not in dispatch_summary["result"]
    assert dispatch_summary["result"]["deliverable_count"] == 2
    assert dispatch_summary["result"]["code_file_count"] == 1
    assert dispatch_summary["result"]["has_project_dir"] is True
    assert result["route_result"]["dispatch"]["result"]["project_dir"] == "/vol1/1000/projects/demo-agent-dashboard"
    assert _DummyDispatcher.last_outbox is runtime.outbox

    security = PolicyEngine().check_security(content, "internal")
    assert security.allowed is True
