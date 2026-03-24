from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.direct_provider_execution_gate as mod


def test_run_direct_provider_execution_gate_passes_with_monkeypatched_live_calls(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_load_tokens", lambda env_file: {"OPENMIND_API_KEY": "ignored", "CHATGPTREST_API_TOKEN": "token"})

    def fake_post_job(**kwargs):
        if kwargs["kind"] == "chatgpt_web.ask":
            return {"status_code": 403, "body": {"detail": {"error": "direct_live_chatgpt_ask_blocked", "x_client_name": "chatgptrestctl"}}}
        return {"status_code": 200, "body": {"job_id": "job-gemini-1", "kind": "gemini_web.ask", "status": "queued"}}

    monkeypatch.setattr(mod, "_post_job", fake_post_job)
    monkeypatch.setattr(mod, "_wait_for_job", lambda **kwargs: {"status": "completed", "kind": "gemini_web.ask"})
    monkeypatch.setattr(mod, "_get_answer_chunk", lambda **kwargs: {"chunk": "done", "done": True})

    report = mod.run_direct_provider_execution_gate(base_url="http://127.0.0.1:18711")

    assert report.num_checks == 3
    assert report.num_failed == 0


def test_build_v1_jobs_auth_header_prefers_chatgptrest_api_token() -> None:
    headers = mod._build_v1_jobs_auth_header({"OPENMIND_API_KEY": "ignored", "CHATGPTREST_API_TOKEN": "abc"})

    assert headers == {"Authorization": "Bearer abc"}


def test_direct_provider_execution_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.DirectProviderExecutionGateReport(
        base_url="http://127.0.0.1:18711",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.DirectProviderExecutionCheck(name="blocked", passed=True, details={"http_status": 403})],
        scope_boundary=["scoped direct provider proof"],
    )

    json_path, md_path = mod.write_direct_provider_execution_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "Direct Provider Execution Gate Report" in md_path.read_text(encoding="utf-8")
