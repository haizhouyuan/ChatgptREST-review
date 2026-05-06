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
from chatgptrest.core.job_store import LeaseLost, claim_next_job, request_cancel
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


def test_chatgpt_page_crashed_send_failure_records_exhaustion_event(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_EXTEND_MAX_ATTEMPTS", "0")

    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Please do a deep review."},
        "params": {"preset": "pro_extended", "deep_research": True},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "chatgpt-page-crashed-send-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _PageCrashedExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="error",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "Error",
                    "error": 'Page.goto: Page crashed\nCall log:\n  - navigating to "https://chatgpt.com/"',
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _PageCrashedExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "MaxAttemptsExceeded"
    assert "InfraError: Page.goto: Page crashed" in (data.get("error") or "")

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    retry_exhausted = [item for item in events if item.get("type") == "web_send_retry_exhausted"]
    assert retry_exhausted
    payload = retry_exhausted[-1]["payload"]
    assert payload["terminal_error_type"] == "MaxAttemptsExceeded"
    assert payload["error_type"] == "InfraError"
    assert payload["recommended_params"]["send_timeout_seconds"] == 240


def test_chatgpt_send_cancel_preserves_inflight_provider_evidence(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "Please review this proposal."}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "chatgpt-inflight-cancel-evidence"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    started: asyncio.Event = asyncio.Event()
    conversation_url = "https://chatgpt.com/c/inflight-cancel-evidence"

    class _SlowSentExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002, ARG002
            started.set()
            await asyncio.sleep(0.2)
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": conversation_url},
            )

    original_cancel_watch = worker_mod._cancel_watch

    async def _fast_cancel_watch(**kwargs):  # noqa: ANN003
        kwargs["poll_seconds"] = 0.01
        return await original_cancel_watch(**kwargs)

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _SlowSentExecutor())
    monkeypatch.setattr(worker_mod, "_cancel_watch", _fast_cancel_watch)

    async def _run_and_cancel() -> bool:
        task = asyncio.create_task(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
        await asyncio.wait_for(started.wait(), timeout=1)
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            request_cancel(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                requested_by={"test": "inflight_cancel"},
                reason="unit test cancel after provider send started",
            )
            conn.commit()
        return await asyncio.wait_for(task, timeout=2)

    ran = asyncio.run(_run_and_cancel())
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "canceled"
    assert data["phase"] == "send"
    assert data["conversation_url"] == conversation_url

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "canceled"
    assert result["conversation_url"] == conversation_url

    with connect(env["db_path"]) as conn:
        event_types = [
            str(row["type"])
            for row in conn.execute("SELECT type FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)).fetchall()
        ]
    assert "inflight_send_cancel_observed" in event_types
    assert "inflight_send_cancel_completed" in event_types
    assert "inflight_send_cancel_recorded" in event_types


def test_worker_retry_helpers_honor_human_retry_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS", "90")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS", "0")
    monkeypatch.setenv("CHATGPTREST_UI_RETRY_AFTER_SECONDS", "30")
    monkeypatch.setenv("CHATGPTREST_WAIT_UI_RETRY_AFTER_SECONDS", "12")

    assert worker_mod._retry_after_seconds_for_error(error_type="RuntimeError", error="Gemini upload menu button not found.") == 90.0
    assert (
        worker_mod._retry_after_seconds_for_wait_phase_error(
            kind="gemini_web.ask",
            conversation_url="https://gemini.google.com/app/abc123",
            error_type="RuntimeError",
            error="Gemini upload menu button not found.",
        )
        == 90.0
    )
    assert worker_mod._completion_guard_retry_after_seconds() == 90.0


def test_worker_fail_closes_when_browser_retry_budget_exceeded(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续整理这一轮网页研究并给出最终结论。"},
        "params": {"preset": "auto"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "browser-retry-budget-exceeded"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_WINDOW_SECONDS", "900")
    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_JOB", "4")
    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_PROVIDER", "999")
    now = time.time()
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(4):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    now - 30,
                    "browser_retry_scheduled",
                    json.dumps({"provider_id": "chatgpt", "phase": "send", "status": "cooldown"}, ensure_ascii=False),
                ),
            )
        conn.commit()

    class _CooldownExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "UiTransientError",
                    "error": "chat input temporarily unavailable",
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _CooldownExecutor(),
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
        assert row["last_error_type"] == "WebRetryBudgetExceeded"
        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "browser_retry_budget_exceeded"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("provider_id") == "chatgpt"
        assert payload_obj.get("recent_job_retry_count") == 4


def test_worker_fail_closes_chatgpt_send_sse_timeout_without_thread(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续这轮分析并给出最终结论。"},
        "params": {"preset": "auto"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "chatgpt-send-sse-fail-closed-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _SseTimeoutExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "ToolCallError",
                    "error": "McpHttpError: SSE stream timeout (deadline exceeded).",
                    "retry_after_seconds": 30,
                    "not_before": time.time() + 30,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _SseTimeoutExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "ToolCallError"
    assert "same-session repair condition without stable conversation/thread evidence" in (
        data.get("error") or data.get("reason") or ""
    )

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "chatgpt_send_manual_repair_fail_closed" in event_types
    assert "max_attempts_extended" not in event_types


def test_worker_keeps_chatgpt_unsent_transport_timeout_retryable(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续这轮分析并给出最终结论。"},
        "params": {"preset": "auto"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "chatgpt-send-unsent-timeout-retryable-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _UnsentTransportTimeoutExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "ToolCallError",
                    "error": (
                        "McpHttpError: SSE stream timeout (deadline exceeded).; "
                        "self_check=ChatGPTSelfCheckError: McpHttpError: SSE stream timeout (deadline exceeded)."
                    ),
                    "retry_after_seconds": 30,
                    "not_before": time.time() + 30,
                    "send_phase_evidence": {
                        "idempotency_sent": False,
                        "recovered_conversation_url": None,
                        "requested_conversation_url": None,
                        "safe_to_retry_send": True,
                    },
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _UnsentTransportTimeoutExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("reason_type") == "ToolCallError"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "chatgpt_send_manual_repair_fail_closed" not in event_types


def test_worker_fail_closes_chatgpt_verification_block_without_thread(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续这轮分析并给出最终结论。"},
        "params": {"preset": "auto"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "chatgpt-send-verification-fail-closed-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _VerificationBlockedExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="blocked",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "Blocked",
                    "error": "driver blocked: verification_pending",
                    "retry_after_seconds": 30,
                    "not_before": time.time() + 30,
                },
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _VerificationBlockedExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "Blocked"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "chatgpt_send_manual_repair_fail_closed" in event_types
    assert "max_attempts_extended" not in event_types


def test_worker_fail_closes_blank_gemini_send_timeout_without_thread(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-blank-timeout-fail-closed-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _BlankTimeoutExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="error",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "RuntimeError",
                    "error": "TimeoutError: <TimeoutError: empty error>",
                    "not_before": time.time() - 1,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _BlankTimeoutExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "GeminiBlankSendTimeout"
    assert "fail closed instead of repeated cooldown retries" in (data.get("error") or data.get("reason") or "")

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "blank_gemini_cooldown_fail_closed" in event_types
    assert "max_attempts_extended" not in event_types


def test_worker_fail_closes_blank_gemini_executor_cooldown_without_thread(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-blank-timeout-fail-closed-2"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _BlankCooldownExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "UiTransientError",
                    "error": "<TimeoutError: empty error>",
                    "retry_after_seconds": 30,
                    "not_before": time.time() + 30,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _BlankCooldownExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "error"
    assert data.get("reason_type") == "GeminiBlankSendTimeout"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "blank_gemini_cooldown_fail_closed" in event_types
    assert "max_attempts_extended" not in event_types


def test_wait_phase_thread_url_retry_backoff_is_still_human_paced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", "120")
    monkeypatch.setenv("CHATGPTREST_WAIT_INFRA_RETRY_AFTER_SECONDS", "15")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS", "90")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS", "0")
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
    assert short_wait == 90.0
    assert default_wait == 120.0


def test_worker_does_not_fail_close_pre_send_gemini_prompt_box_timeout(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前主题的主要技术风险。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "gemini-pre-send-timeout-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _PreSendTimeoutExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={
                    "error_type": "UiTransientError",
                    "error": "<TimeoutError: empty error>",
                    "debug_step": "find_prompt_box_initial",
                    "retry_after_seconds": 30,
                    "not_before": time.time() + 30,
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _PreSendTimeoutExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "cooldown"
    assert data.get("phase") == "send"
    assert data.get("reason_type") == "UiTransientError"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "blank_gemini_cooldown_fail_closed" not in event_types


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


def test_chatgpt_extract_answer_uses_export_last_assistant_without_question(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    conversation_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.extract_answer",
        "input": {"conversation_url": conversation_url},
        "params": {"timeout_seconds": 300},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "extract-answer-last-assistant"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    final_answer = "## Architecture Memo\n\n" + ("final recommendation.\n" * 80)

    class _CompletedBlankExportExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer="",
                answer_format="text",
                meta={"conversation_url": conversation_url},
            )

    async def _fake_export_conversation(**kwargs):
        export_path = env["artifacts_dir"] / "jobs" / str(kwargs["job_id"]) / "conversation.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "text": "original prompt"},
                        {"role": "assistant", "text": "我先看材料。"},
                        {"role": "user", "text": "please continue"},
                        {"role": "assistant", "text": final_answer},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _CompletedBlankExportExecutor())
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "completed"
    assert data["answer_chars"] == len(final_answer)

    answer = client.get(f"/v1/jobs/{job_id}/answer?offset=0&max_chars=4000")
    assert answer.status_code == 200
    assert answer.json()["chunk"] == final_answer

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "answer_reconciled_from_conversation"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("export_match", {}).get("answer_source") == "fallback_last_assistant"


def test_chatgpt_extract_answer_empty_export_is_not_completed(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    conversation_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.extract_answer",
        "input": {"conversation_url": conversation_url},
        "params": {"timeout_seconds": 300},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "extract-answer-empty-export"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _CompletedBlankExportExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer="",
                answer_format="text",
                meta={"conversation_url": conversation_url},
            )

    async def _fake_export_conversation(**kwargs):
        export_path = env["artifacts_dir"] / "jobs" / str(kwargs["job_id"]) / "conversation.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps({"messages": [{"role": "user", "text": "original prompt"}]}, ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _CompletedBlankExportExecutor())
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "ExtractAnswerEmpty"


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


def test_completion_guard_fails_closed_when_suspicious_short_answer_repeats_without_improvement(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请完整评审这个 bundle，并给出真正可执行的风险和下一步。"},
        "params": {"preset": "auto", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "short-answer-loop-breaker"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(8):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    time.time(),
                    "completion_guard_downgraded",
                    json.dumps(
                        {
                            "reason": "answer_quality_suspect_short_answer",
                            "answer_chars": 132,
                        },
                        ensure_ascii=False,
                    ),
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

    class _LoopingShortAnswerExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=(
                    "初步检查显示有一些潜在问题，但目前还不足以下最终结论。"
                    "我建议继续查看剩余文件后再给出完整 verdict。"
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-short-answer-loop-breaker"},
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
    assert data["status"] == "needs_followup"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT last_error_type, last_error FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row["last_error_type"] == "SuspiciousShortAnswerLoop"

        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_suspicious_short_answer_loop_broken"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("decision_reason") == "suspicious_short_answer_loop_breaker"


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


def test_completion_guard_fails_closed_when_export_thread_is_contaminated(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = "重新做一份更聚焦的深度调研：AI 真正改变了 3D 打印玩法。"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "deep_research", "deep_research": True, "min_chars": 800},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "thread-contaminated-export"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    artifacts_job_dir = env["artifacts_dir"] / "jobs" / job_id
    artifacts_job_dir.mkdir(parents=True, exist_ok=True)
    conversation_export = {
        "messages": [
            {"role": "user", "text": question},
            {"role": "user", "text": "扫描 /vol1/1000/projects/planning 下所有 2026 年 Q1 文档。"},
            {"role": "assistant", "text": "当前 chat runtime 无法直接访问 /vol1 挂载。"},
        ]
    }
    (artifacts_job_dir / "conversation.json").write_text(
        json.dumps(conversation_export, ensure_ascii=False),
        encoding="utf-8",
    )

    class _ContaminatedThreadExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=(
                    "当前 chat runtime 无法直接访问 /vol1 挂载，因此我先输出一个替代性的扫描方案，"
                    "后续再补真正的目录梳理结果。"
                ),
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test-thread-contaminated"},
            )

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _ContaminatedThreadExecutor(),
    )

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"

    with connect(env["db_path"]) as conn:
        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_thread_contaminated"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("reason") == "thread_contaminated_by_subsequent_user_turn"
        assert payload_obj.get("next_role_after_match") == "user"


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


def test_thinking_send_timeout_without_complete_export_requeues_to_wait(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = "请完整输出 Pro 顾问结论。"
    thread_url = "https://chatgpt.com/c/33333333-3333-3333-3333-333333333333"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "pro_extended", "min_chars": 800},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "thinking-send-timeout-no-export"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    answer = (
        "## 顾问结论\n\n"
        "这段文字看起来像一个完整答案，但 driver 已经命中 send-stage timeout，"
        "并且没有 conversation export 能证明当前 assistant turn 已经完成。"
        "因此 worker 必须把它交给 wait 阶段继续对账，而不是直接 final。"
        * 20
    )

    class _TimedOutThinkingExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="completed",
                answer=answer,
                answer_format="markdown",
                meta={
                    "conversation_url": thread_url,
                    "wait_observations": {"timed_out": True},
                    "debug_timeline": [{"phase": "sent", "t": 1.0}, {"phase": "answer_ready", "t": 60.0}],
                },
            )

    async def _fake_export_conversation(**kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _TimedOutThinkingExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="send"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"
    assert data["answer_chars"] is None

    with connect(env["db_path"]) as conn:
        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_downgraded"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("reason") == "thinking_send_timeout_without_complete_export"


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


def test_wait_phase_finalizes_from_current_answer_when_export_missing_reply(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = "请基于当前仓库状态输出一版完整的执行收口总结。"
    thread_url = "https://chatgpt.com/c/11111111-1111-1111-1111-111111111111"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "auto", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-finalize-current-answer"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=90,
        conversation_url=thread_url,
    )

    artifacts_job_dir = env["artifacts_dir"] / "jobs" / job_id
    artifacts_job_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_job_dir / "conversation.json").write_text(
        json.dumps({"messages": [{"role": "user", "text": question}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    answer = (
        "# 执行收口总结\n\n"
        "当前主线已经明确分成两部分：一是把自愈和自动修复的路由收窄，二是把等待 export 对账时已经成型的答案直接收口为 canonical answer。"
        "这意味着系统不会继续把明显不该进 Codex 的问题送进 Spark，也不会再让用户在网页里已经看到完整答案时仍然拿不到 answer artifact。\n\n"
        "- 自愈治理：先按错误家族做 gate，再进入 repair.check / codex_sre / repair.autofix。\n"
        "- export 对账：当 export 只匹配到用户消息但尚未返回 assistant reply 时，允许用当前页面答案完成收口。\n"
        "- 风险边界：若线程在匹配问题后已经被后续用户消息污染，则 fail-closed 到 needs_followup。\n"
        "- 交付结果：最终 answer artifact、completion contract 与 canonical answer 会在同一轮 wait 中一起落盘，不再要求用户手工从浏览器复制正文。\n\n"
        "这份总结同时说明了为什么要把两条修复放在一起做：如果只收紧自愈而不补 export 对账，用户仍会遇到网页答案已经完成但 API 拿不到结果的问题；"
        "如果只修 export 对账而不收紧自愈，系统又会继续把大量 caller contract、验证码、区域限制和 same-session repair 问题送进 Spark，整体成本仍然失控。"
        "因此正确的收口方式，是把 repair gate、预算、显式开关和 wait 阶段的 canonical answer 终态一起做成一套。"
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer=answer,
                answer_format="markdown",
                meta={
                    "conversation_url": thread_url,
                    "debug_timeline": [{"phase": "answer_ready", "t": 1.0}],
                },
            )

    async def _fake_export_conversation(**kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    job_data = job.json()
    assert job_data["status"] == "completed"

    result = client.get(f"/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    result_data = result.json()
    assert result_data["status"] == "completed"
    assert result_data["completion_contract"]["answer_state"] == "final"
    assert result_data["completion_contract"]["authoritative_answer_path"].endswith("answer.md")

    answer_path = env["artifacts_dir"] / result_data["completion_contract"]["authoritative_answer_path"]
    assert answer_path.read_text(encoding="utf-8").strip() == answer.strip()

    with connect(env["db_path"]) as conn:
        ignored_evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "conversation_export_missing_reply_ignored"),
        ).fetchone()
        assert ignored_evt is not None
        completed_evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "answer_completed_from_wait_answer"),
        ).fetchone()
        assert completed_evt is not None
        payload_obj = json.loads(str(completed_evt["payload_json"] or "{}"))
        assert payload_obj.get("chosen_source") == "current_answer"


def test_wait_phase_finalizes_from_answer_id_when_export_missing_reply(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = "请输出完整的仓库治理升级结论。"
    thread_url = "https://chatgpt.com/c/22222222-2222-2222-2222-222222222222"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "pro_extended", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-finalize-answer-id"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=90,
        conversation_url=thread_url,
    )

    artifacts_job_dir = env["artifacts_dir"] / "jobs" / job_id
    artifacts_job_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_job_dir / "conversation.json").write_text(
        json.dumps({"messages": [{"role": "user", "text": question}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    partial = "TRUNCATED: 当前已经确认要同时修复自愈治理与 canonical answer 收口。"
    full_answer = (
        partial
        + "\n\n"
        + "完整结论如下：先按 repair gate 把 caller contract、external prerequisite、provider fail-closed 三类问题挡在 Codex 之前，"
        + "再把 maint daemon 和 worker 两条 auto-fix 路由统一纳入每日预算和显式开关。"
        + "与此同时，wait/export 对账逻辑要允许在 export 尚未补齐 assistant reply 时直接采用 answer_id 还原出的完整答案，"
        + "这样 canonical answer artifact 不再被无意义地拖后。"
        + "这也意味着，即使 DOM 只拿到了截断片段，只要 answer_id 已经保存了完整正文，worker 也可以在 wait 阶段直接完成最终落盘。"
        + "最终效果应该是 completed、authoritative_answer_path 可读、answer_state=final，而不是继续停留在 awaiting_export_reconciliation。"
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer=partial,
                answer_format="markdown",
                meta={
                    "conversation_url": thread_url,
                    "answer_saved": True,
                    "answer_truncated": True,
                    "answer_id": "a" * 32,
                    "answer_chars": len(full_answer),
                    "debug_timeline": [{"phase": "answer_ready", "t": 1.0}],
                },
            )

    async def _fake_export_conversation(**kwargs):  # noqa: ARG001
        return None

    async def _fake_rehydrate_answer_from_answer_id(**kwargs):  # noqa: ARG001
        return full_answer

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)
    monkeypatch.setattr(worker_mod, "_rehydrate_answer_from_answer_id", _fake_rehydrate_answer_from_answer_id)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"

    result = client.get(f"/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    result_data = result.json()
    answer_path = env["artifacts_dir"] / result_data["completion_contract"]["authoritative_answer_path"]
    assert answer_path.read_text(encoding="utf-8").strip() == full_answer.strip()

    with connect(env["db_path"]) as conn:
        completed_evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "answer_completed_from_answer_id"),
        ).fetchone()
        assert completed_evt is not None
        payload_obj = json.loads(str(completed_evt["payload_json"] or "{}"))
        assert payload_obj.get("chosen_source") == "answer_id"
        assert bool(payload_obj.get("answer_rehydrated")) is True


def test_wait_phase_fails_closed_when_export_thread_is_contaminated(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    client = TestClient(app)
    question = "请基于当前变更给出最终收口方案。"
    thread_url = "https://chatgpt.com/c/33333333-3333-3333-3333-333333333333"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "auto", "min_chars": 0},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-thread-contaminated"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=90,
        conversation_url=thread_url,
    )

    artifacts_job_dir = env["artifacts_dir"] / "jobs" / job_id
    artifacts_job_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_job_dir / "conversation.json").write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "text": question},
                    {"role": "user", "text": "顺便把另一个完全无关的任务也做了。"},
                    {"role": "assistant", "text": "我先处理后一个任务。"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer=(
                    "这里有一段当前页面里的内容，但它已经不能被安全地认定为本 job 的最终答案，"
                    "因为 export 已经显示在匹配问题之后又出现了新的 user turn。"
                ),
                answer_format="text",
                meta={"conversation_url": thread_url},
            )

    async def _fake_export_conversation(**kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        worker_mod,
        "_executor_for_job",
        lambda cfg, kind, tool_caller=None: _InProgressExecutor(),
    )
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    job_data = job.json()
    assert job_data["status"] == "needs_followup"

    with connect(env["db_path"]) as conn:
        evt = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "completion_guard_thread_contaminated"),
        ).fetchone()
        assert evt is not None
        payload_obj = json.loads(str(evt["payload_json"] or "{}"))
        assert payload_obj.get("reason") == "thread_contaminated_by_subsequent_user_turn"
        assert payload_obj.get("next_role_after_match") == "user"


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


def test_wait_phase_active_finalization_requeues_without_browser_retry_budget(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请判断这是不是主力路线。"},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-active-finalization-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url=thread_url,
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="我会直接按你指定的格式给出平台判断。",
                answer_format="text",
                meta={
                    "conversation_url": thread_url,
                    "retry_after_seconds": 0,
                },
            )

    async def _fake_export_conversation(**kwargs):
        artifacts_dir = env["artifacts_dir"]
        export_path = artifacts_dir / "jobs" / job_id / "conversation.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_obj = {
            "conversation_id": "12345678-1234-1234-1234-123456789abc",
            "default_model_slug": "gpt-5-4-pro",
            "current_node": "tool1",
            "mapping": {
                "user1": {
                    "id": "user1",
                    "parent": None,
                    "message": {
                        "id": "user1",
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["请判断这是不是主力路线。"]},
                        "status": "finished_successfully",
                    },
                },
                "assistant1": {
                    "id": "assistant1",
                    "parent": "user1",
                    "message": {
                        "id": "assistant1",
                        "author": {"role": "assistant"},
                        "content": {"content_type": "text", "parts": ["我会直接按你指定的格式给出平台判断。"]},
                        "status": "finished_successfully",
                        "end_turn": True,
                        "channel": "commentary",
                        "metadata": {
                            "model_slug": "gpt-5-4-pro",
                            "is_thinking_preamble_message": True,
                        },
                    },
                },
                "tool1": {
                    "id": "tool1",
                    "parent": "assistant1",
                    "message": {
                        "id": "tool1",
                        "author": {"role": "tool", "name": "a8km123"},
                        "content": {"content_type": "text", "parts": [""]},
                        "status": "in_progress",
                        "metadata": {
                            "model_slug": "gpt-5-4-pro",
                            "thinking_effort": "extended",
                            "is_finalizing": True,
                            "pro_progress": 63.95,
                        },
                    },
                },
            },
        }
        export_path.write_text(json.dumps(export_obj, ensure_ascii=False), encoding="utf-8")
        _insert_job_event(
            db_path=env["db_path"],
            job_id=job_id,
            event_type="conversation_exported",
            payload={"conversation_export_chars": len(export_path.read_text(encoding="utf-8"))},
        )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "wait_requeued" in event_types
    assert "wait_active_finalization_observed" in event_types
    assert "browser_retry_scheduled" not in event_types
    assert "browser_retry_budget_exceeded" not in event_types


def test_active_finalization_ignores_stale_tool_before_latest_user_turn():
    obj = {
        "mapping": {
            "user1": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 100.0,
                    "status": "finished_successfully",
                    "content": {"content_type": "text", "parts": ["first ask"]},
                }
            },
            "stale_tool": {
                "message": {
                    "author": {"role": "tool"},
                    "create_time": 110.0,
                    "status": "in_progress",
                    "content": {"content_type": "text", "parts": [""]},
                    "metadata": {
                        "model_slug": "gpt-5-5-pro",
                        "pro_progress": 30.116840781560022,
                        "is_finalizing": False,
                    },
                }
            },
            "user2": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 200.0,
                    "status": "finished_successfully",
                    "content": {"content_type": "text", "parts": ["corrective ask"]},
                }
            },
            "assistant_thoughts": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 201.0,
                    "status": "finished_successfully",
                    "content": {"content_type": "thoughts", "parts": []},
                }
            },
        }
    }

    assert worker_mod._conversation_export_active_finalization_details(obj=obj) is None


