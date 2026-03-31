from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.codex_runner import CodexExecResult
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core import client_issues, job_store
from chatgptrest.executors import sre as sre_exec
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    lanes_dir = tmp_path / "sre_lanes"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SRE_LANES_DIR", str(lanes_dir))
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir, "lanes_dir": lanes_dir}


def _auth_headers(idempotency_key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer ops-token",
        "Idempotency-Key": idempotency_key,
    }


def _create_completed_dummy_job(client: TestClient) -> str:
    created = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 1}},
        headers=_auth_headers("dummy-target"),
    )
    assert created.status_code == 200
    target_job_id = created.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="dummy-1", lease_ttl_seconds=60, kind_prefix="dummy."))
    assert ran is True
    return target_job_id


def _report_issue(db_path: Path, *, job_id: str, symptom: str) -> str:
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title="SRE routing regression",
            severity="P1",
            kind="job_error",
            symptom=symptom,
            job_id=job_id,
            source="pytest",
        )
        conn.commit()
        return issue.issue_id


def _write_bootstrap_packet(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "purpose": "Memory-oriented packet for openmind x openclaw maintagent",
        "entrypoint_markdown": "/vol1/maint/docs/2026-03-15_maintagent_memory_index.md",
        "machine_snapshot_markdown": "/vol1/maint/docs/2026-03-15_maintagent_machine_snapshot.md",
        "repo_snapshot_markdown": "/vol1/maint/docs/2026-03-15_maintagent_repo_workspace_snapshot.md",
        "highlights": {
            "machine": {"hostname": "YogaS2", "root_fs": "/dev/nvme0n1p2 ext4 63G used 85%"},
            "workspace": {"repo_or_worktree_count": 73},
        },
        "known_drifts": ["AGENTS.md still describes memory as 24GB, but live observation shows about 32GB installed."],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_sre_fix_request_creates_open_pr_followup(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)
    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="dummy job needs code fix")

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": True, "ok": True, "query": kwargs.get("query"), "markdown": "process: test"},
    )

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=12,
            cmd=["codex", "exec"],
            output={
                "summary": "Need a code-level fix.",
                "root_cause": "Router logic must change.",
                "route": "repair.open_pr",
                "confidence": "high",
                "rationale": "Runtime actions cannot solve this.",
                "open_pr": {"mode": "p0", "instructions": "Patch the failing router path.", "run_tests": False},
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_codex_exec_with_schema)

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {
                "issue_id": issue_id,
                "job_id": target_job_id,
                "symptom": "dummy job needs code fix",
                "instructions": "Prefer a minimal patch proposal.",
            },
            "params": {"route_mode": "auto_best_effort", "open_pr_mode": "p0"},
        },
        headers=_auth_headers("sre-open-pr"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-1", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    job = client.get(f"/v1/jobs/{fix_job_id}", headers={"Authorization": "Bearer ops-token"}).json()
    assert job["status"] == "completed"

    answer = client.get(
        f"/v1/jobs/{fix_job_id}/answer?offset=0&max_chars=4000",
        headers={"Authorization": "Bearer ops-token"},
    ).json()["chunk"]
    assert "repair.open_pr" in answer

    report_path = env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["decision"]["route"] == "repair.open_pr"
    assert report["downstream"]["kind"] == "repair.open_pr"

    with connect(env["db_path"]) as conn:
        pr_row = conn.execute(
            "SELECT kind, status FROM jobs WHERE kind = 'repair.open_pr' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert pr_row is not None
        assert str(pr_row["status"]) == "queued"
        issue = client_issues.get_issue(conn, issue_id=issue_id)
        assert issue is not None
        assert issue.latest_job_id == target_job_id
        assert issue.latest_artifacts_path == "jobs/" + fix_job_id + "/sre_fix_report.json"


def test_gemini_import_lane_unavailable_does_not_route_runtime_fix() -> None:
    decision = sre_exec._heuristic_runtime_fix_decision(
        kind="gemini_web.ask",
        status="error",
        error_type="GeminiImportCodeUnavailable",
        error="Gemini import code unavailable: Cannot find Gemini Tools button: element is not enabled",
    )

    assert decision is not None
    assert decision["route"] == "manual"
    assert decision["runtime_fix"] == {}
    assert "repo-import" in decision["summary"].lower()


def test_sre_fix_request_resumes_lane_and_routes_runtime_fix(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)
    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="dummy job needs runtime fix")

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    calls = {"fresh": 0, "resume": 0}

    def fake_fresh(**kwargs):  # noqa: ANN003
        calls["fresh"] += 1
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=5,
            cmd=["codex", "exec"],
            output={
                "summary": "First pass diagnosis only.",
                "root_cause": "Need more runtime confirmation.",
                "route": "manual",
                "confidence": "medium",
                "rationale": "Keep the lane warm before routing.",
            },
        )

    def fake_resume(**kwargs):  # noqa: ANN003
        calls["resume"] += 1
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=6,
            cmd=["codex", "exec", "resume"],
            output={
                "summary": "Driver reset should fix it.",
                "root_cause": "The target path is blocked on driver state.",
                "route": "repair.autofix",
                "confidence": "high",
                "rationale": "A guarded runtime reset is enough.",
                "runtime_fix": {"allow_actions": ["restart_driver"], "max_risk": "low", "reason": "Reset driver"},
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_fresh)
    monkeypatch.setattr(sre_exec, "codex_resume_last_message_json", fake_resume)

    first = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "dummy job needs runtime fix"},
            "params": {"route_mode": "plan_only"},
        },
        headers=_auth_headers("sre-first"),
    )
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]

    ran_first = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-2", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran_first is True

    second = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "dummy job needs runtime fix"},
            "params": {
                "route_mode": "auto_best_effort",
                "runtime_max_risk": "low",
                "runtime_apply_actions": False,
            },
        },
        headers=_auth_headers("sre-second"),
    )
    assert second.status_code == 200
    second_job_id = second.json()["job_id"]

    ran_second = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-3", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran_second is True

    assert calls == {"fresh": 1, "resume": 1}

    second_report_path = env["artifacts_dir"] / "jobs" / second_job_id / "sre_fix_report.json"
    assert second_report_path.exists()
    second_report = json.loads(second_report_path.read_text(encoding="utf-8"))
    assert second_report["runner_mode"] == "resume"
    assert second_report["downstream"]["kind"] == "repair.autofix"

    with connect(env["db_path"]) as conn:
        runtime_row = conn.execute(
            "SELECT kind, status FROM jobs WHERE kind = 'repair.autofix' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert runtime_row is not None
        assert str(runtime_row["status"]) == "queued"

    lane_dirs = sorted(p.name for p in env["lanes_dir"].iterdir() if p.is_dir())
    assert lane_dirs
    history_path = env["lanes_dir"] / lane_dirs[0] / "decision_history.jsonl"
    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 2
    assert first_job_id in history_lines[0]


def test_sre_fix_request_injects_bootstrap_memory(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet_path = _write_bootstrap_packet(env["artifacts_dir"] / "maintagent_memory_packet_2026-03-15.json")
    monkeypatch.setenv("CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET", str(packet_path))

    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)
    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="dummy job needs diagnosis")

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    captured: dict[str, str] = {}

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        captured["prompt"] = str(kwargs.get("prompt") or "")
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=8,
            cmd=["codex", "exec"],
            output={
                "summary": "Need operator review.",
                "root_cause": "Collect more evidence first.",
                "route": "manual",
                "confidence": "medium",
                "rationale": "Bootstrap memory is present, but runtime evidence is still limited.",
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_codex_exec_with_schema)

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "dummy job needs diagnosis"},
            "params": {"route_mode": "plan_only"},
        },
        headers=_auth_headers("sre-bootstrap-memory"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-bootstrap", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    job = client.get(f"/v1/jobs/{fix_job_id}", headers={"Authorization": "Bearer ops-token"}).json()
    assert job["status"] == "completed"
    assert "Maintagent bootstrap memory" in captured["prompt"]
    assert "Maintagent repo memory" in captured["prompt"]
    assert "repo_or_worktree_count=73" in captured["prompt"]
    assert "24GB" in captured["prompt"]

    request_dir = env["lanes_dir"] / f"issue-{issue_id}" / "requests"
    request_files = sorted(request_dir.glob("*.json"))
    assert request_files
    request_payload = json.loads(request_files[-1].read_text(encoding="utf-8"))
    assert request_payload["repo_memory"]["checkout_root"]
    assert request_payload["repo_memory"]["shared_state_root"]
    assert request_payload["repo_memory"]["shared_state_root"] != str(env["lanes_dir"])
    assert any(
        str(path).startswith(request_payload["repo_memory"]["shared_state_root"])
        for path in request_payload["repo_memory"]["key_state_paths"]
    )


def test_sre_fix_request_writes_controller_taskpack_projection(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)
    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="dummy job needs structured controller output")

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=9,
            cmd=["codex", "exec"],
            output={
                "summary": "Need operator review before any repair action.",
                "root_cause": "The incident needs a human decision on scope.",
                "route": "manual",
                "confidence": "medium",
                "rationale": "Keep the lane warm and preserve structured controller state.",
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_codex_exec_with_schema)

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "dummy job needs structured controller output"},
            "params": {"route_mode": "plan_only"},
        },
        headers=_auth_headers("sre-controller-taskpack"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-controller", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    lane_dir = env["lanes_dir"] / f"issue-{issue_id}"
    manifest = json.loads((lane_dir / "lane_manifest.json").read_text(encoding="utf-8"))
    assert manifest["controller_kind"] == "codex_maint"
    assert manifest["controller_phase"] == "manual_required"
    assert manifest["run_kind"] == "issue_maintenance"
    assert Path(manifest["task_pack_projection_path"]).exists()
    assert "codex_maint_attach.py --lane-id" in manifest["operator_attach_command"]

    request_view = json.loads((lane_dir / "taskpack" / "request_view.json").read_text(encoding="utf-8"))
    assert request_view["lane_id"] == f"issue-{issue_id}"
    assert request_view["issue_id"] == issue_id
    assert request_view["target_job_id"] == target_job_id
    assert request_view["acceptance_criteria"]

    allowed_actions_view = json.loads((lane_dir / "taskpack" / "allowed_actions_view.json").read_text(encoding="utf-8"))
    assert allowed_actions_view["lane_id"] == f"issue-{issue_id}"
    assert isinstance(allowed_actions_view["allowed_actions"], list)

    prompt_view = (lane_dir / "taskpack" / "prompt_view.md").read_text(encoding="utf-8")
    assert "incident-scoped repair coordinator" in prompt_view

    report_path = env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["controller"]["kind"] == "codex_maint"
    assert report["controller"]["phase"] == "manual_required"
    assert report["controller"]["operator_attach"]["argv"][-2:] == ["--lane-id", f"issue-{issue_id}"]
    assert report["taskpack"]["request_view"].endswith("/taskpack/request_view.json")
    assert report["decision_path"].endswith(".decision.json")


def test_sre_fix_request_decision_override_routes_runtime_fix_without_codex(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)

    def fail_if_called(**kwargs):  # noqa: ANN003
        raise AssertionError("codex_exec_with_schema should not run for controller decision overrides")

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fail_if_called)
    monkeypatch.setattr(sre_exec, "codex_resume_last_message_json", fail_if_called)

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {
                "incident_id": "inc-override-1",
                "job_id": target_job_id,
                "symptom": "maint daemon fallback wants guarded runtime repair",
            },
            "params": {
                "route_mode": "auto_runtime",
                "decision_override": {
                    "summary": "Use guarded runtime repair.",
                    "root_cause": "Upstream fallback selected runtime autofix.",
                    "route": "repair.autofix",
                    "confidence": "high",
                    "rationale": "This fallback should stay inside the canonical lane.",
                    "runtime_fix": {
                        "allow_actions": ["restart_driver", "capture_ui"],
                        "max_risk": "medium",
                        "reason": "Reset stale runtime state.",
                    },
                },
            },
        },
        headers=_auth_headers("sre-override-runtime"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-override", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    report_path = env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["runner_mode"] == "override"
    assert report["controller"]["decision_source"] == "override"
    assert report["decision"]["route"] == "repair.autofix"
    assert report["downstream"]["kind"] == "repair.autofix"

    lane_dir = env["lanes_dir"] / report["lane_id"]
    manifest = json.loads((lane_dir / "lane_manifest.json").read_text(encoding="utf-8"))
    assert manifest["controller_phase"] == "routed_to_repair_autofix"
    assert manifest["last_decision_source"] == "override"
    assert manifest["current_downstream_job_id"] == report["downstream"]["job_id"]


def test_sre_fix_request_uses_heuristic_fast_path_for_runtime_failures(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET kind = ?, status = ?, phase = ?, last_error_type = ?, last_error = ? WHERE job_id = ?",
            (
                "chatgpt_web.ask",
                "error",
                "send",
                "RuntimeError",
                "CDP connect failed (TargetClosedError: BrowserContext.new_page: Target page, context or browser has been closed).",
                target_job_id,
            ),
        )
        conn.commit()

    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="chatgpt send path failed on closed browser context")

    def should_not_run(**kwargs):  # noqa: ANN003
        raise AssertionError("codex_exec_with_schema should be skipped on heuristic fast path")

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", should_not_run)
    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id},
            "params": {"route_mode": "plan_only"},
        },
        headers=_auth_headers("sre-heuristic-fast-path"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-heuristic", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    report_path = env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["runner_mode"] == "heuristic"
    assert report["decision"]["route"] == "repair.autofix"
    assert "restart_driver" in report["decision"]["runtime_fix"]["allow_actions"]

    with connect(env["db_path"]) as conn:
        issue = client_issues.get_issue(conn, issue_id=issue_id)
        assert issue is not None
        assert issue.latest_job_id == target_job_id


def test_sre_fix_request_reuses_existing_runtime_fix_on_downstream_idempotency_collision(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)
    issue_id = _report_issue(env["db_path"], job_id=target_job_id, symptom="runtime fix needed")

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=5,
            cmd=["codex", "exec"],
            output={
                "summary": "Driver reset should fix it.",
                "root_cause": "The target path is blocked on driver state.",
                "route": "repair.autofix",
                "confidence": "high",
                "rationale": "A guarded runtime reset is enough.",
                "runtime_fix": {"allow_actions": ["restart_driver"], "max_risk": "low", "reason": "Reset driver"},
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_codex_exec_with_schema)

    first = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "first symptom"},
            "params": {"route_mode": "auto_runtime", "runtime_apply_actions": False},
        },
        headers=_auth_headers("sre-runtime-first"),
    )
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]
    assert asyncio.run(_run_once(cfg=load_config(), worker_id="sre-runtime-first", lease_ttl_seconds=60, kind_prefix="sre."))

    with connect(env["db_path"]) as conn:
        existing_repair = conn.execute(
            "SELECT job_id FROM jobs WHERE kind = 'repair.autofix' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert existing_repair is not None
        existing_repair_job_id = str(existing_repair["job_id"])

    second = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue_id, "job_id": target_job_id, "symptom": "second symptom with more detail"},
            "params": {"route_mode": "auto_runtime", "runtime_apply_actions": False},
        },
        headers=_auth_headers("sre-runtime-second"),
    )
    assert second.status_code == 200
    second_job_id = second.json()["job_id"]
    assert asyncio.run(_run_once(cfg=load_config(), worker_id="sre-runtime-second", lease_ttl_seconds=60, kind_prefix="sre."))

    second_report = json.loads(
        (env["artifacts_dir"] / "jobs" / second_job_id / "sre_fix_report.json").read_text(encoding="utf-8")
    )
    assert second_report["decision"]["route"] == "repair.autofix"
    assert second_report["downstream"]["job_id"] == existing_repair_job_id
    assert second_report["downstream"]["idempotency_reused"] is True
    assert "collision" in second_report["downstream"]


