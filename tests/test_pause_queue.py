from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job
from chatgptrest.core.pause import set_pause_state


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_REQUIRE_OPS_TOKEN_FOR_REPAIR_KINDS", "0")
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _create_job(client: TestClient, *, idem: str, kind: str, input: dict, params: dict):
    r = client.post("/v1/jobs", json={"kind": kind, "input": input, "params": params}, headers={"Idempotency-Key": idem})
    assert r.status_code == 200
    return str(r.json()["job_id"])


def test_pause_send_skips_send_phase_non_repair_jobs(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    send_id = _create_job(client, idem="pause-send-1", kind="dummy.echo", input={"text": "hi"}, params={"repeat": 1})
    repair_id = _create_job(
        client,
        idem="pause-send-2",
        kind="repair.check",
        input={"job_id": "t1", "symptom": "x"},
        params={"mode": "quick", "timeout_seconds": 5, "probe_driver": False},
    )
    wait_id = _create_job(client, idem="pause-send-3", kind="dummy.echo", input={"text": "wait"}, params={"repeat": 1})

    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id = ?", (wait_id,))
        set_pause_state(conn, mode="send", until_ts=time.time() + 60, reason="test")
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert claimed is not None
    assert claimed.job_id != send_id
    assert claimed.job_id in {repair_id, wait_id}


def test_pause_send_allows_wait_phase_when_no_repair(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    send_id = _create_job(client, idem="pause-send-only-1", kind="dummy.echo", input={"text": "hi"}, params={"repeat": 1})
    wait_id = _create_job(client, idem="pause-send-only-2", kind="dummy.echo", input={"text": "wait"}, params={"repeat": 1})

    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id = ?", (wait_id,))
        set_pause_state(conn, mode="send", until_ts=time.time() + 60, reason="test")
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == wait_id
    assert claimed.job_id != send_id


def test_pause_all_allows_only_repair(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    wait_id = _create_job(client, idem="pause-all-1", kind="dummy.echo", input={"text": "wait"}, params={"repeat": 1})
    repair_id = _create_job(
        client,
        idem="pause-all-2",
        kind="repair.check",
        input={"job_id": "t1", "symptom": "x"},
        params={"mode": "quick", "timeout_seconds": 5, "probe_driver": False},
    )

    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id = ?", (wait_id,))
        set_pause_state(conn, mode="all", until_ts=time.time() + 60, reason="test")
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == repair_id