def test_wait_partial_answer_progress_dedupes_stored_preview_head(env: dict[str, Path]):
    answer = "这是一段已经被 wait 层反复读到的部分答案。" * 20
    job_id = "partial-progress-dedupe"
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="wait_partial_answer_progressed",
        payload={
            "answer_chars": len(answer),
            "answer_quality": "partial",
            "preview": answer[:240],
            "changed": True,
        },
    )

    with connect(env["db_path"]) as conn:
        payload = worker_mod._wait_partial_answer_progress_payload(
            conn=conn,
            job_id=job_id,
            answer_text=answer,
        )

    assert payload is None


def test_wait_partial_answer_prompt_echo_is_not_progress(env: dict[str, Path]):
    question = "请现在实际输出答案，不要复述我的问题。请补完第 7-10 节。" * 8
    job_id = "partial-progress-prompt-echo"

    with connect(env["db_path"]) as conn:
        payload = worker_mod._wait_partial_answer_progress_payload(
            conn=conn,
            job_id=job_id,
            answer_text=question,
            question_text=question,
        )

    assert payload is not None
    assert payload["_event_type"] == "wait_partial_answer_echo_observed"
    assert payload["prompt_echo"] is True
    assert payload["prompt_echo_match"] == "exact"
    assert worker_mod._wait_no_progress_event_is_progress(
        "wait_partial_answer_echo_observed",
        payload,
    ) is False


