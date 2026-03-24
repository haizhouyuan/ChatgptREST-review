from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import create_job
from chatgptrest.worker.worker import _maybe_submit_worker_autofix


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX", "1")
    monkeypatch.setenv("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_WINDOW_SECONDS", "60")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_worker_auto_autofix_submits_repair_job(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review the dashboard routing changes and explain the regression risk."},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "autofix-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    cfg = load_config()
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=job_id,
            kind="chatgpt_web.ask",
            status="cooldown",
            error_type="TimeoutError",
            error="Locator.click: Timeout 30000ms exceeded.",
            conversation_url=None,
        )
    )

    with connect(env["db_path"]) as conn:
        repair = conn.execute("SELECT job_id, kind FROM jobs WHERE kind = 'repair.autofix'").fetchall()
        assert len(repair) == 1
        row = conn.execute(
            "SELECT params_json FROM jobs WHERE kind = 'repair.autofix' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        params = json.loads(str(row["params_json"] or "{}"))
        assert params["model"] == "gpt-5.3-codex-spark"
        events = conn.execute(
            "SELECT type FROM job_events WHERE job_id = ? AND type = ?",
            (job_id, "auto_autofix_submitted"),
        ).fetchall()
        assert events


def test_worker_auto_autofix_skips_inprogress(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review the dashboard routing changes and explain the regression risk."},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "autofix-2"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    cfg = load_config()
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=job_id,
            kind="chatgpt_web.ask",
            status="cooldown",
            error_type="InProgress",
            error="job still in progress; retry later",
            conversation_url=None,
        )
    )

    with connect(env["db_path"]) as conn:
        repair = conn.execute("SELECT job_id FROM jobs WHERE kind = 'repair.autofix'").fetchall()
        assert not repair


def test_worker_auto_autofix_submits_for_wait_timeout_needs_followup(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review the dashboard routing changes and explain the regression risk."},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "autofix-3"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    cfg = load_config()
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=job_id,
            kind="chatgpt_web.ask",
            status="needs_followup",
            error_type="WaitNoProgressTimeout",
            error="wait phase made no progress; age=3600s threshold=1800s",
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000001",
        )
    )

    with connect(env["db_path"]) as conn:
        repair = conn.execute("SELECT job_id, kind FROM jobs WHERE kind = 'repair.autofix'").fetchall()
        assert len(repair) == 1
        events = conn.execute(
            "SELECT type FROM job_events WHERE job_id = ? AND type = ?",
            (job_id, "auto_autofix_submitted"),
        ).fetchall()
        assert events


def test_worker_auto_autofix_submits_regenerate_for_pro_instant_answer(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review the dashboard routing changes and explain the regression risk."},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "autofix-pro-instant-answer"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    cfg = load_config()
    conversation_url = "https://chatgpt.com/c/00000000-0000-0000-0000-000000000002"
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=job_id,
            kind="chatgpt_web.ask",
            status="needs_followup",
            error_type="ProInstantAnswerNeedsRegenerate",
            error="thinking preset produced a suspicious fast answer; request regenerate on the same conversation",
            conversation_url=conversation_url,
        )
    )

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT params_json FROM jobs WHERE kind = 'repair.autofix' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        params = json.loads(str(row["params_json"] or "{}"))
        assert params["model"] == "gpt-5.3-codex-spark"
        allow_actions = params.get("allow_actions") or []
        assert "regenerate" in allow_actions
        assert "refresh" in allow_actions


def test_worker_auto_autofix_dedupes_same_conversation_within_cooldown(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_CONVERSATION_COOLDOWN_SECONDS", "3600")
    app = create_app()
    client = TestClient(app)
    conversation_url = "https://chatgpt.com/c/00000000-0000-0000-0000-000000000099"

    payload1 = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review the dashboard routing changes.", "conversation_url": conversation_url},
        "params": {"preset": "pro_extended", "allow_queue": True},
    }
    payload2 = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Continue the dashboard routing review.", "conversation_url": conversation_url},
        "params": {"preset": "pro_extended", "allow_queue": True},
    }
    r1 = client.post("/v1/jobs", json=payload1, headers={"Idempotency-Key": "autofix-dedupe-1"})
    r2 = client.post("/v1/jobs", json=payload2, headers={"Idempotency-Key": "autofix-dedupe-2"})
    assert r1.status_code == 200
    assert r2.status_code == 200

    cfg = load_config()
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=r1.json()["job_id"],
            kind="chatgpt_web.ask",
            status="needs_followup",
            error_type="WaitNoProgressTimeout",
            error="wait phase made no progress; age=3600s threshold=1800s",
            conversation_url=conversation_url,
        )
    )
    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=r2.json()["job_id"],
            kind="chatgpt_web.ask",
            status="needs_followup",
            error_type="WaitNoProgressTimeout",
            error="wait phase made no progress; age=3600s threshold=1800s",
            conversation_url=conversation_url,
        )
    )

    with connect(env["db_path"]) as conn:
        rows = conn.execute(
            "SELECT job_id FROM jobs WHERE kind = 'repair.autofix' ORDER BY created_at ASC"
        ).fetchall()
        assert len(rows) == 1


def test_worker_auto_autofix_skips_synthetic_source_job(env: dict[str, Path]) -> None:
    cfg = load_config()
    with connect(env["db_path"]) as conn:
        source = create_job(
            conn,
            artifacts_dir=cfg.artifacts_dir,
            idempotency_key="synthetic-source-1",
            kind="chatgpt_web.ask",
            input={"question": "hello\n\n--- 附加上下文 ---\n- depth: standard"},
            params={"preset": "auto", "allow_live_chatgpt_smoke": True},
            client={"name": "advisor_ask"},
            requested_by={"transport": "test"},
            max_attempts=1,
        )
        conn.commit()

    asyncio.run(
        _maybe_submit_worker_autofix(
            cfg=cfg,
            job_id=source.job_id,
            kind="chatgpt_web.ask",
            status="needs_followup",
            error_type="WaitNoProgressTimeout",
            error="wait phase made no progress; age=3600s threshold=1800s",
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000123",
        )
    )

    with connect(env["db_path"]) as conn:
        repair = conn.execute("SELECT job_id FROM jobs WHERE kind = 'repair.autofix'").fetchall()
        assert not repair
        events = conn.execute(
            "SELECT type FROM job_events WHERE job_id = ?",
            (source.job_id,),
        ).fetchall()
        assert any(str(row["type"]) == "auto_autofix_skipped_synthetic_source" for row in events)
