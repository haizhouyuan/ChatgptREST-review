from __future__ import annotations

from ops import antigravity_router_e2e as module


def test_run_case_completed_non_final_research_does_not_fetch_answer(monkeypatch) -> None:
    case = module.Case(
        case_id="direct_chatgpt_deep_research",
        kind="direct",
        title="Direct deep research",
        question="research this",
        expected_kind="chatgpt_web.ask",
        direct_kind="chatgpt_web.ask",
        direct_params={"preset": "thinking_heavy", "deep_research": True},
    )

    def fake_http_json(*, method: str, url: str, body=None, headers=None, timeout_seconds=30.0):  # noqa: ANN001,ARG001
        return (
            200,
            {
                "ok": True,
                "job_id": "job-antigravity-1",
                "kind": "chatgpt_web.ask",
                "status": "queued",
            },
            "{}",
        )

    def fake_wait_job(*, base_url: str, headers: dict[str, str], job_id: str, max_wait_seconds: int, poll_seconds: int):  # noqa: ARG001
        return {
            "job_id": job_id,
            "status": "completed",
            "completion_contract": {
                "answer_state": "provisional",
                "authoritative_answer_path": "jobs/job-antigravity-1/answer.md",
                "answer_provenance": {"contract_class": "research"},
            },
        }

    def fail_fetch_answer(**_kwargs):  # noqa: ANN001
        raise AssertionError("answer fetch should not run for non-final research result")

    monkeypatch.setattr(module, "_http_json", fake_http_json)
    monkeypatch.setattr(module, "_wait_job", fake_wait_job)
    monkeypatch.setattr(module, "_fetch_answer", fail_fetch_answer)

    record = module._run_case(
        case=case,
        idx=1,
        base_url="http://127.0.0.1:18711",
        token="test-token",
        client_name="antigravity",
        client_instance="ag-1",
        max_wait_seconds=60,
        poll_seconds=1,
        cancel_on_timeout=False,
    )

    assert record["wait_status"] == "completed"
    assert record["answer_state"] == "provisional"
    assert record["authoritative_answer_path"] == "jobs/job-antigravity-1/answer.md"
    assert record["final_status"] == "completed_not_final"
    assert "answer_chars" not in record