def test_wait_phase_stale_active_finalization_no_longer_extends_pro_grace(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_ACTIVE_FINALIZATION_NO_PROGRESS_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续输出最终结论"},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-stale-active-finalization-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="wait_active_finalization_progressed",
        payload={
            "in_progress_count": 1,
            "active_count": 1,
            "best_progress": 30.116840781560022,
            "best_role": "tool",
            "best_channel": None,
            "best_content_type": "text",
        },
        ts=time.time() - 20,
    )

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

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    clear_events = [
        item
        for item in events
        if item.get("type") == "wait_active_finalization_observed"
        and (item.get("payload") or {}).get("cleared") is True
    ]
    assert clear_events


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


def test_wait_phase_browser_retry_events_do_not_reset_no_progress_timeout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-browser-retry-noise-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="browser_retry_scheduled",
        payload={"phase": "wait", "error_type": "RuntimeError", "error_preview": "<RuntimeError: empty error>"},
        ts=time.time(),
    )

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

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"


def test_wait_phase_active_finalization_events_do_not_reset_no_progress_timeout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-active-finalization-noise-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="wait_active_finalization_observed",
        payload={
            "phase": "wait",
            "error_type": "RuntimeError",
            "error_preview": "我直接整理成符合要求的成稿。",
            "in_progress_count": 1,
            "active_count": 1,
            "best_progress": 71.42857142857143,
            "best_role": "tool",
            "best_channel": None,
            "best_content_type": "text",
        },
        ts=time.time(),
    )

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

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "needs_followup"
    assert data.get("reason_type") == "WaitNoProgressTimeout"


