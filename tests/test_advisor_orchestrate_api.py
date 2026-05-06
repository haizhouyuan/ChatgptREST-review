from __future__ import annotations

import asyncio
import time
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core import artifacts
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _mock_wrapper() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        prompt_refine=lambda raw_question, context: f"refined: {raw_question}",
        question_gap_check=lambda raw_question, context: [],
        channel_strategy=lambda raw_question: "chatgpt_pro",
    )


def _mark_child_completed(*, env: dict[str, Path], child_job_id: str, answer: str) -> None:
    answer_meta = artifacts.write_answer(env["artifacts_dir"], child_job_id, answer=answer, answer_format="text")
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE jobs
            SET status = 'completed',
                phase = 'wait',
                updated_at = ?,
                answer_path = ?,
                answer_format = ?,
                answer_sha256 = ?,
                answer_chars = ?
            WHERE job_id = ?
            """,
            (
                float(time.time()),
                answer_meta.answer_path,
                answer_meta.answer_format,
                answer_meta.answer_sha256,
                answer_meta.answer_chars,
                child_job_id,
            ),
        )
        conn.commit()


def test_advisor_advise_orchestrate_creates_run_and_job(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(mod, "_load_wrapper_module", _mock_wrapper)

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "给我做一个编排方案",
            "execute": True,
            "orchestrate": True,
            "mode": "strict",
            "quality_threshold": 21,
            "max_retries": 2,
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t1",
            "X-Request-ID": "rid-orch-1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"job_created", "cooldown"}
    assert body["orchestrate"] is True
    assert isinstance(body.get("run_id"), str) and body["run_id"]
    assert isinstance(body.get("orchestrate_job_id"), str) and body["orchestrate_job_id"]
    assert body.get("provider") == "advisor_orchestrate"

    run = client.get(f"/v1/advisor/runs/{body['run_id']}")
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["run_id"] == body["run_id"]
    assert run_body["mode"] == "strict"
    assert run_body["quality_threshold"] == 21
    assert run_body["max_retries"] == 2
    assert run_body["orchestrate_job_id"] == body["orchestrate_job_id"]


def test_orchestrate_worker_dispatches_child_job_and_records_events(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(mod, "_load_wrapper_module", _mock_wrapper)

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "把这个任务编排执行",
            "execute": True,
            "orchestrate": True,
            "mode": "balanced",
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t2",
            "X-Request-ID": "rid-orch-2",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    run_id = str(body["run_id"])
    orch_job_id = str(body["orchestrate_job_id"])

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="advisor-orch-test", lease_ttl_seconds=60, role="send"))
    assert ran is True

    orch_job = client.get(f"/v1/jobs/{orch_job_id}")
    assert orch_job.status_code == 200
    assert orch_job.json()["status"] == "completed"

    run = client.get(f"/v1/advisor/runs/{run_id}")
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["status"] == "RUNNING"
    assert isinstance(run_body.get("final_job_id"), str) and run_body["final_job_id"]
    assert len(run_body.get("steps") or []) >= 1
    step = run_body["steps"][0]
    assert step["step_id"] == "ask_primary"
    assert step["status"] in {"EXECUTING", "SUCCEEDED"}
    child_job_id = str(run_body["final_job_id"])

    child = client.get(f"/v1/jobs/{child_job_id}")
    assert child.status_code == 200
    assert child.json()["kind"] == "chatgpt_web.ask"

    events = client.get(f"/v1/advisor/runs/{run_id}/events?after_id=0&limit=200")
    assert events.status_code == 200
    event_types = {ev["type"] for ev in events.json()["events"]}
    assert "run.created" in event_types
    assert "run.planned" in event_types
    assert "step.dispatched" in event_types
    assert "step.started" in event_types

    # Simulate child completion then verify run reconciliation to COMPLETED.
    _mark_child_completed(
        env=env,
        child_job_id=child_job_id,
        answer="结论：建议执行A方案。来源: https://example.com\n不确定性：存在并发抖动风险。\n下一步：1. 先灰度再全量。",
    )

    run_stale = client.get(f"/v1/advisor/runs/{run_id}")
    assert run_stale.status_code == 200
    assert run_stale.json()["status"] == "RUNNING"

    run2 = client.post(
        f"/v1/advisor/runs/{run_id}/reconcile",
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t2",
            "X-Request-ID": "rid-orch-2-reconcile-1",
        },
    )
    assert run2.status_code == 200
    assert run2.json()["status"] == "COMPLETED"

    artifacts_view = client.get(f"/v1/advisor/runs/{run_id}/artifacts")
    assert artifacts_view.status_code == 200
    art_body = artifacts_view.json()
    assert art_body["run_id"] == run_id
    assert isinstance(art_body.get("artifacts"), list)


def test_orchestrate_gate_retry_then_complete(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(mod, "_load_wrapper_module", _mock_wrapper)

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "做一次带质量门重试的编排",
            "context": {"require_evidence": True, "constraints": ["SLA"]},
            "execute": True,
            "orchestrate": True,
            "mode": "strict",
            "quality_threshold": 20,
            "max_retries": 1,
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t3",
            "X-Request-ID": "rid-orch-retry-1",
        },
    )
    assert resp.status_code == 200
    run_id = str(resp.json()["run_id"])
    orch_job_id = str(resp.json()["orchestrate_job_id"])

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="advisor-orch-retry", lease_ttl_seconds=60, role="send"))
    assert ran is True
    orch_job = client.get(f"/v1/jobs/{orch_job_id}")
    assert orch_job.status_code == 200
    assert orch_job.json()["status"] == "completed"

    run = client.get(f"/v1/advisor/runs/{run_id}")
    child_job_id = str(run.json()["final_job_id"])

    # First completion intentionally fails gate (no evidence, short answer), should dispatch retry.
    _mark_child_completed(env=env, child_job_id=child_job_id, answer="ok")
    run_after_fail = client.post(
        f"/v1/advisor/runs/{run_id}/reconcile",
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t3",
            "X-Request-ID": "rid-orch-retry-1-reconcile-1",
        },
    )
    assert run_after_fail.status_code == 200
    run_after_fail_body = run_after_fail.json()
    assert run_after_fail_body["status"] in {"RUNNING", "WAITING_GATES"}
    retry_child_job_id = str(run_after_fail_body["final_job_id"])
    assert retry_child_job_id != child_job_id

    # Second completion passes gates.
    _mark_child_completed(
        env=env,
        child_job_id=retry_child_job_id,
        answer="结论明确。来源: https://example.com/report\n风险与假设：可能存在波动。\n下一步：1. 执行SLA方案",
    )
    run_done = client.post(
        f"/v1/advisor/runs/{run_id}/reconcile",
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t3",
            "X-Request-ID": "rid-orch-retry-1-reconcile-2",
        },
    )
    assert run_done.status_code == 200
    assert run_done.json()["status"] == "COMPLETED"

    events = client.get(f"/v1/advisor/runs/{run_id}/events?after_id=0&limit=300")
    assert events.status_code == 200
    event_types = [ev["type"] for ev in events.json()["events"]]
    assert "gate.failed" in event_types
    assert "gate.passed" in event_types
    assert "step.succeeded" in event_types


def test_orchestrate_takeover_and_replay(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(mod, "_load_wrapper_module", _mock_wrapper)

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "触发降级并手工接管",
            "context": {"require_evidence": True},
            "execute": True,
            "orchestrate": True,
            "mode": "strict",
            "quality_threshold": 20,
            "max_retries": 0,
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t4",
            "X-Request-ID": "rid-orch-takeover-1",
        },
    )
    assert resp.status_code == 200
    run_id = str(resp.json()["run_id"])

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="advisor-orch-takeover", lease_ttl_seconds=60, role="send"))
    assert ran is True
    run = client.get(f"/v1/advisor/runs/{run_id}")
    child_job_id = str(run.json()["final_job_id"])

    # Force gate failure and degrade.
    _mark_child_completed(env=env, child_job_id=child_job_id, answer="ok")
    degraded = client.post(
        f"/v1/advisor/runs/{run_id}/reconcile",
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t4",
            "X-Request-ID": "rid-orch-takeover-1-reconcile-1",
        },
    )
    assert degraded.status_code == 200
    assert degraded.json()["status"] == "DEGRADED"

    takeover = client.post(
        f"/v1/advisor/runs/{run_id}/takeover",
        json={"note": "人工接管收口", "actor": "pm", "compensation": {"action": "handoff_to_pm"}},
    )
    assert takeover.status_code == 200
    assert takeover.json()["status"] == "MANUAL_TAKEOVER"

    replay = client.get(f"/v1/advisor/runs/{run_id}/replay?persist=1")
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["persisted"] is True
    assert replay_body["replay"]["status"] == "MANUAL_TAKEOVER"
    assert isinstance(replay_body.get("snapshot_path"), str) and replay_body["snapshot_path"]


def test_orchestrate_takeover_honors_write_trace_guards(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(mod, "_load_wrapper_module", _mock_wrapper)
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "触发人工接管护栏",
            "execute": True,
            "orchestrate": True,
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t4-guard",
            "X-Request-ID": "rid-orch-takeover-guard-1",
        },
    )
    assert resp.status_code == 200
    run_id = str(resp.json()["run_id"])

    missing_trace = client.post(
        f"/v1/advisor/runs/{run_id}/takeover",
        json={"note": "人工接管"},
        headers={"X-Client-Name": "chatgptrest-mcp"},
    )
    assert missing_trace.status_code == 400
    assert missing_trace.json()["detail"]["error"] == "missing_trace_headers"


def test_orchestrate_openclaw_required_failure_degrades_run(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as routes_mod
    import chatgptrest.executors.advisor_orchestrate as exec_mod

    monkeypatch.setattr(routes_mod, "_load_wrapper_module", _mock_wrapper)

    class _FailingAdapter:
        def __init__(self, *, url: str, client_name: str = "x", client_version: str = "x"):  # noqa: ARG002
            self.url = url

        def run_protocol(self, *, run_id: str, step_id: str, question: str, params: dict):  # noqa: ARG002
            raise exec_mod.OpenClawAdapterError("sessions_spawn", "simulated failure")

    monkeypatch.setattr(exec_mod, "OpenClawAdapter", _FailingAdapter)

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "需要 openclaw",
            "execute": True,
            "orchestrate": True,
            "agent_options": {
                "openclaw_mcp_url": "http://127.0.0.1:18801/mcp",
                "openclaw_required": True,
            },
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "t5",
            "X-Request-ID": "rid-orch-openclaw-fail-1",
        },
    )
    assert resp.status_code == 200
    run_id = str(resp.json()["run_id"])

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="advisor-orch-openclaw", lease_ttl_seconds=60, role="send"))
    assert ran is True
    run = client.get(f"/v1/advisor/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["status"] == "DEGRADED"
