from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import LeaseLost, claim_next_job, store_answer_result
from chatgptrest.core import job_store as job_store_mod
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_answer_not_found_404(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/jobs/not-exist/answer?offset=0&max_chars=10")
    assert r.status_code == 404


def test_answer_not_ready_409_has_status(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "ans-409"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ans = client.get(f"/v1/jobs/{job_id}/answer?offset=0&max_chars=10")
    assert ans.status_code == 409
    detail = ans.json()["detail"]
    assert detail["status"] == "queued"


@pytest.mark.parametrize(
    ("joined_paths", "expected_count"),
    [
        ("newline", 2),
        ("comma", 2),
    ],
)
def test_create_job_splits_joined_file_path_entries(
    env: dict[str, Path],
    tmp_path: Path,
    joined_paths: str,
    expected_count: int,
):
    app = create_app()
    client = TestClient(app)
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("A\n", encoding="utf-8")
    b.write_text("B\n", encoding="utf-8")
    blob = f"{a.as_posix()}\n{b.as_posix()}" if joined_paths == "newline" else f"{a.as_posix()},{b.as_posix()}"

    r = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请比较这两份材料的不同点。", "file_paths": [blob]},
            "params": {"preset": "pro"},
        },
        headers={"Idempotency-Key": f"joined-paths-{joined_paths}"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    request_path = env["artifacts_dir"] / "jobs" / job_id / "request.json"
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    file_paths = payload.get("input", {}).get("file_paths")
    assert isinstance(file_paths, list)
    assert len(file_paths) == expected_count
    assert file_paths == [a.as_posix(), b.as_posix()]


def test_answer_completed_missing_artifact_503(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 1, "delay_ms": 1}},
        headers={"Idempotency-Key": "ans-503"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}").json()
    answer_path = env["artifacts_dir"] / str(job["path"])
    assert answer_path.exists()
    answer_path.unlink()

    ans = client.get(f"/v1/jobs/{job_id}/answer?offset=0&max_chars=10")
    assert ans.status_code == 503


def test_store_answer_result_cleans_up_published_files_on_transition_failure(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 1, "delay_ms": 1}},
        headers={"Idempotency-Key": "transition-cleanup"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
        assert claimed is not None

    def _boom(*args, **kwargs):
        raise LeaseLost("simulated transition failure")

    monkeypatch.setattr(job_store_mod, "transition", _boom)

    with connect(env["db_path"]) as conn:
        with pytest.raises(LeaseLost):
            store_answer_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(claimed.lease_token or ""),
                answer="hello\n",
                answer_format="text",
            )

    job_dir = env["artifacts_dir"] / "jobs" / job_id
    assert not (job_dir / "answer.txt").exists()
    assert not (job_dir / "result.json").exists()
    assert not list(job_dir.glob("*.staging.*"))


