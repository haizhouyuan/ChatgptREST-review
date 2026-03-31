from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import chatgptrest.api.routes_advisor_v3 as routes_advisor_v3
from chatgptrest.api.app import create_app
from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.core.incidents import (
    ACTION_STATUS_COMPLETED,
    INCIDENT_STATUS_OPEN,
    create_action,
    create_incident,
    fingerprint_hash,
)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_ops_pause_get_set_and_job_deferred(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    r0 = client.get("/v1/ops/pause")
    assert r0.status_code == 200
    assert r0.json()["mode"] == "none"
    assert r0.json()["active"] is False

    r1 = client.post("/v1/ops/pause", json={"mode": "send", "duration_seconds": 60, "reason": "test"})
    assert r1.status_code == 200
    assert r1.json()["mode"] == "send"
    assert r1.json()["active"] is True
    assert r1.json()["seconds_remaining"] > 0

    j = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "ops-pause-defer-1"},
    )
    assert j.status_code == 200
    job = j.json()
    assert job["status"] == "queued"
    assert job["action_hint"] == "wait_or_poll_send_queue"
    assert job["not_before"] is not None
    assert job["retry_after_seconds"] is not None
    assert job["retry_after_seconds"] > 0

    ev = client.get(f"/v1/jobs/{job['job_id']}/events?after_id=0&limit=50")
    assert ev.status_code == 200
    types = [e["type"] for e in ev.json()["events"]]
    assert "job_deferred_by_pause" in types

    all_ev = client.get("/v1/ops/events?after_id=0&limit=200")
    assert all_ev.status_code == 200
    assert any(e["job_id"] == job["job_id"] for e in all_ev.json()["events"])


def test_runtime_contract_health_surfaces_machine_readable_contract(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "token-123")
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp,planning-wrapper")

    app = create_app()
    client = TestClient(app)

    r1 = client.get("/health/runtime-contract")
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["runtime_contract_ok"] is True
    assert body1["service_identity"] == "chatgptrest-mcp"
    assert body1["allowlist_enforced"] is True
    assert body1["allowlisted"] is True
    assert body1["completion_contract_version"] == "v1"
    assert body1["mcp_surface_version"] == "public-advisor-agent-mcp-v1"

    r2 = client.get("/v1/health/runtime-contract")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["runtime_contract_ok"] is True
    assert body2["service_identity"] == "chatgptrest-mcp"


def test_ops_unpause_wakes_deferred_jobs_only(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    # Job B: not deferred by pause (created before pause), then manually scheduled into the future.
    jb = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "before"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "ops-unpause-job-b"},
    )
    assert jb.status_code == 200
    job_b_id = jb.json()["job_id"]
    future_ts = time.time() + 24 * 60 * 60
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE jobs SET not_before = ? WHERE job_id = ?", (float(future_ts), str(job_b_id)))
        conn.commit()

    # Pause, then create job A which gets deferred by pause at enqueue time.
    r1 = client.post("/v1/ops/pause", json={"mode": "send", "duration_seconds": 3600, "reason": "test"})
    assert r1.status_code == 200
    ja = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "after"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "ops-unpause-job-a"},
    )
    assert ja.status_code == 200
    job_a_id = ja.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row_a = conn.execute("SELECT not_before FROM jobs WHERE job_id = ?", (str(job_a_id),)).fetchone()
        row_b = conn.execute("SELECT not_before FROM jobs WHERE job_id = ?", (str(job_b_id),)).fetchone()
    assert row_a is not None and float(row_a["not_before"] or 0.0) > time.time() + 60
    assert row_b is not None and abs(float(row_b["not_before"]) - float(future_ts)) < 1.0

    # Unpause should wake job A but must not touch job B.
    r2 = client.post("/v1/ops/pause", json={"mode": "none"})
    assert r2.status_code == 200

    with connect(env["db_path"]) as conn:
        row_a2 = conn.execute("SELECT not_before FROM jobs WHERE job_id = ?", (str(job_a_id),)).fetchone()
        row_b2 = conn.execute("SELECT not_before FROM jobs WHERE job_id = ?", (str(job_b_id),)).fetchone()
    assert row_a2 is not None and float(row_a2["not_before"] or 0.0) <= time.time() + 2.0
    assert row_b2 is not None and abs(float(row_b2["not_before"]) - float(future_ts)) < 1.0


