from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_RESCUE_FOLLOWUP_GUARD", "1")
    monkeypatch.setenv("CHATGPTREST_RESCUE_FOLLOWUP_GRACE_SECONDS", "1")
    return {"tmp_path": tmp_path, "db_path": db_path, "artifacts_dir": artifacts_dir}


def test_rescue_followup_does_not_shortcircuit_when_parent_already_completed(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    client = TestClient(app)

    # 1) Create and complete a parent job that has an answer file.
    parent_payload = {"kind": "dummy.echo", "input": {"text": "parent-answer"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=parent_payload, headers={"Idempotency-Key": "parent"})
    assert r.status_code == 200
    parent_job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-parent", lease_ttl_seconds=60))
    assert ran is True

    # Inject a conversation_url so follow-up inheritance path is exercised.
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET conversation_url = ? WHERE job_id = ?",
            ("https://chatgpt.com/c/test", parent_job_id),
        )
        conn.commit()

    # 2) Create a follow-up chatgpt_web.ask job (rescue-style question).
    follow_payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "继续。请直接输出最终结论，不要写代码。", "parent_job_id": parent_job_id},
        "params": {"preset": "pro_extended"},
    }
    r2 = client.post("/v1/jobs", json=follow_payload, headers={"Idempotency-Key": "follow"})
    assert r2.status_code == 200
    follow_job_id = r2.json()["job_id"]

    calls = {"count": 0}
    follow_answer = (
        "最终结论：建议继续推进当前方案。"
        "父任务已经完成，因此这次 follow-up 应被当作一次新的、有意图的继续追问处理，"
        "而不是被 rescue guard 直接短路回父任务答案。"
        "当前风险可控，下一步应进入落地执行和验证阶段。"
    )

    class _StubExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002, ARG002
            calls["count"] += 1
            return ExecutorResult(
                status="completed",
                answer=follow_answer,
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test"},
            )

    import chatgptrest.worker.worker as worker_mod

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _StubExecutor())

    # Run send worker once: since the parent is already completed, this follow-up is intentional
    # and must not be short-circuited.
    ran2 = asyncio.run(_run_once(cfg=load_config(), worker_id="w-send", lease_ttl_seconds=60, role="send"))
    assert ran2 is True
    assert calls["count"] == 1

    job = client.get(f"/v1/jobs/{follow_job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "completed"
    ans = client.get(f"/v1/jobs/{follow_job_id}/answer?offset=0&max_chars=200")
    assert ans.status_code == 200
    assert (ans.json().get("chunk") or "").startswith("最终结论：建议继续推进当前方案。")


def test_rescue_followup_shortcircuits_when_parent_completes_during_grace(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    client = TestClient(app)

    # 1) Create a parent job and mark it as in_progress, with a conversation_url already known.
    parent_payload = {"kind": "dummy.echo", "input": {"text": "parent-answer"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=parent_payload, headers={"Idempotency-Key": "parent2"})
    assert r.status_code == 200
    parent_job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status = ?, conversation_url = ?, lease_owner = ?, lease_token = ?, lease_expires_at = ? WHERE job_id = ?",
            ("in_progress", "https://chatgpt.com/c/test", "w-parent", "lease-token", time.time() + 60.0, parent_job_id),
        )
        conn.commit()

    # 2) Create a rescue-style follow-up that would normally be sent, but should short-circuit
    # if the parent completes during the grace window.
    follow_payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "继续。上一次回答卡住了。请直接输出最终结论，不要写代码。", "parent_job_id": parent_job_id},
        "params": {"preset": "pro_extended"},
    }
    r2 = client.post("/v1/jobs", json=follow_payload, headers={"Idempotency-Key": "follow2"})
    assert r2.status_code == 200
    follow_job_id = r2.json()["job_id"]

    # Avoid any real driver access: the guard must complete the job without calling executor.run.
    class _ExplodingExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002, ARG002
            raise AssertionError("executor.run must not be called when rescue follow-up short-circuits")

    import chatgptrest.worker.worker as worker_mod

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _ExplodingExecutor())

    # Complete the parent shortly after the follow-up starts waiting (race simulation).
    def _complete_parent() -> None:
        time.sleep(0.05)
        text = "parent-answer"
        answer_text = text if text.endswith("\n") else text + "\n"
        sha = hashlib.sha256(answer_text.encode("utf-8", errors="replace")).hexdigest()
        rel_path = f"jobs/{parent_job_id}/answer.txt"
        (env["artifacts_dir"] / rel_path).parent.mkdir(parents=True, exist_ok=True)
        (env["artifacts_dir"] / rel_path).write_text(answer_text, encoding="utf-8")
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE jobs SET status = ?, answer_path = ?, answer_format = ?, answer_sha256 = ?, answer_chars = ? WHERE job_id = ?",
                ("completed", rel_path, "text", sha, len(answer_text), parent_job_id),
            )
            conn.commit()

    t = threading.Thread(target=_complete_parent, daemon=True)
    t.start()

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-send", lease_ttl_seconds=60, role="send"))
    assert ran is True
    t.join(timeout=2.0)

    job = client.get(f"/v1/jobs/{follow_job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "completed"
    ans = client.get(f"/v1/jobs/{follow_job_id}/answer?offset=0&max_chars=200")
    assert ans.status_code == 200
    assert (ans.json().get("chunk") or "").startswith("parent-answer")

    # Confirm the short-circuit event is recorded in job artifacts.
    events_path = env["artifacts_dir"] / "jobs" / follow_job_id / "events.jsonl"
    assert events_path.exists()
    text = events_path.read_text(encoding="utf-8", errors="replace")
    assert "rescue_followup_shortcircuited" in text
