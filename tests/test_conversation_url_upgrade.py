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


def test_set_conversation_url_upgrades_gemini_base_app_url(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-url-upgrade-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job is not None
    lease_token = str(job.lease_token or "")

    base_url = "https://gemini.google.com/app"
    thread_url = "https://gemini.google.com/app/d6d83d5b6fe00ea7"

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=base_url,
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
            conversation_url=thread_url,
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT conversation_url FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert row is not None
    assert str(row["conversation_url"] or "") == thread_url


def test_set_conversation_url_upgrades_chatgpt_base_url(env: dict[str, Path]) -> None:
    """ChatGPT base→thread upgrade via merged can_upgrade OR path."""
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-url-upgrade-chatgpt-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job is not None
    lease_token = str(job.lease_token or "")

    base_url = "https://chatgpt.com/"
    thread_url = "https://chatgpt.com/c/67bc52cf-2d68-8012-bf1a-c0124dbb5420"

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_conversation_url(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=lease_token,
            conversation_url=base_url,
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
            conversation_url=thread_url,
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT conversation_url FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert row is not None
    assert str(row["conversation_url"] or "") == thread_url