def test_ops_idempotency_lookup_and_jobs_list(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "idem-lookup-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    idem = client.get("/v1/ops/idempotency/idem-lookup-1")
    assert idem.status_code == 200
    assert idem.json()["job_id"] == job_id

    jobs = client.get("/v1/ops/jobs?limit=50")
    assert jobs.status_code == 200
    found = next((j for j in jobs.json()["jobs"] if j["job_id"] == job_id), None)
    assert found is not None
    assert found["action_hint"] in {"wait_or_poll_send_queue", "wait_for_completion", "wait_for_completion_or_fetch_conversation"}


def test_ops_incidents_and_actions(env: dict[str, Path]):
    now = time.time()
    inc_id = "inc-1"
    sig = "test_signature"
    fp = fingerprint_hash(sig)
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        create_incident(
            conn,
            incident_id=inc_id,
            fingerprint=fp,
            signature=sig,
            category="test",
            severity="P2",
            now=now,
            job_ids=["job-x"],
            evidence_dir="jobs/job-x/evidence",
        )
        create_action(
            conn,
            incident_id=inc_id,
            action_type="test_action",
            status=ACTION_STATUS_COMPLETED,
            risk_level="low",
            now=now,
            result={"ok": True},
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)

    lst = client.get("/v1/ops/incidents?status=active&limit=50")
    assert lst.status_code == 200
    assert any(x["incident_id"] == inc_id for x in lst.json()["incidents"])

    one = client.get(f"/v1/ops/incidents/{inc_id}")
    assert one.status_code == 200
    assert one.json()["incident_id"] == inc_id
    assert one.json()["status"] == INCIDENT_STATUS_OPEN

    acts = client.get(f"/v1/ops/incidents/{inc_id}/actions?limit=50")
    assert acts.status_code == 200
    assert acts.json()["incident_id"] == inc_id
    assert any(a["action_type"] == "test_action" for a in acts.json()["actions"])

    status = client.get("/v1/ops/status")
    assert status.status_code == 200
    assert status.json()["active_incidents"] >= 1


def test_ops_status_surfaces_issue_family_wait_and_ui_canary_attention(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    fixed_now = 50_000.0
    monkeypatch.setenv("CHATGPTREST_OPS_STUCK_WAIT_SECONDS", "240")
    monkeypatch.setattr(time, "time", lambda: fixed_now)

    ui_dir = env["artifacts_dir"] / "monitor" / "ui_canary"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "latest.json").write_text(
        json.dumps(
            {
                "providers": [
                    {"provider": "chatgpt", "ok": True},
                    {"provider": "gemini", "ok": False, "consecutive_failures": 2, "threshold": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        issue, _, _ = client_issues.report_issue(
            conn,
            project="chatgptrest-mcp",
            title="Gemini wait handoff still stuck",
            severity="P1",
            kind="gemini_web.ask",
            symptom="WaitNoThreadUrlTimeout",
            source="worker_auto",
            job_id="job_wait_stuck",
            now=fixed_now - 60,
            metadata={"family_id": "gemini_wait_handoff"},
        )
        create_incident(
            conn,
            incident_id="inc-stuck",
            fingerprint=fingerprint_hash("stuck:gemini:wait"),
            signature="stuck:gemini:wait",
            category="stuck",
            severity="P1",
            now=fixed_now - 30,
            job_ids=["job_wait_stuck"],
        )
        conn.execute(
            """
            INSERT INTO jobs(
              job_id, kind, input_json, params_json, client_json, phase, status,
              created_at, updated_at, not_before, attempts, max_attempts,
              lease_owner, lease_expires_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "job_wait_stuck",
                "gemini_web.ask",
                "{\"question\":\"继续研究\"}",
                "{}",
                "{\"name\":\"chatgptrest-mcp\"}",
                "wait",
                "in_progress",
                fixed_now - 600,
                fixed_now - 600,
                0.0,
                1,
                3,
                "worker-wait",
                fixed_now + 120.0,
            ),
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)
    status = client.get("/v1/ops/status")
    assert status.status_code == 200
    body = status.json()
    assert body["active_incidents"] == 1
    assert body["active_incident_families"] == 1
    assert body["active_open_issues"] == 1
    assert body["active_issue_families"] == 1
    assert body["stuck_wait_jobs"] == 1
    assert body["ui_canary_ok"] is False
    assert body["ui_canary_failed_providers"] == ["gemini"]
    assert set(body["attention_reasons"]) == {
        "active_incidents",
        "active_open_issues",
        "stuck_wait_jobs",
        "ui_canary_failed",
    }
    assert issue.issue_id


def test_ops_status_ignores_ui_canary_failures_below_threshold(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    fixed_now = 60_000.0
    monkeypatch.setattr(time, "time", lambda: fixed_now)

    ui_dir = env["artifacts_dir"] / "monitor" / "ui_canary"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "latest.json").write_text(
        json.dumps(
            {
                "providers": [
                    {"provider": "chatgpt", "ok": True, "consecutive_failures": 0, "threshold": 2},
                    {"provider": "gemini", "ok": False, "consecutive_failures": 1, "threshold": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    client = TestClient(app)
    status = client.get("/v1/ops/status")
    assert status.status_code == 200
    body = status.json()
    assert body["ui_canary_ok"] is True
    assert body["ui_canary_failed_providers"] == []
    assert "ui_canary_failed" not in body["attention_reasons"]


def test_ops_status_separates_stale_backlog_from_true_stuck_wait(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    fixed_now = 300_000.0
    monkeypatch.setenv("CHATGPTREST_OPS_STUCK_WAIT_SECONDS", "240")
    monkeypatch.setattr(time, "time", lambda: fixed_now)

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            """
            INSERT INTO jobs(
              job_id, kind, input_json, params_json, client_json, phase, status,
              created_at, updated_at, not_before, attempts, max_attempts,
              lease_owner, lease_expires_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    "job_stale_backlog",
                    "gemini_web.ask",
                    "{\"question\":\"继续研究\"}",
                    "{}",
                    "{\"name\":\"chatgptrest-mcp\"}",
                    "wait",
                    "needs_followup",
                    fixed_now - 200_000,
                    fixed_now - 200_000,
                    0.0,
                    1,
                    3,
                    None,
                    None,
                ),
                (
                    "job_queued_wait",
                    "gemini_web.ask",
                    "{\"question\":\"继续等待\"}",
                    "{}",
                    "{\"name\":\"chatgptrest-mcp\"}",
                    "wait",
                    "in_progress",
                    fixed_now - 1_800,
                    fixed_now - 600,
                    0.0,
                    1,
                    3,
                    None,
                    None,
                ),
                (
                    "job_leased_wait",
                    "gemini_web.ask",
                    "{\"question\":\"真正卡住\"}",
                    "{}",
                    "{\"name\":\"chatgptrest-mcp\"}",
                    "wait",
                    "in_progress",
                    fixed_now - 1_800,
                    fixed_now - 600,
                    0.0,
                    1,
                    3,
                    "worker-wait",
                    fixed_now + 120.0,
                ),
            ],
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)
    status = client.get("/v1/ops/status")
    assert status.status_code == 200
    body = status.json()
    assert body["jobs_by_status"]["in_progress"] == 2
    assert body["raw_jobs_by_status"]["needs_followup"] == 1
    assert body["stale_jobs_by_status"]["needs_followup"] == 1
    assert body["stale_jobs_total"] == 1
    assert body["stuck_wait_jobs"] == 1
    assert "stale_backlog" in body["attention_reasons"]


def test_ops_incidents_pagination_tie_breaker(env: dict[str, Path]):
    fixed_ts = 1234567.0
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        create_incident(
            conn,
            incident_id="i1",
            fingerprint=fingerprint_hash("s1"),
            signature="s1",
            category="test",
            severity="P2",
            now=fixed_ts,
        )
        create_incident(
            conn,
            incident_id="i2",
            fingerprint=fingerprint_hash("s2"),
            signature="s2",
            category="test",
            severity="P2",
            now=fixed_ts,
        )
        create_incident(
            conn,
            incident_id="i3",
            fingerprint=fingerprint_hash("s3"),
            signature="s3",
            category="test",
            severity="P2",
            now=fixed_ts,
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)

    p1 = client.get("/v1/ops/incidents?limit=2")
    assert p1.status_code == 200
    body1 = p1.json()
    got1 = [x["incident_id"] for x in body1["incidents"]]
    assert got1 == ["i3", "i2"]
    assert body1["next_before_ts"] == fixed_ts
    assert body1["next_before_incident_id"] == "i2"

    p2 = client.get(
        f"/v1/ops/incidents?limit=2&before_ts={body1['next_before_ts']}&before_incident_id={body1['next_before_incident_id']}"
    )
    assert p2.status_code == 200
    body2 = p2.json()
    got2 = [x["incident_id"] for x in body2["incidents"]]
    assert got2 == ["i1"]


def test_ops_token_can_be_separate_from_api_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    app = create_app()
    client = TestClient(app)

    # Probe endpoints stay unauthenticated.
    r1 = client.get("/healthz")
    assert r1.status_code == 200
    r2 = client.get("/health")
    assert r2.status_code == 200

    # Other non-ops v1 endpoints still require the API token.
    r3 = client.get("/v1/health")
    assert r3.status_code == 401
    r4 = client.get("/v1/health", headers={"Authorization": "Bearer api-token"})
    assert r4.status_code == 200

    # Ops endpoints require the ops token.
    r5 = client.get("/v1/ops/status", headers={"Authorization": "Bearer api-token"})
    assert r5.status_code == 401
    r6 = client.get("/v1/ops/status", headers={"Authorization": "Bearer ops-token"})
    assert r6.status_code == 200


def test_probe_endpoints_are_exempt_from_global_bearer_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("CHATGPTREST_DRIVER_URL", "http://127.0.0.1:1/mcp")

    app = create_app()
    client = TestClient(app)

    r1 = client.get("/healthz")
    assert r1.status_code == 200
    r2 = client.get("/health")
    assert r2.status_code == 200
    r3 = client.get("/livez")
    assert r3.status_code == 200
    r4 = client.get("/readyz")
    assert r4.status_code == 503


def test_v2_routes_keep_openmind_auth_when_global_bearer_is_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-token")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r1 = client.get("/v2/advisor/dashboard")
    assert r1.status_code == 401

    r2 = client.get("/v2/advisor/dashboard", headers={"X-Api-Key": "openmind-token"})
    assert r2.status_code != 401


def test_readyz_reports_driver_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_DRIVER_URL", "http://127.0.0.1:1/mcp")

    app = create_app()
    client = TestClient(app)

    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["detail"]["status"] == "not_ready"
    assert r.json()["detail"]["checks"]["driver"]["ok"] is False


def test_readyz_returns_ready_when_driver_port_is_reachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    host, port = sock.getsockname()
    monkeypatch.setenv("CHATGPTREST_DRIVER_URL", f"http://{host}:{port}/mcp")

    app = create_app()
    client = TestClient(app)
    try:
        r = client.get("/readyz")
    finally:
        sock.close()

    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["checks"]["driver"]["ok"] is True
    assert r.json()["checks"]["startup"]["ok"] is True


def test_readyz_reports_startup_router_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    host, port = sock.getsockname()
    monkeypatch.setenv("CHATGPTREST_DRIVER_URL", f"http://{host}:{port}/mcp")

    original = routes_advisor_v3.make_v3_advisor_router

    def _boom():
        raise RuntimeError("router boot failed")

    monkeypatch.setattr(routes_advisor_v3, "make_v3_advisor_router", _boom)
    try:
        app = create_app()
        client = TestClient(app)
        response = client.get("/readyz")
    finally:
        monkeypatch.setattr(routes_advisor_v3, "make_v3_advisor_router", original)
        sock.close()

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "not_ready"
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["driver"]["ok"] is True
    assert body["checks"]["startup"]["ok"] is False
    assert body["checks"]["startup"]["status"] == "router_load_failed"
    assert body["checks"]["startup"]["router_load_errors"][0]["name"] == "advisor_v3"


def test_livez_stays_green_when_readiness_dependencies_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_DRIVER_URL", "http://127.0.0.1:1/mcp")

    app = create_app()
    client = TestClient(app)

    live = client.get("/livez")
    health = client.get("/healthz")
    ready = client.get("/readyz")

    assert live.status_code == 200
    assert live.json()["status"] == "live"
    assert health.status_code == 200
    assert ready.status_code == 503


def test_livez_does_not_mask_healthz_database_failure(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    app = create_app()
    client = TestClient(app)

    def _broken_connect(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("chatgptrest.api.routes_jobs.connect", _broken_connect)

    live = client.get("/livez")
    health = client.get("/healthz")

    assert live.status_code == 200
    assert live.json()["status"] == "live"
    assert health.status_code == 503
    assert health.json()["detail"]["status"] == "error"
    assert health.json()["detail"]["error_type"] == "RuntimeError"