def test_wait_phase_pro_active_finalization_gets_longer_no_progress_grace(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_ACTIVE_FINALIZATION_NO_PROGRESS_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请继续输出完整的架构评审结论。"},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-pro-active-finalization-grace-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)
    _insert_job_event(
        db_path=env["db_path"],
        job_id=job_id,
        event_type="wait_active_finalization_observed",
        payload={
            "phase": "wait",
            "in_progress_count": 1,
            "active_count": 1,
            "best_progress": 55.55555555555556,
            "best_role": "tool",
            "best_channel": None,
            "best_content_type": "text",
        },
        ts=time.time(),
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={
                    "conversation_url": thread_url,
                    "retry_after_seconds": 0,
                    "export_active_finalization": True,
                    "export_active_finalization_details": {
                        "in_progress_count": 1,
                        "active_count": 1,
                        "best_progress": 55.55555555555556,
                        "best_role": "tool",
                        "best_channel": None,
                        "best_content_type": "text",
                    },
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "wait_no_progress_timeout" not in event_types


def test_wait_phase_partial_answer_progress_resets_no_progress_timeout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "请继续输出最终结论"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-partial-answer-progress-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer=(
                    "我已经完成了主要核验，现在正在把最终结论整理成结构化成稿。"
                    "当前可确认 Graphiti 仍然领先，但我还在把剩余风险与补证项收束成一版完整结论，"
                    "并会把 clean-room 复跑、真实 provenance 审计、以及最小补证建议整理成同一版最终回复。"
                ),
                answer_format="text",
                meta={"conversation_url": thread_url, "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "wait_partial_answer_progressed" in event_types
    assert "wait_no_progress_timeout" not in event_types


def test_wait_phase_active_finalization_progress_resets_no_progress_timeout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "请继续输出最终结论"}, "params": {"preset": "pro_extended"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-active-finalization-progress-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={
                    "conversation_url": thread_url,
                    "retry_after_seconds": 0,
                    "export_active_finalization": True,
                    "export_active_finalization_details": {
                        "in_progress_count": 1,
                        "active_count": 1,
                        "best_progress": 73.18314960841495,
                        "best_role": "tool",
                        "best_channel": None,
                        "best_content_type": "text",
                    },
                },
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "wait_active_finalization_progressed" in event_types
    assert "wait_no_progress_timeout" not in event_types


def test_wait_phase_regenerates_suspect_short_pro_answer_before_timeout(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_DEEP_RESEARCH_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_STATUS", "needs_followup")

    app = create_app()
    client = TestClient(app)
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请只基于附件给出最终判断"},
        "params": {"preset": "pro_extended", "min_chars": 200},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-regenerate-short-pro-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="我先把附件里直接支持的事实和需要外推的判断分开整理。",
                answer_format="text",
                meta={"conversation_url": thread_url, "retry_after_seconds": 0},
            )

    class _FakeToolCaller:
        def call_tool(self, tool_name: str, tool_args: dict, timeout_sec: float | None = None):  # noqa: ARG002
            if tool_name == "chatgpt_web_regenerate":
                return {
                    "ok": True,
                    "status": "in_progress",
                    "conversation_url": thread_url,
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())
    monkeypatch.setattr(worker_mod, "build_tool_caller", lambda **kwargs: _FakeToolCaller())  # noqa: ARG005

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "wait_regenerate_requested" in event_types
    assert "wait_no_progress_timeout" not in event_types


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


def test_wait_phase_deep_research_progress_stub_does_not_burn_browser_retry_budget(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_WINDOW_SECONDS", "900")
    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_JOB", "4")
    monkeypatch.setenv("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_PROVIDER", "999")
    monkeypatch.setenv("CHATGPTREST_DEEP_RESEARCH_PENDING_RETRY_AFTER_SECONDS", "600")

    app = create_app()
    client = TestClient(app)
    question = "请使用 Deep Research 给出 HomePC 本地模型部署路线。"
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc"
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": question},
        "params": {"preset": "pro_extended", "deep_research": True, "min_chars": 800},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "deep-research-progress-stub-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_in_progress(db_path=env["db_path"], job_id=job_id, age_seconds=30, conversation_url=thread_url)

    now = time.time()
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(4):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (
                    job_id,
                    now - 30,
                    "browser_retry_scheduled",
                    json.dumps({"provider_id": "chatgpt", "phase": "wait", "status": "wait"}, ensure_ascii=False),
                ),
            )
        conn.commit()

    progress_stub = (
        "# HomePC LLM 本地部署路线\n"
        "Update\n"
        "收集并审阅用户附件中的实验 memo 和历史 docs。\n"
        "检索并汇总近期关于 3090/4090/A6000/L40S/A100/H100 的本地 LLM 最佳实践。\n"
        "对比 Ollama、llama.cpp、vLLM、TensorRT-LLM 等后端的优劣与兼容性。\n"
        "生成结果表 schema、风险评估，并说明哪些结论基于本地证据或网页调研。\n\n"
        "Researching"
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": thread_url, "retry_after_seconds": 0},
            )

    async def _fake_export_conversation(**kwargs):  # noqa: ARG001
        export_path = env["artifacts_dir"] / "jobs" / job_id / "conversation.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_obj = {
            "conversation_id": "12345678-1234-1234-1234-123456789abc",
            "default_model_slug": "gpt-5-5-pro",
            "messages": [
                {"role": "user", "text": question, "status": "finished_successfully"},
                {
                    "role": "assistant",
                    "text": progress_stub,
                    "status": "finished_successfully",
                    "metadata": {"model_slug": "gpt-5-5-pro", "thinking_effort": "extended"},
                },
            ],
        }
        export_path.write_text(json.dumps(export_obj, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())
    monkeypatch.setattr(worker_mod, "_maybe_export_conversation", _fake_export_conversation)

    assert worker_mod._deep_research_export_should_finalize(progress_stub) is False

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data["phase"] == "wait"

    events = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=100").json()["events"]
    event_types = [str(item.get("type") or "") for item in events]
    assert "deep_research_pending_from_export" in event_types
    assert "wait_deep_research_pending_observed" in event_types
    assert "wait_partial_answer_progressed" in event_types
    assert "browser_retry_budget_exceeded" not in event_types
