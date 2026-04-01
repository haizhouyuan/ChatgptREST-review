from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import LeaseLost, claim_next_job
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.worker import worker as worker_mod
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"tmp_path": tmp_path, "db_path": db_path, "artifacts_dir": artifacts_dir}


def test_worker_completes_job_and_answer_chunks(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 3, "delay_ms": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "k3"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(
        _run_once(
            cfg=load_config(),
            worker_id="test-worker",
            lease_ttl_seconds=60,
        )
    )
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert (job.json().get("preview") or "").startswith("hello")
    assert (job.json().get("path") or "").endswith(("answer.txt", "answer.md"))

    # Read answer via chunks.
    expected = "hello\nhello\nhello\n"
    pieces: list[str] = []
    offset: int | None = 0
    while offset is not None:
        resp = client.get(f"/v1/jobs/{job_id}/answer?offset={offset}&max_chars=5")
        assert resp.status_code == 200
        data = resp.json()
        pieces.append(data["chunk"])
        offset = data["next_offset"]
        if data["done"]:
            break
    assert "".join(pieces) == expected


def test_worker_stores_error_from_meta(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.error_meta", "input": {}, "params": {}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "meta-error"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(
        _run_once(
            cfg=load_config(),
            worker_id="test-worker",
            lease_ttl_seconds=60,
        )
    )
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "RuntimeError"
    assert "meta error" in (data.get("error") or "")

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert "meta error" in (result.get("error") or "")


def test_worker_converts_infra_error_to_cooldown(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "infra-error-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _InfraErrorExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="error",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "RuntimeError",
                    "error": "CDP connect failed (TimeoutError: BrowserType.connect_over_cdp: Timeout 60000ms exceeded.)",
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InfraErrorExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("reason_type") == "InfraError"
    assert "CDP connect failed" in (data.get("reason") or "")


def test_worker_converts_ui_error_to_cooldown(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "ui-error-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _UiErrorExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="error",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "RuntimeError",
                    "error": "Gemini upload menu button not found.",
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _UiErrorExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("reason_type") == "UiTransientError"
    assert "upload menu" in (data.get("reason") or "").lower()


def test_wait_phase_thread_url_uses_shorter_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", "120")
    monkeypatch.setenv("CHATGPTREST_WAIT_INFRA_RETRY_AFTER_SECONDS", "15")
    monkeypatch.setattr(worker_mod.random, "uniform", lambda _a, _b: 0.0)

    short_wait = worker_mod._retry_after_seconds_for_wait_phase_error(
        kind="gemini_web.ask",
        conversation_url="https://gemini.google.com/app/abc123xyz",
        error_type="RuntimeError",
        error="transport error: [Errno 111] Connection refused",
    )
    default_wait = worker_mod._retry_after_seconds_for_wait_phase_error(
        kind="gemini_web.ask",
        conversation_url=None,
        error_type="RuntimeError",
        error="transport error: [Errno 111] Connection refused",
    )
    assert short_wait == 15.0
    assert default_wait == 120.0


def test_worker_does_not_treat_gemini_base_app_url_as_thread_url(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_MAX_ATTEMPTS", "1")
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-base-url-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _CooldownExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "DriveUploadNotReady",
                    "error": "Google Drive upload not ready; retry later.",
                    "conversation_url": "https://gemini.google.com/app",
                    "retry_after_seconds": 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _CooldownExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("phase") == "send"
    assert int(data.get("max_attempts") or 0) >= 2


def test_worker_converts_gemini_generate_image_ui_error_to_cooldown(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "gemini_web.generate_image", "input": {"prompt": "hi"}, "params": {"count": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "ui-error-gemini-img-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _UiErrorExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="error",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "RuntimeError",
                    "error": "Cannot find Gemini Tools button.",
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _UiErrorExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("reason_type") == "UiTransientError"
    assert "tools button" in (data.get("reason") or "").lower()


def test_send_phase_requeues_wait(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "phase-requeue"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        reclaimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w2",
            lease_ttl_seconds=60,
            phase="wait",
        )
        conn.commit()
    assert reclaimed is not None
    assert reclaimed.job_id == job_id


def test_gemini_send_phase_without_thread_evidence_stays_on_send(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-send-no-thread-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={
                    "debug_timeline": [{"phase": "sent", "t": 0.1}],
                    "error_type": "WaitingForConversationUrl",
                    "error": "conversation_url not available yet; retry later",
                    "retry_after_seconds": 30,
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data["phase"] == "send"
    assert data.get("reason_type") == "WaitingForConversationUrl"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "phase_changed" not in event_types
    assert "wait_requeued" not in event_types


def test_gemini_send_phase_with_response_evidence_requeues_wait(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "deep_think"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-send-response-evidence-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={
                    "conversation_url": "https://gemini.google.com/app",
                    "error_type": "GeminiDeepThinkThreadPending",
                    "error": "Gemini Deep Think response started but the final answer is still pending.",
                    "response_started": True,
                    "wait_handoff_ready": True,
                    "retry_after_seconds": 15,
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "phase_changed" in event_types
    assert "wait_requeued" in event_types


def test_gemini_send_phase_with_pending_recovery_requeues_wait(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "deep_think"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-send-pending-recovery-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={
                    "conversation_url": "https://gemini.google.com/app",
                    "error_type": "GeminiSendPendingRecovery",
                    "error": "Gemini prompt was previously marked as sent, but no stable conversation URL was cached yet; recover via wait/sidebar instead of resending.",
                    "wait_handoff_ready": True,
                    "wait_handoff_reason": "idempotency_sent_without_thread",
                    "replayed": True,
                    "retry_after_seconds": 15,
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "phase_changed" in event_types
    assert "wait_requeued" in event_types


def test_gemini_send_phase_rebinds_to_latest_thread_url(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    initial_url = "https://gemini.google.com/app/aaaaaaaaaaaaaaaa"
    rebound_url = "https://gemini.google.com/app/bbbbbbbbbbbbbbbb"
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "hi", "conversation_url": initial_url},
        "params": {"preset": "deep_think", "deep_research": True},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-send-rebind-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    export_calls: list[str] = []

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": rebound_url, "retry_after_seconds": 0},
            )

    async def _fake_export_conversation(*, conversation_url: str, **kwargs):
        export_calls.append(str(conversation_url))

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"
    assert data["conversation_url"] == rebound_url
    assert rebound_url in export_calls


def test_completion_guard_downgrades_tool_payload_without_min_chars(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请给出答案"},
        "params": {"preset": "auto", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "tool-payload-guard-no-min-chars"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _CompletedToolPayloadExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=json.dumps(
                    {
                        "search_query": [{"q": "OpenClaw EvoMap integration"}],
                        "response_length": "short",
                    },
                    ensure_ascii=False,
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _CompletedToolPayloadExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_downgraded"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "tool_payload_not_final"


def test_completion_guard_still_enforces_min_chars_for_short_answers(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请输出完整报告"},
        "params": {"preset": "auto", "min_chars": 4000},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "min-chars-guard-short-answer"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _ShortCompletedExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=(
                    "报告已经整理完成，核心判断是当前方案可以继续推进，但需要先补齐验证闭环与风险登记。"
                    "现阶段的主要问题不在方向，而在于执行节奏和证据沉淀还不够完整。"
                    "如果今天就进入实施，建议先按高优先级清单逐项收口，再安排一次复盘。"
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _ShortCompletedExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_downgraded"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "answer_too_short_for_min_chars"


def test_completion_guard_research_contract_escalates_stalled_partial_answer(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请基于现有材料输出完整研究报告"},
        "params": {"preset": "auto", "purpose": "report", "min_chars": 4000},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "research-contract-blocked"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for i in range(10):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    float(i),
                    "completion_guard_downgraded",
                    json.dumps(
                        {
                            "reason": "answer_too_short_for_min_chars",
                            "answer_chars": 439,
                            "min_chars_required": 4000,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        conn.commit()

    class _ShortReportExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer="当前代码已经初步梳理完毕，下一步建议进入正式实现与验证。",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-report-grade-partial"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _ShortReportExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_classify_answer_quality", lambda *args, **kwargs: "final")

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data["completion_contract"]["answer_state"] == "provisional"
    assert data["completion_contract"]["finality_reason"] == "ResearchCompletionNotFinal"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_research_contract_blocked"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("action") == "research_completion_not_final"
    assert payload_obj.get("terminal_action") == "needs_followup"


def test_completion_guard_completes_legacy_trivial_prompt_short_answer(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "hello --- 附加上下文 --- - depth: standard"},
        "params": {"preset": "auto", "min_chars": 200},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "legacy-trivial-short-answer"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _TrivialHelloExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer="Hello! How can I assist you today?",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-trivial-hello"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _TrivialHelloExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "completed"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_completed_under_min_chars"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("action") == "completed_under_min_chars"
    assert payload_obj.get("decision_reason") == "trivial_prompt_short_answer"


def test_completion_guard_breaks_legacy_trivial_wait_loop_after_repeated_short_answer_downgrades(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "测试"},
        "params": {"preset": "auto", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "legacy-trivial-loop-breaker"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(3):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    time.time(),
                    "completion_guard_downgraded",
                    json.dumps({"reason": "answer_quality_suspect_short_answer"}, ensure_ascii=False),
                ),
            )
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    time.time(),
                    "wait_requeued",
                    json.dumps({"not_before": time.time() + 60}, ensure_ascii=False),
                ),
            )
        conn.commit()

    monkeypatch.setattr(worker_mod, "looks_like_synthetic_or_trivial_agent_prompt", lambda text: False)

    class _LoopingShortAnswerExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer="收到，已正常响应。要我帮你测试点什么？",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-trivial-loop-breaker"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _LoopingShortAnswerExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "completed"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_legacy_trivial_loop_broken"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("decision_reason") == "legacy_trivial_wait_loop_breaker"


def test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请完整评审这个 bundle"},
        "params": {"preset": "pro_extended", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "pro-short-answer-regenerate"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _SuspiciousProExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=(
                    "Based on the initial analysis of the uploaded review bundle, I found a few likely problems. "
                    "I will continue reviewing the remaining files and summarize the final verdict next."
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-pro-short-answer"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _SuspiciousProExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT last_error_type, last_error FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row["last_error_type"] == "ProInstantAnswerNeedsRegenerate"
        assert "regenerate" in str(row["last_error"] or "").lower()

        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_downgraded"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("action") == "needs_followup_regenerate"


def test_completion_guard_routes_generic_pro_review_verdict_to_regenerate_followup(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = (
        "Review the current ChatgptREST review mirror for source commit d84fe718e1478c59324e753a3637ed87b304d1fc.\n\n"
        "Use GitHub connector repo context for haizhouyuan/ChatgptREST-review. "
        "Three local markdown files are attached and must be treated as required reading.\n\n"
        "Instructions:\n"
        "- Findings first, ordered by severity.\n"
        "- For each finding, cite the problematic path.\n"
        "- Be critical rather than compliant.\n"
    )
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "pro_extended", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "pro-generic-review-regenerate"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _GenericReviewExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=(
                    "### Findings\n\n"
                    "#### 1. Public Agent as the sole general northbound entry\n"
                    "**Path**: Public Agent Control Plane (Blueprint)\n"
                    "- **Finding**: The architecture correctly keeps Public Agent as the single northbound entry.\n"
                    "- **Verdict**: This is a sound decision that keeps the flow coherent and implementable.\n\n"
                    "#### 2. Review as an internal mode under Public Agent\n"
                    "**Path**: Public Agent Deliberation Plane\n"
                    "- **Finding**: Treating review and deliberation as internal execution modes is a smart move.\n"
                    "- **Verdict**: The phased approach is sound and realistic.\n\n"
                    "### Open Questions\n\n"
                    "Will the migration remain realistic and coherent during rollout?\n\n"
                    "### Verdict\n\n"
                    "The proposed next-step architecture appears fundamentally solid overall."
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-pro-generic-review"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _GenericReviewExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT last_error_type, last_error FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row["last_error_type"] == "ProInstantAnswerNeedsRegenerate"
        assert "regenerate" in str(row["last_error"] or "").lower()

        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_downgraded"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("action") == "needs_followup_regenerate"
        assert payload_obj.get("reason") == "answer_quality_suspect_review_shallow_verdict"


def test_worker_does_not_crash_on_store_answer_lease_lost(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-lost-finalize"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    def _boom(*args, **kwargs):  # noqa: ARG001
        raise LeaseLost("lease lost")

    monkeypatch.setattr(worker_mod, "store_answer_result", _boom)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="test-worker", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "in_progress"


def _force_wait_in_progress(
    *,
    db_path: Path,
    job_id: str,
    age_seconds: float,
    conversation_url: str | None,
) -> None:
    now = time.time()
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE jobs
            SET status = 'in_progress',
                phase = 'wait',
                not_before = 0,
                created_at = ?,
                updated_at = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                lease_token = NULL,
                conversation_url = ?,
                conversation_id = NULL
            WHERE job_id = ?
            """,
            (now - float(age_seconds), now - float(age_seconds), conversation_url, job_id),
        )
        conn.commit()


def _insert_job_event(
    *,
    db_path: Path,
    job_id: str,
    event_type: str,
    payload: dict | None = None,
    ts: float | None = None,
) -> None:
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO job_events(job_id, ts, type, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                float(ts if ts is not None else time.time()),
                str(event_type),
                (json.dumps(payload, ensure_ascii=False) if payload is not None else None),
            ),
        )
        conn.commit()


def test_wait_no_progress_event_classifies_export_events_as_non_progress() -> None:
    assert worker_mod._wait_no_progress_event_is_progress("status_changed", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("mihomo_delay_snapshot", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("model_observed", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("conversation_exported", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("conversation_export_forced", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("model_observed_export", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("worker_timing", {}) is False
    assert worker_mod._wait_no_progress_event_is_progress("prompt_sent", {}) is True


def test_wait_no_progress_phase_changed_only_wait_counts_as_progress() -> None:
    assert worker_mod._wait_no_progress_event_is_progress("phase_changed", {"to": "wait"}) is True
    assert worker_mod._wait_no_progress_event_is_progress("phase_changed", {"to": "send"}) is False
    assert worker_mod._wait_no_progress_event_is_progress("phase_changed", {}) is False


@pytest.mark.parametrize("event_type", ["status_changed", "mihomo_delay_snapshot", "model_observed"])
def test_wait_phase_non_progress_churn_events_do_not_reset_anchor(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
) -> None:
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": f"wait-non-progress-{event_type}"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type=event_type,
        payload={"marker": "non-progress-churn"},
        ts=time.time(),
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_timeout"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "no_progress"
    assert payload_obj.get("last_progress_source") == "job_created"


def test_wait_phase_recent_progress_event_beats_latest_non_progress_churn(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-progress-anchor-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )

    now = time.time()
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="prompt_sent",
        payload={"channel": "test"},
        ts=now - 1.0,
    )
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="status_changed",
        payload={"from": "cooldown", "to": "in_progress"},
        ts=now,
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

def test_wait_phase_no_progress_timeout_to_needs_followup(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS", "7")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-no-progress-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_timeout"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "no_progress"
    assert payload_obj.get("status") == "needs_followup"


def test_wait_phase_export_noise_does_not_reset_no_progress_timeout(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-export-noise-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="conversation_exported",
        payload={"conversation_export_chars": 1024},
        ts=time.time(),
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"


def test_wait_phase_missing_thread_url_timeout(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-no-thread-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=None)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(status="in_progress", answer="", answer_format="text", meta={"retry_after_seconds": 0})

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoThreadUrlTimeout"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_timeout"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "missing_thread_url"


def test_gemini_wait_phase_missing_thread_url_timeout_tags_issue_family(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-wait-no-thread-family-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=None)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(status="in_progress", answer="", answer_format="text", meta={"retry_after_seconds": 0})

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_timeout"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("issue_family") == "gemini_no_thread_url"


def test_gemini_wait_phase_no_progress_timeout_tags_issue_family(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://gemini.google.com/app/1234567890abcdef"
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。", "conversation_url": thread_url},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-wait-no-progress-family-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": thread_url, "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_timeout"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("issue_family") == "gemini_stable_thread_no_progress"


def test_wait_phase_deep_research_uses_longer_timeout(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")

    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "hi"},
        "params": {"preset": "auto", "deep_research": True},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-deep-research-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"
