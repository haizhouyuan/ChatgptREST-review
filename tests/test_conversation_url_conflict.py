from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job, set_conversation_url


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_set_conversation_url_does_not_overwrite_existing_thread(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-url-conflict-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job is not None
    lease_token = str(job.lease_token or "")

    url1 = "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    url2 = "https://chatgpt.com/c/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=url1,
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=url2,
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT conversation_url FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert row is not None
    assert str(row["conversation_url"] or "") == url1


def test_set_conversation_url_rebinds_gemini_thread_for_in_progress_followup(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "gemini_web.ask", "input": {"question": "hi"}, "params": {"preset": "pro"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-url-rebind-gemini-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job is not None
    lease_token = str(job.lease_token or "")

    url1 = "https://gemini.google.com/app/aaaaaaaaaaaaaaaa"
    url2 = "https://gemini.google.com/app/bbbbbbbbbbbbbbbb"

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=url1,
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=url2,
        )
        conn.commit()
        row = conn.execute("SELECT conversation_url FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        event = conn.execute(
            "SELECT type FROM job_events WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()

    assert row is not None
    assert str(row["conversation_url"] or "") == url2
    assert event is not None
    assert str(event["type"] or "") == "conversation_url_rebound"
