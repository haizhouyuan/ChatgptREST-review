from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

from chatgptrest.core.db import init_db
from chatgptrest.core import job_store


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_codex_input_fingerprint_changes_when_job_row_changes(tmp_path: Path):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "jobs" / "j1").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text(json.dumps({"incident_id": "inc-1"}), encoding="utf-8")
    (inc_dir / "jobs" / "j1" / "job_row.json").write_text(json.dumps({"status": "error"}), encoding="utf-8")

    h1 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001
    (inc_dir / "jobs" / "j1" / "job_row.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")
    h2 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001
    assert h1 != h2


def test_codex_input_fingerprint_changes_when_issues_registry_snapshot_changes(tmp_path: Path):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text(json.dumps({"incident_id": "inc-1"}), encoding="utf-8")

    (inc_dir / "snapshots" / "issues_registry.yaml").write_text("v1", encoding="utf-8")
    h1 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001
    (inc_dir / "snapshots" / "issues_registry.yaml").write_text("v2", encoding="utf-8")
    h2 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001
    assert h1 != h2



def test_codex_input_fingerprint_ignores_codex_manifest_fields(tmp_path: Path):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    inc_dir.mkdir(parents=True, exist_ok=True)

    (inc_dir / "manifest.json").write_text(json.dumps({"incident_id": "inc-1"}), encoding="utf-8")
    h1 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001

    # Simulate maint_daemon writing Codex metadata back into the incident manifest.
    (inc_dir / "manifest.json").write_text(
        json.dumps({"incident_id": "inc-1", "codex_sre": {"last_run_ts": "2026-01-01T00:00:00Z"}}),
        encoding="utf-8",
    )
    h2 = md._codex_input_fingerprint(inc_dir)  # noqa: SLF001
    assert h1 == h2


def test_render_codex_sre_actions_markdown(tmp_path: Path):
    md = _load_maint_daemon_module()
    payload = {
        "summary": "Root cause: CDP is down.",
        "hypotheses": [{"title": "Chrome crashed", "evidence": ["cdp_probe.ok=false"], "confidence": "high"}],
        "actions": [{"name": "restart_chrome", "reason": "CDP not reachable", "risk": "low"}],
        "risks": ["Restarting Chrome may interrupt active sessions."],
        "next_steps": ["Verify http://127.0.0.1:9222/json/version"],
    }
    text = md._render_codex_sre_actions_markdown(payload)  # noqa: SLF001
    assert "Codex SRE report" in text
    assert "restart_chrome" in text


