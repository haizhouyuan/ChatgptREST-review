from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    path = Path("ops/smoke_test_chatgpt_auto.py").resolve()
    spec = importlib.util.spec_from_file_location("smoke_test_chatgpt_auto_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_policy_blocks_live_chatgpt_smoke_by_default() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="auto", allow_live_chatgpt_smoke=False)
    assert err is not None
    assert err["error_type"] == "PolicyError"
    assert "blocked by default" in err["message"]


def test_policy_blocks_high_cost_preset() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="pro_extended", allow_live_chatgpt_smoke=True)
    assert err is not None
    assert "only permits preset=auto" in err["message"]


def test_policy_allows_controlled_auto_override() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="auto", allow_live_chatgpt_smoke=True)
    assert err is None


def test_main_does_not_count_completed_but_non_final_research(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()

    def _fake_http_json(*, method: str, url: str, body=None, headers=None, timeout_seconds=30.0):  # noqa: ANN001,ARG001
        if url.endswith("/healthz"):
            return {"ok": True}
        if method == "POST" and url.endswith("/v1/jobs"):
            return {"job_id": "job-1", "status": "queued"}
        if method == "GET" and url.endswith("/v1/jobs/job-1"):
            return {
                "job_id": "job-1",
                "status": "completed",
                "completion_contract": {
                    "answer_state": "provisional",
                    "authoritative_answer_path": "jobs/job-1/answer.md",
                    "answer_provenance": {"contract_class": "research"},
                },
            }
        if "/v1/jobs/job-1/answer?" in url:
            raise AssertionError("answer endpoint should not be read for completed-but-non-final research")
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(mod, "_http_json", _fake_http_json)
    monkeypatch.setattr(mod, "_build_questions", lambda: [mod.SmokeQuestion(label="test", question="research this")])
    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)

    log_path = tmp_path / "smoke.jsonl"
    rc = mod.main(
        [
            "--allow-live-chatgpt-smoke",
            "--count",
            "1",
            "--poll-seconds",
            "0.01",
            "--sleep-between",
            "0",
            "--log-jsonl",
            str(log_path),
        ]
    )

    assert rc == 2
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "completed"
    assert record["answer_state"] == "provisional"
    assert record["finality_status"] == "completed_not_final"
    assert "answer_chars" not in record
