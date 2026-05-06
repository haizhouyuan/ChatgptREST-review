from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    return create_app()


def test_wait_route_auto_wait_cooldown(monkeypatch: pytest.MonkeyPatch, app, tmp_path: Path) -> None:
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    created = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "k1"})
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    # Force the job into cooldown with a future not_before.
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status='cooldown', not_before=?, updated_at=? WHERE job_id=?",
            (1005.0, 1000.0, job_id),
        )
        conn.commit()

    import chatgptrest.api.routes_jobs as routes

    now = {"t": 1000.0}
    sleeps: list[float] = []

    def fake_time() -> float:
        return float(now["t"])

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(float(seconds))
        now["t"] += float(seconds)

    monkeypatch.setattr(routes.time, "time", fake_time)
    monkeypatch.setattr(routes.asyncio, "sleep", fake_sleep)

    # Default: cooldown is DONEISH, so /wait returns immediately (no sleeps).
    r1 = client.get(f"/v1/jobs/{job_id}/wait?timeout_seconds=1&poll_seconds=0.2")
    assert r1.status_code == 200
    assert r1.json()["status"] == "cooldown"
    assert sleeps == []

    # With auto_wait_cooldown, /wait keeps waiting until deadline (sleep recorded).
    now["t"] = 1000.0
    sleeps.clear()
    r2 = client.get(f"/v1/jobs/{job_id}/wait?timeout_seconds=1&poll_seconds=0.2&auto_wait_cooldown=1")
    assert r2.status_code == 200
    assert r2.json()["status"] == "cooldown"
    assert sleeps == [1.0]

