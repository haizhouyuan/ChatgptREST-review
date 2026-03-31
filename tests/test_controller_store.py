from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.controller import store
from chatgptrest.core.db import connect


def test_controller_store_snapshot_includes_objective_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))

    with connect(tmp_path / "jobdb.sqlite3") as conn:
        conn.execute("BEGIN IMMEDIATE")
        store.upsert_run(
            conn,
            run_id="run-objective",
            trace_id="trace-objective",
            request_id="req-objective",
            execution_mode="async",
            controller_status="WAITING_HUMAN",
            objective_text="Ship the rollout plan",
            objective_kind="artifact_delivery",
            success_criteria=[{"type": "artifact_written", "value": True}],
            constraints=[{"type": "repo", "value": "ChatgptREST"}],
            delivery_target={"channel": "api", "mode": "decision_ready"},
            current_work_id="deliver",
            blocked_reason="awaiting approval",
            plan_version=2,
            plan_obj={"steps": [{"work_id": "deliver"}]},
            delivery_obj={"status": "waiting_human"},
            next_action_obj={"type": "await_human_checkpoint"},
        )
        store.upsert_work_item(
            conn,
            run_id="run-objective",
            work_id="deliver",
            title="Deliver the rollout plan",
            kind="delivery",
            status="WAITING_HUMAN",
            owner="controller",
            lane="delivery",
            output_obj={"status": "waiting_human"},
        )
        store.upsert_checkpoint(
            conn,
            run_id="run-objective",
            checkpoint_id="cp-objective",
            title="Approve rollout",
            status="NEEDS_HUMAN",
            blocking=True,
            details_obj={"team_gate": True},
        )
        store.upsert_artifact(
            conn,
            run_id="run-objective",
            artifact_id="artifact-objective",
            work_id="deliver",
            kind="plan",
            title="Rollout plan",
            metadata_obj={"path": "report.md"},
        )
        conn.commit()

    with connect(tmp_path / "jobdb.sqlite3") as conn:
        snapshot = store.snapshot_run(conn, run_id="run-objective")

    assert snapshot is not None
    assert snapshot["run"]["objective_text"] == "Ship the rollout plan"
    assert snapshot["run"]["objective_kind"] == "artifact_delivery"
    assert snapshot["run"]["plan_version"] == 2
    assert snapshot["run"]["blocked_reason"] == "awaiting approval"
    assert snapshot["run"]["delivery_target"]["mode"] == "decision_ready"
    assert snapshot["checkpoints"][0]["status"] == "NEEDS_HUMAN"
    assert snapshot["artifacts"][0]["artifact_id"] == "artifact-objective"
    json.dumps(snapshot, ensure_ascii=False)


def test_controller_store_transition_updates_status_and_next_action_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))

    with connect(tmp_path / "jobdb.sqlite3") as conn:
        conn.execute("BEGIN IMMEDIATE")
        store.upsert_run(
            conn,
            run_id="run-transition",
            trace_id="trace-transition",
            request_id="req-transition",
            execution_mode="async",
            controller_status="WAITING_EXTERNAL",
            objective_text="Resolve the incident",
            objective_kind="answer",
            current_work_id="execute",
            next_action_obj={"type": "await_job_completion", "status": "pending"},
        )
        store.upsert_work_item(
            conn,
            run_id="run-transition",
            work_id="execute",
            title="Execute the route",
            kind="execution",
            status="QUEUED",
            owner="controller",
            lane="chatgpt",
            job_id="job-transition",
        )
        conn.commit()

    with connect(tmp_path / "jobdb.sqlite3") as conn:
        conn.execute("BEGIN IMMEDIATE")
        store.upsert_run(
            conn,
            run_id="run-transition",
            trace_id=None,
            request_id=None,
            execution_mode="async",
            controller_status="DELIVERED",
            current_work_id=None,
            next_action_obj={"type": "await_user_followup", "status": "optional"},
            delivery_obj={"status": "completed", "summary": "done"},
        )
        store.upsert_work_item(
            conn,
            run_id="run-transition",
            work_id="execute",
            title="Execute the route",
            kind="execution",
            status="COMPLETED",
            owner="controller",
            lane="chatgpt",
            job_id="job-transition",
            output_obj={"job_status": "completed"},
        )
        conn.commit()

    with connect(tmp_path / "jobdb.sqlite3") as conn:
        snapshot = store.snapshot_run(conn, run_id="run-transition")

    assert snapshot is not None
    assert snapshot["run"]["controller_status"] == "DELIVERED"
    assert snapshot["run"]["current_work_id"] is None
    assert snapshot["run"]["next_action"]["type"] == "await_user_followup"
    assert snapshot["work_items"][0]["status"] == "COMPLETED"
