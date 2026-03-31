from __future__ import annotations

import time
from pathlib import Path

import pytest

from chatgptrest.core import advisor_runs
from chatgptrest.core.db import connect


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_reclaim_expired_leases_marks_step_retry_wait(env: dict[str, Path]) -> None:
    run_id = advisor_runs.new_run_id()
    now = time.time()
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        advisor_runs.create_run(
            conn,
            run_id=run_id,
            request_id="rid-lease-1",
            mode="balanced",
            status="RUNNING",
            route="chatgpt_pro",
            raw_question="q",
            normalized_question="q",
            context={},
            quality_threshold=17,
            crosscheck=False,
            max_retries=1,
            orchestrate_job_id="j_parent",
            final_job_id="j_child",
        )
        advisor_runs.upsert_step(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            step_type="ask",
            status="EXECUTING",
            attempt=1,
            job_id="j_child",
            lease_id="l_1",
            lease_expires_at=now - 1,
            input_obj={"kind": "chatgpt_web.ask"},
            output_obj={},
        )
        advisor_runs.upsert_lease(
            conn,
            lease_id="l_1",
            run_id=run_id,
            step_id="ask_primary",
            owner="job:j_parent",
            token="l_1",
            status="leased",
            expires_at=now - 1,
            heartbeat_at=now - 2,
        )
        reclaimed = advisor_runs.reclaim_expired_leases(conn, run_id=run_id, now_ts=now)
        conn.commit()
    assert len(reclaimed) == 1
    with connect(env["db_path"]) as conn:
        step = advisor_runs.get_step(conn, run_id=run_id, step_id="ask_primary")
        assert step is not None
        assert step["status"] == "RETRY_WAIT"
        leases = advisor_runs.list_leases(conn, run_id=run_id)
        assert leases and leases[0]["status"] == "expired"
        events, _ = advisor_runs.list_events(conn, run_id=run_id, after_id=0, limit=100)
        assert any(ev["type"] == "step.failed" for ev in events)


def test_replay_run_reconstructs_manual_takeover(env: dict[str, Path]) -> None:
    run_id = advisor_runs.new_run_id()
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        advisor_runs.create_run(
            conn,
            run_id=run_id,
            request_id="rid-replay-1",
            mode="strict",
            status="PLAN_COMPILED",
            route="chatgpt_pro",
            raw_question="q",
            normalized_question="q",
            context={},
            quality_threshold=20,
            crosscheck=False,
            max_retries=0,
            orchestrate_job_id="job_orch",
            final_job_id=None,
        )
        advisor_runs.append_event(conn, run_id=run_id, type="run.created", payload={"run_id": run_id})
        advisor_runs.append_event(conn, run_id=run_id, type="run.planned", payload={"run_id": run_id})
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            type="step.dispatched",
            attempt=1,
            payload={"step_id": "ask_primary", "attempt": 1, "job_id": "job_child_1"},
        )
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            type="step.started",
            attempt=1,
            payload={"step_id": "ask_primary", "attempt": 1, "job_id": "job_child_1"},
        )
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            type="gate.failed",
            attempt=1,
            payload={"step_id": "ask_primary", "attempt": 1},
        )
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            type="run.degraded",
            payload={"reason_type": "GateFailed", "reason": "quality gate failed"},
        )
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            step_id="manual_takeover",
            type="step.compensated",
            attempt=1,
            payload={"step_id": "manual_takeover", "attempt": 1},
        )
        advisor_runs.append_event(
            conn,
            run_id=run_id,
            type="run.taken_over",
            payload={"actor": "pm"},
        )
        replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=True)
        conn.commit()

    assert replay is not None
    assert replay["status"] == "MANUAL_TAKEOVER"
    assert replay["degraded"] is True
    assert any(s["step_id"] == "manual_takeover" and s["status"] == "COMPENSATED" for s in replay["steps"])
    with connect(env["db_path"]) as conn:
        run = advisor_runs.get_run(conn, run_id=run_id)
    assert run is not None
    assert run["status"] == "MANUAL_TAKEOVER"
