"""Tests for EventBatch (Opt-3).

Verifies that the ``EventBatch`` collector correctly accumulates events
and flushes them in a single transaction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest.core.db import connect
from chatgptrest.core.event_batch import EventBatch


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    # Initialise DB schema by importing and loading config (triggers create_app side-effects).
    from chatgptrest.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    client = TestClient(app)
    # Create a dummy job so the schema is ready.
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "batch-test-setup"},
    )
    assert r.status_code == 200
    return {"db_path": db_path, "artifacts_dir": artifacts_dir, "job_id": r.json()["job_id"]}


def test_batch_flush_writes_all_events(env: dict) -> None:
    """flush() should write all accumulated events in one go."""
    batch = EventBatch()
    job_id = env["job_id"]
    batch.add(job_id, type="test_event_a", payload={"key": "val1"})
    batch.add(job_id, type="test_event_b", payload={"key": "val2"})
    batch.add(job_id, type="test_event_c")

    assert batch.pending_count == 3

    with connect(env["db_path"]) as conn:
        batch.flush(conn, artifacts_dir=env["artifacts_dir"])

    assert batch.pending_count == 0

    with connect(env["db_path"]) as conn:
        rows = conn.execute(
            "SELECT type, payload_json FROM job_events WHERE job_id = ? AND type LIKE 'test_event_%' ORDER BY id",
            (job_id,),
        ).fetchall()

    assert len(rows) == 3
    assert rows[0]["type"] == "test_event_a"
    assert json.loads(rows[0]["payload_json"]) == {"key": "val1"}
    assert rows[1]["type"] == "test_event_b"
    assert rows[2]["type"] == "test_event_c"
    assert rows[2]["payload_json"] is None


def test_batch_empty_flush_is_noop(env: dict) -> None:
    """Flushing an empty batch should not open any transaction."""
    batch = EventBatch()

    with connect(env["db_path"]) as conn:
        batch.flush(conn, artifacts_dir=env["artifacts_dir"])

    assert batch.pending_count == 0


def test_batch_flush_clears_pending(env: dict) -> None:
    """After flush, pending events should be empty and another flush is a noop."""
    batch = EventBatch()
    batch.add(env["job_id"], type="test_clear_a")
    batch.add(env["job_id"], type="test_clear_b")

    with connect(env["db_path"]) as conn:
        batch.flush(conn, artifacts_dir=env["artifacts_dir"])

    assert batch.pending_count == 0

    # Second flush — nothing happens.
    with connect(env["db_path"]) as conn:
        batch.flush(conn, artifacts_dir=env["artifacts_dir"])

    with connect(env["db_path"]) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM job_events WHERE job_id = ? AND type LIKE 'test_clear_%'",
            (env["job_id"],),
        ).fetchone()[0]
    assert count == 2