def test_store_answer_result_transition_failure_preserves_existing_canonical_files(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hello"}, "params": {"repeat": 1, "delay_ms": 1}},
        headers={"Idempotency-Key": "transition-preserve-winner"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
        assert claimed is not None

    job_dir = env["artifacts_dir"] / "jobs" / job_id
    answer_path = job_dir / "answer.txt"
    result_path = job_dir / "result.json"
    answer_path.write_text("winner\n", encoding="utf-8")
    result_path.write_text(json.dumps({"ok": True, "path": "jobs/winner/answer.txt"}) + "\n", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise LeaseLost("simulated transition failure")

    monkeypatch.setattr(job_store_mod, "transition", _boom)

    with connect(env["db_path"]) as conn:
        with pytest.raises(LeaseLost):
            store_answer_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(claimed.lease_token or ""),
                answer="loser\n",
                answer_format="text",
            )

    assert answer_path.read_text(encoding="utf-8") == "winner\n"
    assert json.loads(result_path.read_text(encoding="utf-8"))["path"] == "jobs/winner/answer.txt"
    assert not list(job_dir.glob("*.staging.*"))


def test_preview_and_answer_follow_answer_path(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "FROMTXT"}, "params": {"repeat": 1, "delay_ms": 1}},
        headers={"Idempotency-Key": "path-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    # Create a competing markdown file with different content.
    job_dir = env["artifacts_dir"] / "jobs" / job_id
    (job_dir / "answer.md").write_text("FROMMD\n", encoding="utf-8")

    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["preview"].startswith("FROMTXT")

    ans = client.get(f"/v1/jobs/{job_id}/answer?offset=0&max_chars=20")
    assert ans.status_code == 200
    assert ans.json()["chunk"].startswith("FROMTXT")


def test_followup_parent_job_id_inherits_conversation_url(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    thread_url = "https://chatgpt.com/c/THREAD-123"
    r1 = client.post(
        "/v1/jobs",
        json={
            "kind": "dummy.conversation_echo",
            "input": {"text": "hi", "conversation_url": thread_url},
            "params": {"repeat": 1, "delay_ms": 1},
        },
        headers={"Idempotency-Key": "followup-parent"},
    )
    assert r1.status_code == 200
    parent_job_id = r1.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    parent = client.get(f"/v1/jobs/{parent_job_id}").json()
    assert parent["status"] == "completed"
    assert parent["conversation_url"] == thread_url

    r2 = client.post(
        "/v1/jobs",
        json={
            "kind": "dummy.conversation_echo",
            "input": {"text": "follow", "parent_job_id": parent_job_id},
            "params": {"repeat": 1, "delay_ms": 1},
        },
        headers={"Idempotency-Key": "followup-child"},
    )
    assert r2.status_code == 200
    child_job_id = r2.json()["job_id"]

    ran2 = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran2 is True

    child = client.get(f"/v1/jobs/{child_job_id}").json()
    assert child["status"] == "completed"
    assert child["parent_job_id"] == parent_job_id
    assert child["conversation_url"] == thread_url


def test_followup_parent_job_id_without_conversation_url_does_not_hard_fail(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    r1 = client.post(
        "/v1/jobs",
        json={
            "kind": "dummy.echo",
            "input": {"text": "parent-no-thread"},
            "params": {"repeat": 1, "delay_ms": 1},
        },
        headers={"Idempotency-Key": "followup-parent-no-thread"},
    )
    assert r1.status_code == 200
    parent_job_id = r1.json()["job_id"]

    ran_parent = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran_parent is True
    parent = client.get(f"/v1/jobs/{parent_job_id}").json()
    assert parent["status"] == "completed"
    assert not str(parent.get("conversation_url") or "").strip()

    r2 = client.post(
        "/v1/jobs",
        json={
            "kind": "dummy.conversation_echo",
            "input": {"text": "child-follow", "parent_job_id": parent_job_id},
            "params": {"repeat": 1, "delay_ms": 1},
        },
        headers={"Idempotency-Key": "followup-child-parent-no-thread"},
    )
    assert r2.status_code == 200
    child_job_id = r2.json()["job_id"]

    ran_child = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran_child is True
    child = client.get(f"/v1/jobs/{child_job_id}").json()
    assert child["status"] == "completed"
    assert child["parent_job_id"] == parent_job_id

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (child_job_id, "conversation_url_inherit_skipped"),
        ).fetchone()
    assert row is not None
    payload = json.loads(str(row["payload_json"] or "{}"))
    assert payload.get("parent_job_id") == parent_job_id
    assert payload.get("reason") == "parent_conversation_url_missing"


def test_followup_parent_job_id_inherits_deep_research_when_param_omitted(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    thread_url = "https://gemini.google.com/app/thread1234"
    parent = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "parent", "conversation_url": thread_url},
            "params": {"preset": "pro", "deep_research": True},
        },
        headers={"Idempotency-Key": "followup-dr-parent"},
    )
    assert parent.status_code == 200
    parent_job_id = parent.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, conversation_url = ?, conversation_id = ? WHERE job_id = ?",
            ("completed", thread_url, "thread1234", parent_job_id),
        )
        conn.commit()

    child = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "continue", "parent_job_id": parent_job_id},
            "params": {"preset": "pro"},
        },
        headers={"Idempotency-Key": "followup-dr-child-inherit"},
    )
    assert child.status_code == 200
    child_job_id = child.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT params_json, conversation_url FROM jobs WHERE job_id = ?",
            (child_job_id,),
        ).fetchone()
    assert row is not None
    params = json.loads(str(row["params_json"] or "{}"))
    assert params.get("deep_research") is True
    assert row["conversation_url"] == thread_url


