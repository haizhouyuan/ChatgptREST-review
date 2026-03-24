from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.attachment_contract import detect_missing_attachment_contract
from chatgptrest.core.config import load_config
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor
from chatgptrest.worker import worker as worker_mod
from chatgptrest.worker.worker import _run_once


class _NeverCalledToolCaller:
    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
        raise AssertionError(f"tool should not be called: {tool_name}")


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ISSUE_AUTOREPORT_ENABLED", "1")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_detect_missing_attachment_contract_marks_high_risk_review_bundle() -> None:
    signal = detect_missing_attachment_contract(
        kind="chatgpt_web.ask",
        input_obj={"question": "Read the local review bundle at /vol1/work/review_bundle_v1.md and summarize it."},
        params_obj={"purpose": "review"},
    )
    assert signal is not None
    assert signal["family_id"] == "attachment_contract_missing"
    assert signal["high_risk"] is True
    assert signal["local_file_refs"] == ["/vol1/work/review_bundle_v1.md"]


def test_detect_missing_attachment_contract_does_not_hard_block_path_discussion() -> None:
    signal = detect_missing_attachment_contract(
        kind="chatgpt_web.ask",
        input_obj={"question": "Why does /vol1/work/review_bundle_v1.md keep changing between runs?"},
        params_obj={},
    )
    assert signal is not None
    assert signal["high_risk"] is False


def test_detect_missing_attachment_contract_ignores_chinese_slash_headings() -> None:
    signal = detect_missing_attachment_contract(
        kind="chatgpt_web.ask",
        input_obj={
            "question": (
                "请覆盖 /二手来源**：标注每个信息点是一手来源还是二手来源。\n"
                "并按证据强弱（强/中/弱/推测）标注，不要把 /中/弱/推测） 当成文件路径。\n"
                "要有具体证据/行为/访谈/组合调整支撑，不要合理化叙述。"
            )
        },
        params_obj={"purpose": "research"},
    )
    assert signal is None


def test_detect_missing_attachment_contract_keeps_relative_bundle_paths() -> None:
    signal = detect_missing_attachment_contract(
        kind="chatgpt_web.ask",
        input_obj={"question": "Read ./review_bundle_v1.zip and summarize the materials."},
        params_obj={"purpose": "review"},
    )
    assert signal is not None
    assert signal["local_file_refs"] == ["./review_bundle_v1.zip"]
    assert signal["high_risk"] is True


def test_chatgpt_executor_fails_closed_for_high_risk_missing_attachment() -> None:
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _NeverCalledToolCaller()  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-chatgpt-contract",
            kind="chatgpt_web.ask",
            input={"question": "Read the local review bundle at /vol1/work/review_bundle_v1.md and review it."},
            params={"preset": "auto", "phase": "send", "max_wait_seconds": 60, "purpose": "review"},
        )
    )
    assert res.status == "error"
    meta = res.meta or {}
    assert meta.get("error_type") == "AttachmentContractMissing"
    assert meta.get("family_id") == "attachment_contract_missing"


def test_gemini_executor_fails_closed_for_high_risk_missing_attachment() -> None:
    ex = GeminiWebMcpExecutor(tool_caller=_NeverCalledToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-contract",
            kind="gemini_web.ask",
            input={"question": "Read the local audit bundle at /vol1/work/audit_bundle_v2.zip and compare it."},
            params={"preset": "pro", "phase": "send", "timeout_seconds": 60, "max_wait_seconds": 60, "purpose": "audit"},
        )
    )
    assert res.status == "error"
    meta = res.meta or {}
    assert meta.get("error_type") == "AttachmentContractMissing"
    assert meta.get("family_id") == "attachment_contract_missing"


def test_worker_records_attachment_contract_event_and_issue_family(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)

    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Read the local review bundle at /vol1/work/review_bundle_v1.md and summarize it."},
        "params": {"purpose": "review", "preset": "auto"},
        "client": {"project": "research"},
    }
    created = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "attachment-contract-worker-1"})
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    class _DummyExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002, ARG002
            return ExecutorResult(
                status="error",
                answer="simulated failure",
                meta={"error_type": "RuntimeError", "error": "simulated failure"},
            )

    monkeypatch.setattr(worker_mod, "build_tool_caller", lambda **kwargs: object())
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _DummyExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-attachment", lease_ttl_seconds=60))
    assert ran is True

    events_resp = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]
    detected = [evt for evt in events if evt["type"] == "attachment_contract_missing_detected"]
    assert len(detected) == 1
    assert detected[0]["payload"]["family_id"] == "attachment_contract_missing"
    assert detected[0]["payload"]["high_risk"] is True

    issues_resp = client.get("/v1/issues?source=worker_auto&limit=10")
    assert issues_resp.status_code == 200
    issues = issues_resp.json()["issues"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue["metadata"]["family_id"] == "attachment_contract_missing"
    assert issue["metadata"]["family_label"] == "Attachment contract missing"
    assert issue["metadata"]["attachment_contract"]["high_risk"] is True
