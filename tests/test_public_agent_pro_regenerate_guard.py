from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.advisor.graph as advisor_graph
import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.advisor.runtime import reset_advisor_runtime
from chatgptrest.controller.engine import ControllerEngine
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect


def _patch_report_route(monkeypatch) -> None:
    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": False,
            "kb_answerability": 0.0,
            "kb_top_chunks": [],
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "analyze_intent",
        lambda state: {
            "intent_top": "WRITE_REPORT",
            "intent_confidence": 0.95,
            "multi_intent": False,
            "step_count_est": 2,
            "constraint_count": 0,
            "open_endedness": 0.3,
            "verification_need": True,
            "action_required": False,
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "route_decision",
        lambda state: {
            "selected_route": "report",
            "route_rationale": "test report route",
            "executor_lane": "chatgpt",
        },
    )


def _route_mapping() -> dict[str, dict[str, str]]:
    return {
        "quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
        "report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
    }


def _mark_job_needs_regenerate(*, db_path: Path, job_id: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
               SET status = ?,
                   last_error_type = ?,
                   last_error = ?,
                   conversation_url = ?
             WHERE job_id = ?
            """,
            (
                "needs_followup",
                "ProInstantAnswerNeedsRegenerate",
                "thinking preset produced a suspicious fast answer; request regenerate on the same conversation",
                "https://chatgpt.com/c/test-pro-regenerate",
                job_id,
            ),
        )
        conn.commit()


def _make_agent_client(monkeypatch) -> TestClient:
    reset_advisor_runtime()
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    app = FastAPI()
    app.include_router(routes_agent_v3.make_v3_agent_router())
    return TestClient(app, raise_server_exceptions=False)


def _wait_for_latest_job_id(*, db_path: Path, timeout_seconds: float = 2.0) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with connect(db_path) as conn:
            row = conn.execute("SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        if row is not None and str(row["job_id"] or "").strip():
            return str(row["job_id"])
        time.sleep(0.05)
    raise AssertionError("expected controller dispatch job to be created")


def test_controller_reconciles_pro_instant_answer_regenerate_to_waiting_human(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    _patch_report_route(monkeypatch)

    engine = ControllerEngine({})
    result = engine.ask(
        question="请正式评审这个战略材料并给出建议",
        trace_id="trace-pro-regenerate-controller",
        intent_hint="report",
        role_id="",
        session_id="sess-pro-regenerate-controller",
        account_id="",
        thread_id="",
        agent_id="",
        user_id="tester",
        stable_context={},
        idempotency_key="controller-pro-regenerate",
        request_fingerprint="controller-pro-regenerate",
        timeout_seconds=300,
        max_retries=1,
        quality_threshold=0,
        request_metadata={},
        degradation=[],
        route_mapping=_route_mapping(),
        kb_direct_completion_allowed=lambda _state: False,
        kb_direct_synthesis_enabled=lambda: False,
    )

    assert result["controller_status"] == "WAITING_EXTERNAL"
    cfg = load_config()
    _mark_job_needs_regenerate(db_path=cfg.db_path, job_id=str(result["job_id"]))

    snapshot = engine.get_run_snapshot(run_id=str(result["run_id"]))

    assert snapshot is not None
    assert snapshot["run"]["controller_status"] == "WAITING_HUMAN"
    assert snapshot["run"]["delivery"]["status"] == "waiting_human"
    assert snapshot["run"]["next_action"]["type"] == "same_session_repair"
    assert snapshot["run"]["next_action"]["error_type"] == "ProInstantAnswerNeedsRegenerate"


def test_public_agent_session_projects_pro_instant_answer_regenerate_as_needs_followup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_report_route(monkeypatch)

    client = _make_agent_client(monkeypatch)
    headers = {"X-Api-Key": "test-key"}

    turn = client.post(
        "/v3/agent/turn",
        json={
            "message": "请正式评审这个战略材料并给出建议",
            "goal_hint": "report",
            "delivery_mode": "deferred",
            "trace_id": "trace-pro-regenerate-agent",
            "contract": {
                "decision_to_support": "是否进入下一阶段投入",
                "audience": "管理层",
                "output_shape": "markdown_report",
                "task_template": "report_generation",
                "risk_class": "medium",
            },
        },
        headers=headers,
    )

    assert turn.status_code == 202
    session_id = turn.json()["session_id"]

    cfg = load_config()
    job_id = _wait_for_latest_job_id(db_path=cfg.db_path)
    _mark_job_needs_regenerate(db_path=cfg.db_path, job_id=job_id)

    status = client.get(f"/v3/agent/session/{session_id}", headers=headers)
    assert status.status_code == 200
    body = status.json()

    assert body["status"] == "needs_followup"
    assert body["lifecycle"]["phase"] == "clarify_required"
    assert body["lifecycle"]["same_session_patch_allowed"] is True
    assert body["next_action"]["type"] == "same_session_repair"
    assert body["next_action"]["job_id"] == job_id
    assert body["delivery"]["terminal"] is False
    assert body["provenance"]["job_id"] == job_id
    assert str(body.get("answer") or "").strip() == ""