def test_followup_parent_job_id_keeps_explicit_deep_research_false(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    thread_url = "https://gemini.google.com/app/thread5678"
    parent = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "parent", "conversation_url": thread_url},
            "params": {"preset": "pro", "deep_research": True},
        },
        headers={"Idempotency-Key": "followup-dr-parent-explicit-false"},
    )
    assert parent.status_code == 200
    parent_job_id = parent.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, conversation_url = ?, conversation_id = ? WHERE job_id = ?",
            ("completed", thread_url, "thread5678", parent_job_id),
        )
        conn.commit()

    child = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "continue without dr", "parent_job_id": parent_job_id},
            "params": {"preset": "pro", "deep_research": False},
        },
        headers={"Idempotency-Key": "followup-dr-child-explicit-false"},
    )
    assert child.status_code == 200
    child_job_id = child.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT params_json FROM jobs WHERE job_id = ?", (child_job_id,)).fetchone()
    assert row is not None
    params = json.loads(str(row["params_json"] or "{}"))
    assert params.get("deep_research") is False


def test_cancel_queued_writes_result_json(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "cancel-queued"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    c = client.post(f"/v1/jobs/{job_id}/cancel")
    assert c.status_code == 200
    assert c.json()["status"] == "canceled"

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["canceled"] is True

    ans = client.get(f"/v1/jobs/{job_id}/answer?offset=0&max_chars=10")
    assert ans.status_code == 409
    assert ans.json()["detail"]["status"] == "canceled"


def test_worker_error_writes_result_json(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.unknown", "input": {}, "params": {}},
        headers={"Idempotency-Key": "worker-error"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == "error"
    assert job["error"]

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["status"] == "error"


def test_lease_cas_prevents_old_worker_overwrite(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "lease-cas"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job1 = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job1 is not None

    # Force lease expiry, then reclaim by another worker.
    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?", (time.time() - 1, job_id))
        conn.commit()
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job2 = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w2", lease_ttl_seconds=60)
        conn.commit()
    assert job2 is not None

    # Old worker must not be able to finish.
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(LeaseLost):
            store_answer_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(job1.lease_token or ""),
                answer="A",
                answer_format="text",
            )
        conn.rollback()

    # New worker finishes successfully.
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        store_answer_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w2",
            lease_token=str(job2.lease_token or ""),
            answer="B",
            answer_format="text",
        )
        conn.commit()

    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == "completed"
    answer_path = env["artifacts_dir"] / str(job["path"])
    assert answer_path.read_text(encoding="utf-8") == "B\n"


def test_worker_heartbeat_prevents_reclaim(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "slow"}, "params": {"repeat": 1, "delay_ms": 4000}},
        headers={"Idempotency-Key": "heartbeat-1"},
    )
    assert r.status_code == 200

    async def run() -> None:
        worker_task = asyncio.create_task(
            _run_once(
                cfg=load_config(),
                worker_id="w1",
                lease_ttl_seconds=3,
            )
        )
        # Wait past initial TTL; without renewal another worker could reclaim.
        await asyncio.sleep(3.5)
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            reclaimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w2", lease_ttl_seconds=3)
            conn.commit()
        assert reclaimed is None
        await worker_task

    asyncio.run(run())


def test_idempotency_ignores_client_metadata(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload1 = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}, "client": {"a": 1}}
    payload2 = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}, "client": {"a": 2}}
    r1 = client.post("/v1/jobs", json=payload1, headers={"Idempotency-Key": "client-1"})
    assert r1.status_code == 200
    job_id = r1.json()["job_id"]
    r2 = client.post("/v1/jobs", json=payload2, headers={"Idempotency-Key": "client-1"})
    assert r2.status_code == 200
    assert r2.json()["job_id"] == job_id


def test_idempotency_concurrent_post_same_key(env: dict[str, Path]):
    app = create_app()
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}

    async def run() -> list[str]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async def submit() -> str:
                r = await client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conc-1"})
                assert r.status_code == 200
                return str(r.json()["job_id"])

            return await asyncio.gather(*[submit() for _ in range(20)])

    job_ids = asyncio.run(run())
    assert len(set(job_ids)) == 1
