from __future__ import annotations

from pathlib import Path

import pytest

from chatgptrest.core.db import connect
from chatgptrest.core.idempotency import IdempotencyCollision, begin


def test_begin_insert_then_replay(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        out1 = begin(conn, idempotency_key="k", request_hash="h1", job_id="j1")
        conn.commit()
    assert out1.created is True
    assert out1.job_id == "j1"

    # Second call hits UNIQUE constraint and must replay safely (no 500s).
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        out2 = begin(conn, idempotency_key="k", request_hash="h1", job_id="j2")
        conn.commit()
    assert out2.created is False
    assert out2.job_id == "j1"


def test_begin_collision_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        begin(conn, idempotency_key="k", request_hash="h1", job_id="j1")
        conn.commit()

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(IdempotencyCollision):
            begin(conn, idempotency_key="k", request_hash="h2", job_id="j2")
        conn.rollback()