def test_run_codex_sre_analyze_incident_writes_lane_pointer_and_mirror_payload(tmp_path: Path, monkeypatch):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "jobs" / "job-1").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text(
        json.dumps({"incident_id": "inc-1", "sig_hash": "incident-sig-1", "signature": "driver blocked", "job_ids": ["job-1"]}),
        encoding="utf-8",
    )
    (inc_dir / "summary.md").write_text("driver blocked summary", encoding="utf-8")
    (inc_dir / "jobs" / "job-1" / "job_row.json").write_text(
        json.dumps({"job_id": "job-1", "status": "error", "last_error": "blocked"}),
        encoding="utf-8",
    )

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    global_memory_jsonl = tmp_path / "codex_global_memory.jsonl"
    global_memory_md = tmp_path / "codex_global_memory.md"
    global_memory_jsonl.write_text(
        json.dumps({"sig_hash": "incident-sig-1", "top_actions": [{"name": "restart_driver", "reason": "Known good fix."}]}) + "\n",
        encoding="utf-8",
    )
    global_memory_md.write_text("# global memory snapshot\n", encoding="utf-8")
    init_db(db_path)
    captured: dict[str, object] = {}

    def fake_execute_controller(**kwargs):  # noqa: ANN003
        captured["input_obj"] = kwargs.get("input_obj")
        return {
            "lane_id": "incident-inc-1",
            "report": {
                "lane_id": "incident-inc-1",
                "request_path": "/tmp/lane/requests/req.json",
                "prompt_path": "/tmp/lane/codex/prompt.md",
                "decision_path": "/tmp/lane/codex/decision.json",
                "report_path": "/tmp/lane/reports/report.json",
                "task_pack_projection_path": "/tmp/lane/taskpack",
                "controller": {
                    "kind": "codex_maint",
                    "phase": "manual_required",
                },
            },
            "decision": {
                "summary": "Need guarded driver reset.",
                "root_cause": "Driver state is stale.",
                "route": "repair.autofix",
                "confidence": "high",
                "rationale": "A low-risk reset is enough.",
                "runtime_fix": {
                    "allow_actions": ["restart_driver"],
                    "max_risk": "low",
                    "reason": "Reset the stale driver session.",
                },
                "notes": ["Prefer guarded runtime recovery before broader restarts."],
            },
        }

    monkeypatch.setattr(md, "execute_sre_fix_request_controller", fake_execute_controller)

    run_meta = md._run_codex_sre_analyze_incident(  # noqa: SLF001
        repo_root=Path(__file__).resolve().parents[1],
        inc_dir=inc_dir,
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        model="gpt-5",
        timeout_seconds=120,
        global_memory_md=global_memory_md,
        global_memory_jsonl=global_memory_jsonl,
    )

    assert run_meta["ok"] is True
    assert run_meta["artifact_mode"] == "mirror_pointer"
    assert run_meta["target_job_id"] == "job-1"

    actions_payload = json.loads((inc_dir / "codex" / "sre_actions.json").read_text(encoding="utf-8"))
    assert actions_payload["actions"][0]["name"] == "restart_driver"
    assert "incident-inc-1" in json.dumps(actions_payload, ensure_ascii=False)

    pointer_payload = json.loads((inc_dir / "codex" / "source_lane.json").read_text(encoding="utf-8"))
    assert pointer_payload["artifact_mode"] == "mirror_pointer"
    assert pointer_payload["source_lane_id"] == "incident-inc-1"
    assert pointer_payload["canonical_decision_path"] == "/tmp/lane/codex/decision.json"

    input_obj = captured["input_obj"]
    assert isinstance(input_obj, dict)
    context_pack = input_obj.get("context_pack")
    assert isinstance(context_pack, dict)
    assert context_pack["preferred_action_families"]["preferred_actions"][0]["name"] == "restart_driver"
    assert context_pack["global_memory_snapshot_path"] == str(global_memory_md)

    stdout_text = (inc_dir / "codex" / "stdout.txt").read_text(encoding="utf-8")
    assert "mirror/pointer only" in stdout_text
    assert "canonical_report_path=/tmp/lane/reports/report.json" in stdout_text


