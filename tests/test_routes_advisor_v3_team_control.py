from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatgptrest.api.routes_advisor_v3 import make_v3_advisor_router
from chatgptrest.kernel.cc_executor import CcResult, CcTask
from chatgptrest.kernel.team_control_plane import TeamControlPlane


def _make_client(monkeypatch, dispatch_team=None):
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_CONTROL_API_KEY", "control-key")
    monkeypatch.setenv("OPENMIND_RATE_LIMIT", "100")

    plane = TeamControlPlane(db_path=":memory:")
    fake_cc = SimpleNamespace(
        _team_control_plane=plane,
        _team_policy=None,
        dispatch_team=dispatch_team,
    )

    monkeypatch.setattr(
        "chatgptrest.advisor.runtime.get_advisor_runtime",
        lambda: {"cc_native": fake_cc},
    )

    app = FastAPI()
    app.include_router(make_v3_advisor_router())
    headers = {"X-Api-Key": "secret-key", "X-Control-Api-Key": "control-key"}
    return TestClient(app, raise_server_exceptions=False), plane, headers


def test_cc_team_topologies_route_lists_catalog(monkeypatch) -> None:
    client, plane, headers = _make_client(monkeypatch)

    response = client.get("/v2/advisor/cc-team-topologies", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert any(item["topology_id"] == "review_triad" for item in body["topologies"])
    assert any(item["role_id"] == "scout" for item in body["roles"])

    plane.close()


def test_cc_team_run_and_checkpoint_routes(monkeypatch) -> None:
    client, plane, headers = _make_client(monkeypatch)
    spec, topology = plane.resolve_team_spec(topology_id="implementation_duo", task_type="bug_fix")
    assert spec is not None
    assert topology is not None

    task = CcTask(task_type="bug_fix", description="Fix issue", trace_id="tr_route")
    plane.create_run(
        team_run_id="trun_route",
        team_spec=spec,
        topology_id=topology.topology_id,
        task=task,
        repo="ChatgptREST",
    )
    plane.mark_role_started("trun_route", "scout", task_trace_id="tr_route:scout")
    plane.mark_role_completed(
        "trun_route",
        "scout",
        CcResult(ok=True, agent="native", task_type="bug_fix", output="scout", elapsed_seconds=1.0, quality_score=0.8),
    )
    plane.mark_role_started("trun_route", "implementer", task_trace_id="tr_route:implementer")
    plane.mark_role_completed(
        "trun_route",
        "implementer",
        CcResult(ok=True, agent="native", task_type="bug_fix", output="impl", elapsed_seconds=2.0, quality_score=0.9),
    )
    checkpoints = plane.finalize_run(
        team_run_id="trun_route",
        team_spec=spec,
        final_result=CcResult(ok=True, agent="native-team", task_type="bug_fix", output="final", elapsed_seconds=3.0, quality_score=0.85),
        role_outcomes={
            "scout": {"ok": True, "quality_score": 0.8, "elapsed_seconds": 1.0, "error": ""},
            "implementer": {"ok": True, "quality_score": 0.9, "elapsed_seconds": 2.0, "error": ""},
        },
    )

    runs_response = client.get("/v2/advisor/cc-team-runs", headers=headers)
    assert runs_response.status_code == 200
    assert any(item["team_run_id"] == "trun_route" for item in runs_response.json()["runs"])

    detail_response = client.get("/v2/advisor/cc-team-runs/trun_route", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["run"]["team_run_id"] == "trun_route"
    assert detail_response.json()["run"]["status"] == "needs_review"

    cp_response = client.get("/v2/advisor/cc-team-checkpoints", headers=headers)
    assert cp_response.status_code == 200
    assert any(item["checkpoint_id"] == checkpoints[0].checkpoint_id for item in cp_response.json()["checkpoints"])

    approve_response = client.post(
        f"/v2/advisor/cc-team-checkpoints/{checkpoints[0].checkpoint_id}/approve",
        headers=headers,
        json={"actor": "tester", "reason": "approved"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["checkpoint"]["status"] == "approved"

    plane.close()


def test_cc_dispatch_team_applies_topology_overlay_to_explicit_team(monkeypatch) -> None:
    captured = {}

    async def _fake_dispatch(task, team=None):  # noqa: ANN001
        captured["task"] = task
        captured["team"] = team
        return CcResult(
            ok=True,
            agent="native-team",
            task_type=task.task_type,
            output="team output",
            elapsed_seconds=1.0,
            quality_score=0.9,
            trace_id=task.trace_id,
        )

    client, plane, headers = _make_client(monkeypatch, dispatch_team=_fake_dispatch)

    response = client.post(
        "/v2/advisor/cc-dispatch-team",
        headers=headers,
        json={
            "task_type": "architecture_review",
            "description": "Review the design",
            "repo": "ChatgptREST",
            "topology_id": "review_triad",
            "team": {
                "roles": [
                    {"name": "scout", "model": "sonnet", "prompt": "Scout"},
                    {"name": "reviewer", "model": "sonnet", "prompt": "Review"},
                    {"name": "synthesizer", "model": "sonnet", "prompt": "Synthesize"},
                ],
                "metadata": {"custom_flag": "keep-me"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["topology_id"] == "review_triad"
    assert captured["team"] is not None
    assert captured["team"].metadata["topology_id"] == "review_triad"
    assert captured["team"].metadata["execution_mode"] == "parallel"
    assert captured["team"].metadata["synthesis_role"] == "synthesizer"
    assert captured["team"].metadata["gate_ids"] == ["team_failure", "low_quality"]
    assert captured["team"].metadata["custom_flag"] == "keep-me"

    plane.close()
