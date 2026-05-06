from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.repair_jobs import create_repair_autofix_job
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _create_job(client: TestClient, *, idem: str, kind: str, input: dict, params: dict) -> str:
    r = client.post("/v1/jobs", json={"kind": kind, "input": input, "params": params}, headers={"Idempotency-Key": idem})
    assert r.status_code == 200
    return str(r.json()["job_id"])


def test_wait_claim_prioritizes_gemini_deep_research_with_thread_url(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    generic_wait_id = _create_job(
        client,
        idem="claim-priority-generic-1",
        kind="dummy.echo",
        input={"text": "generic wait"},
        params={"repeat": 1},
    )
    gemini_missing_thread_id = _create_job(
        client,
        idem="claim-priority-gemini-missing-thread-1",
        kind="gemini_web.ask",
        input={"question": "请比较普通搜索和深度研究。"},
        params={"preset": "pro", "deep_research": True},
    )
    gemini_thread_id = _create_job(
        client,
        idem="claim-priority-gemini-thread-1",
        kind="gemini_web.ask",
        input={"question": "请帮我做一份家庭教育调研。"},
        params={"preset": "pro", "deep_research": True},
    )

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET phase = 'wait', conversation_url = ?, conversation_id = ? WHERE job_id = ?",
            ("https://gemini.google.com/app/8b5f4e0e4e3d0aa1", "8b5f4e0e4e3d0aa1", gemini_thread_id),
        )
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id IN (?, ?)", (generic_wait_id, gemini_missing_thread_id))
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w-wait-1",
            lease_ttl_seconds=60,
            phase="wait",
        )
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == gemini_thread_id


def test_wait_claim_priority_respects_kind_prefix(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    gemini_thread_id = _create_job(
        client,
        idem="claim-priority-kind-prefix-gemini-1",
        kind="gemini_web.ask",
        input={"question": "请解释记忆系统为什么需要隔离。"},
        params={"preset": "pro", "deep_research": True},
    )
    dummy_wait_id = _create_job(
        client,
        idem="claim-priority-kind-prefix-dummy-1",
        kind="dummy.echo",
        input={"text": "dummy wait"},
        params={"repeat": 1},
    )

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET phase = 'wait', conversation_url = ?, conversation_id = ? WHERE job_id = ?",
            ("https://gemini.google.com/app/3d96df91f65f98b2", "3d96df91f65f98b2", gemini_thread_id),
        )
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id = ?", (dummy_wait_id,))
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w-wait-2",
            lease_ttl_seconds=60,
            phase="wait",
            kind_prefix="dummy.",
        )
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == dummy_wait_id


def test_send_claim_prioritizes_non_repair_jobs_ahead_of_repair(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    target_job_id = _create_job(
        client,
        idem="claim-priority-send-target-1",
        kind="dummy.echo",
        input={"text": "target"},
        params={"repeat": 1},
    )
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        create_repair_autofix_job(
            conn=conn,
            artifacts_dir=env["artifacts_dir"],
            idempotency_key="claim-priority-send-repair-1",
            client_name="test_repair_autofix",
            job_id=target_job_id,
            symptom="TimeoutError: empty error",
            allow_actions=["capture_ui"],
            apply_actions=False,
        )
        conn.commit()

    ask_job_id = _create_job(
        client,
        idem="claim-priority-send-gemini-1",
        kind="gemini_web.ask",
        input={"question": "请整理三条下一步推进建议。"},
        params={"preset": "pro"},
    )

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET status = 'completed' WHERE job_id = ?",
            (target_job_id,),
        )
        conn.execute(
            "UPDATE jobs SET not_before = 0 WHERE job_id = ?",
            (ask_job_id,),
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w-send-priority",
            lease_ttl_seconds=60,
            phase="send",
        )
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == ask_job_id