def test_route_repair_autofix_fallback_via_controller_writes_lane_pointer(tmp_path: Path, monkeypatch):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "jobs" / "job-1").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text(
        json.dumps({"incident_id": "inc-fallback-1", "sig_hash": "incident-sig-fallback", "signature": "driver blocked", "job_ids": ["job-1"]}),
        encoding="utf-8",
    )
    (inc_dir / "summary.md").write_text("driver blocked summary", encoding="utf-8")
    (inc_dir / "jobs" / "job-1" / "job_row.json").write_text(
        json.dumps({"job_id": "job-1", "status": "error", "last_error": "blocked"}),
        encoding="utf-8",
    )

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    global_memory_jsonl = tmp_path / "codex_global_memory.jsonl"
    global_memory_jsonl.write_text(
        json.dumps({"sig_hash": "incident-sig-fallback", "top_actions": [{"name": "restart_driver", "reason": "Known good fix."}]}) + "\n",
        encoding="utf-8",
    )
    init_db(db_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(md, "_source_job_uses_synthetic_or_trivial_prompt", lambda conn, job_id: False)

    def fake_execute_controller(**kwargs):  # noqa: ANN003
        captured["input_obj"] = kwargs.get("input_obj")
        captured["params_obj"] = kwargs.get("params_obj")
        return {
            "lane_id": "incident-inc-fallback-1",
            "report": {
                "lane_id": "incident-inc-fallback-1",
                "request_path": "/tmp/lane/requests/req.json",
                "prompt_path": "/tmp/lane/codex/prompt.md",
                "decision_path": "/tmp/lane/codex/decision.json",
                "report_path": "/tmp/lane/reports/report.json",
                "task_pack_projection_path": "/tmp/lane/taskpack",
                "controller": {
                    "kind": "codex_maint",
                    "phase": "routed_to_repair_autofix",
                },
            },
            "decision": {
                "summary": "Fallback to guarded runtime fix.",
                "root_cause": "Incident analysis did not converge.",
                "route": "repair.autofix",
                "confidence": "medium",
                "rationale": "Keep fallback inside the canonical lane.",
                "runtime_fix": {
                    "allow_actions": ["restart_driver"],
                    "max_risk": "medium",
                    "reason": "Reset the stale driver session.",
                },
                "notes": ["controller_override"],
            },
            "downstream": {
                "kind": "repair.autofix",
                "job_id": "repair-job-1",
                "status": "queued",
            },
        }

    monkeypatch.setattr(md, "execute_sre_fix_request_controller", fake_execute_controller)

    summary = md._route_repair_autofix_fallback_via_controller(  # noqa: SLF001
        inc_dir=inc_dir,
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        target_job_id="job-1",
        signature="driver blocked",
        timeout_seconds=180,
        allow_actions="restart_driver,capture_ui",
        max_risk="medium",
        trigger="codex_sre_failed",
        global_memory_jsonl=global_memory_jsonl,
    )

    assert summary["ok"] is True
    assert summary["lane_id"] == "incident-inc-fallback-1"
    assert summary["downstream"]["job_id"] == "repair-job-1"

    pointer_payload = json.loads((inc_dir / "codex" / "source_lane.json").read_text(encoding="utf-8"))
    assert pointer_payload["artifact_mode"] == "mirror_pointer"
    assert pointer_payload["source_lane_id"] == "incident-inc-fallback-1"
    assert pointer_payload["source"] == "maint_daemon_fallback_controller"

    params_obj = captured["params_obj"]
    assert isinstance(params_obj, dict)
    decision_override = params_obj.get("decision_override")
    assert isinstance(decision_override, dict)
    assert decision_override["route"] == "repair.autofix"
    assert decision_override["notes"][-1] == "codex_sre_failed"

    input_obj = captured["input_obj"]
    assert isinstance(input_obj, dict)
    context_pack = input_obj.get("context_pack")
    assert isinstance(context_pack, dict)
    assert context_pack["preferred_action_families"]["preferred_actions"][0]["name"] == "restart_driver"
    assert "global_memory_snapshot_path" not in context_pack


def test_route_incident_runtime_fix_via_controller_reuses_canonical_decision(tmp_path: Path, monkeypatch):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "codex").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text(
        json.dumps({"incident_id": "inc-runtime-1", "sig_hash": "incident-runtime-1", "signature": "driver blocked"}),
        encoding="utf-8",
    )
    (inc_dir / "summary.md").write_text("driver blocked summary", encoding="utf-8")

    canonical_decision = tmp_path / "lane" / "decision.json"
    canonical_decision.parent.mkdir(parents=True, exist_ok=True)
    canonical_decision.write_text(
        json.dumps(
            {
                "summary": "Use guarded runtime repair.",
                "root_cause": "Driver state is stale.",
                "route": "repair.autofix",
                "confidence": "high",
                "rationale": "A low-risk reset is enough.",
                "runtime_fix": {
                    "allow_actions": ["restart_driver"],
                    "max_risk": "low",
                    "reason": "Reset the stale driver session.",
                },
            }
        ),
        encoding="utf-8",
    )
    (inc_dir / "codex" / "source_lane.json").write_text(
        json.dumps(
            {
                "artifact_mode": "mirror_pointer",
                "source_lane_id": "incident-inc-runtime-1",
                "canonical_decision_path": str(canonical_decision),
            }
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)
    captured: dict[str, object] = {}

    def fake_execute_controller(**kwargs):  # noqa: ANN003
        captured["input_obj"] = kwargs.get("input_obj")
        captured["params_obj"] = kwargs.get("params_obj")
        return {
            "lane_id": "incident-inc-runtime-1",
            "report": {
                "lane_id": "incident-inc-runtime-1",
                "decision_path": "/tmp/lane/codex/decision.json",
                "report_path": "/tmp/lane/reports/report.json",
                "controller": {"kind": "codex_maint", "phase": "routed_to_repair_autofix"},
            },
            "downstream": {"kind": "repair.autofix", "job_id": "repair-job-runtime", "status": "queued"},
        }

    monkeypatch.setattr(md, "execute_sre_fix_request_controller", fake_execute_controller)

    summary = md._route_incident_runtime_fix_via_controller(  # noqa: SLF001
        inc_dir=inc_dir,
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        target_job_id="job-1",
        signature="driver blocked",
    )

    assert summary["ok"] is True
    assert summary["downstream"]["job_id"] == "repair-job-runtime"
    params_obj = captured["params_obj"]
    assert isinstance(params_obj, dict)
    assert params_obj["route_mode"] == "auto_runtime"
    decision_override = params_obj["decision_override"]
    assert isinstance(decision_override, dict)
    assert decision_override["route"] == "repair.autofix"
    assert decision_override["runtime_fix"]["allow_actions"] == ["restart_driver"]


def test_apply_codex_sre_autofix_respects_allowlist_and_writes_log(tmp_path: Path, monkeypatch):
    md = _load_maint_daemon_module()

    inc_dir = tmp_path / "incident"
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)
    driver_root = tmp_path / "driver_root"
    (driver_root / "ops").mkdir(parents=True, exist_ok=True)
    (driver_root / "ops" / "chrome_start.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    # Stub side-effect functions.
    monkeypatch.setattr(md, "run_cmd", lambda *args, **kwargs: (True, "ok"))  # noqa: SLF001
    monkeypatch.setattr(md, "_start_driver_if_down", lambda *args, **kwargs: (True, {"started": True}))  # noqa: SLF001
    monkeypatch.setattr(md, "_chatgptmcp_call", lambda *args, **kwargs: {"ok": True})  # noqa: SLF001

    actions_payload = {
        "summary": "test",
        "hypotheses": [],
        "actions": [
            {"name": "restart_chrome", "reason": "cdp down", "risk": "low"},
            {"name": "restart_driver", "reason": "driver down", "risk": "low"},
            {"name": "clear_blocked", "reason": "stale block", "risk": "low"},
            {"name": "capture_ui", "reason": "need UI evidence", "risk": "low"},
            {"name": "refresh", "reason": "not supported in autofix", "risk": "low"},
        ],
        "risks": [],
    }

    summary = md._apply_codex_sre_autofix(  # noqa: SLF001
        inc_dir=inc_dir,
        incident_id="inc-1",
        actions_payload=actions_payload,
        allowed_actions={"restart_chrome", "restart_driver", "clear_blocked", "capture_ui"},
        max_risk="low",
        db_path=db_path,
        driver_root=driver_root,
        driver_url="http://127.0.0.1:18701/mcp",
        cdp_url="http://127.0.0.1:9222",
        mcp_client=object(),
    )
    assert summary["executed"] >= 4
    log_path = Path(summary["log_path"])
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert any("restart_chrome" in line for line in lines)
    assert any("restart_driver" in line for line in lines)


def test_apply_codex_sre_autofix_skips_restart_when_send_in_progress(tmp_path: Path, monkeypatch):
    md = _load_maint_daemon_module()

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)

    # Create an in-progress send job to trigger the drain guard.
    conn = md._connect(db_path)  # noqa: SLF001
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = job_store.create_job(
            conn,
            artifacts_dir=artifacts_dir,
            idempotency_key="k1",
            kind="chatgpt_web.ask",
            input={"question": "hi"},
            params={},
            max_attempts=1,
            allow_queue=True,
            enforce_conversation_single_flight=False,
        )
        job_store.transition(
            conn,
            artifacts_dir=artifacts_dir,
            job_id=job.job_id,
            dst=job_store.JobStatus.IN_PROGRESS,
        )
        conn.commit()
    finally:
        conn.close()

    inc_dir = tmp_path / "incident"
    driver_root = tmp_path / "driver_root"
    (driver_root / "ops").mkdir(parents=True, exist_ok=True)
    (driver_root / "ops" / "chrome_start.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(md, "run_cmd", lambda *args, **kwargs: (True, "ok"))  # noqa: SLF001
    monkeypatch.setattr(md, "_start_driver_if_down", lambda *args, **kwargs: (True, {"started": True}))  # noqa: SLF001
    monkeypatch.setattr(md, "_chatgptmcp_call", lambda *args, **kwargs: {"ok": True})  # noqa: SLF001

    actions_payload = {
        "summary": "test",
        "hypotheses": [],
        "actions": [
            {"name": "restart_chrome", "reason": "cdp down", "risk": "low"},
            {"name": "restart_driver", "reason": "driver down", "risk": "low"},
        ],
        "risks": [],
    }

    summary = md._apply_codex_sre_autofix(  # noqa: SLF001
        inc_dir=inc_dir,
        incident_id="inc-1",
        actions_payload=actions_payload,
        allowed_actions={"restart_chrome", "restart_driver"},
        max_risk="low",
        db_path=db_path,
        driver_root=driver_root,
        driver_url="http://127.0.0.1:18701/mcp",
        cdp_url="http://127.0.0.1:9222",
        mcp_client=object(),
    )
    assert summary["executed"] == 0
    log_path = Path(summary["log_path"])
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert any("send_in_progress" in line for line in lines)