def test_sre_fix_request_short_circuits_issue_payload_collision_to_existing_downstream(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)

    with connect(env["db_path"]) as conn:
        failed_sre_job = job_store.create_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            idempotency_key="sre-failed-job",
            kind="sre.fix_request",
            input={"issue_id": "placeholder"},
            params={},
            client={"name": "pytest"},
            max_attempts=1,
            enforce_conversation_single_flight=False,
        )
        conn.execute(
            "UPDATE jobs SET status = 'error', phase = 'send' WHERE job_id = ?",
            (failed_sre_job.job_id,),
        )
        existing_repair = job_store.create_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            idempotency_key="repair-existing",
            kind="repair.autofix",
            input={"job_id": target_job_id},
            params={"apply_actions": False},
            client={"name": "pytest"},
            max_attempts=1,
            enforce_conversation_single_flight=False,
        )
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title="sre.fix_request: MaxAttemptsExceeded",
            severity="P2",
            kind="job_error",
            symptom=f"Job {failed_sre_job.job_id} failed after 3 attempt(s)",
            raw_error=(
                "Reached max_attempts=3 while retrying (cooldown): IdempotencyCollision: "
                f"idempotency_key collision: same key used with different request payload "
                f"(existing_job_id={existing_repair.job_id}, existing_hash=abc123, new_hash=def456)."
            ),
            job_id=failed_sre_job.job_id,
            source="executor_auto",
        )
        conn.commit()

    def should_not_run(**kwargs):  # noqa: ANN003
        raise AssertionError("codex_exec_with_schema should be skipped when issue payload already names the downstream job")

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", should_not_run)
    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"issue_id": issue.issue_id},
            "params": {"route_mode": "auto_runtime", "runtime_apply_actions": False},
        },
        headers=_auth_headers("sre-issue-collision-fast-path"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    assert asyncio.run(_run_once(cfg=load_config(), worker_id="sre-issue-collision", lease_ttl_seconds=60, kind_prefix="sre."))

    report = json.loads((env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json").read_text(encoding="utf-8"))
    assert report["runner_mode"] == "heuristic"
    assert report["decision"]["route"] == "repair.autofix"
    assert "downstream_reuse_from_issue_payload" in report["decision"]["notes"]
    assert report["downstream"]["job_id"] == existing_repair.job_id
    assert report["downstream"]["idempotency_reused"] is True
    assert report["downstream"]["reused_reason"] == "issue_existing_job_id"


def test_sre_fix_request_includes_context_pack_in_prompt_and_artifacts(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    target_job_id = _create_completed_dummy_job(client)

    monkeypatch.setattr(
        sre_exec,
        "_gitnexus_query",
        lambda **kwargs: {"enabled": False, "ok": False, "reason": "disabled", "query": kwargs.get("query")},
    )

    captured: dict[str, str] = {}

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        captured["prompt"] = str(kwargs.get("prompt") or "")
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=5,
            cmd=["codex", "exec"],
            output={
                "summary": "Need operator review.",
                "root_cause": "Use the attached runtime context for diagnosis.",
                "route": "manual",
                "confidence": "medium",
                "rationale": "The supplied context pack is enough for a manual triage decision.",
            },
        )

    monkeypatch.setattr(sre_exec, "codex_exec_with_schema", fake_codex_exec_with_schema)

    context_pack = {
        "recent_failures": [{"job_id": "job-1", "error_type": "WaitNoProgressTimeout"}],
        "system_state": {"driver": "degraded", "chrome": "alive"},
        "repair_history": [{"route": "repair.autofix", "status": "completed"}],
    }
    created = client.post(
        "/v1/jobs",
        json={
            "kind": "sre.fix_request",
            "input": {"job_id": target_job_id, "context_pack": context_pack},
            "params": {"route_mode": "plan_only"},
        },
        headers=_auth_headers("sre-context-pack"),
    )
    assert created.status_code == 200
    fix_job_id = created.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="sre-context-pack", lease_ttl_seconds=60, kind_prefix="sre."))
    assert ran is True

    assert "Provided context pack" in captured["prompt"]
    assert "WaitNoProgressTimeout" in captured["prompt"]
    assert '"driver": "degraded"' in captured["prompt"]

    request_dir = env["lanes_dir"] / f"job-{target_job_id}" / "requests"
    request_files = sorted(request_dir.glob("*.json"))
    assert request_files
    request_payload = json.loads(request_files[-1].read_text(encoding="utf-8"))
    assert request_payload["context_pack"] == context_pack

    report_path = env["artifacts_dir"] / "jobs" / fix_job_id / "sre_fix_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["context_pack"] == context_pack


def test_sre_fix_request_schema_is_strict_object_compatible() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "ops" / "schemas" / "sre_fix_request_decision.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert sorted(schema["required"]) == sorted(schema["properties"].keys())
    runtime_fix = schema["properties"]["runtime_fix"]
    assert sorted(runtime_fix["required"]) == sorted(runtime_fix["properties"].keys())
    open_pr = schema["properties"]["open_pr"]
    assert sorted(open_pr["required"]) == sorted(open_pr["properties"].keys())
