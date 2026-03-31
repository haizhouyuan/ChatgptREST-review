from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB


def test_connect_sets_busy_timeout_to_30s(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "evomap.db"))
    conn = db.connect()
    try:
        busy_timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert busy_timeout_ms == 30000
    finally:
        db.close()


class _RetryThenPassConn:
    def __init__(self, failures: int) -> None:
        self.failures_remaining = failures
        self.attempts = 0
        self.rollbacks = 0
        self.commits = 0

    def execute(self, sql: str, params: list[object]):
        self.attempts += 1
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise sqlite3.OperationalError("database is locked")
        return _FakeCursor(rowcount=1)

    def rollback(self) -> None:
        self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1


class _FakeCursor:
    def __init__(self, *, rowcount: int) -> None:
        self.rowcount = rowcount


class _RecordingLock:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False


def test_insert_retries_locked_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    db = KnowledgeDB(db_path=":memory:")
    fake_conn = _RetryThenPassConn(failures=2)
    db._conn = fake_conn  # type: ignore[assignment]
    sleeps: list[float] = []
    monkeypatch.setattr("chatgptrest.evomap.knowledge.db.time.sleep", sleeps.append)

    db._insert("atoms", {"atom_id": "at_1"})

    assert fake_conn.attempts == 3
    assert fake_conn.rollbacks == 2
    assert fake_conn.commits == 1
    assert sleeps == [0.2, 0.4]


def test_insert_does_not_retry_non_lock_errors() -> None:
    class _BrokenConn:
        def __init__(self) -> None:
            self.attempts = 0

        def execute(self, sql: str, params: list[object]):
            self.attempts += 1
            raise sqlite3.OperationalError("syntax error")

        def rollback(self) -> None:  # pragma: no cover - should never be called
            raise AssertionError("rollback should not be called")

    db = KnowledgeDB(db_path=":memory:")
    fake_conn = _BrokenConn()
    db._conn = fake_conn  # type: ignore[assignment]

    with pytest.raises(sqlite3.OperationalError, match="syntax error"):
        db._insert("atoms", {"atom_id": "at_1"})

    assert fake_conn.attempts == 1


def test_insert_if_absent_retries_locked_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    db = KnowledgeDB(db_path=":memory:")
    fake_conn = _RetryThenPassConn(failures=2)
    db._conn = fake_conn  # type: ignore[assignment]
    sleeps: list[float] = []
    monkeypatch.setattr("chatgptrest.evomap.knowledge.db.time.sleep", sleeps.append)

    inserted = db._insert_if_absent("episodes", {"episode_id": "ep_1"})

    assert inserted is True
    assert fake_conn.attempts == 3
    assert fake_conn.rollbacks == 2
    assert fake_conn.commits == 1
    assert sleeps == [0.2, 0.4]


def test_insert_if_absent_returns_false_when_row_exists() -> None:
    class _IgnoreConn:
        def __init__(self) -> None:
            self.commits = 0

        def execute(self, sql: str, params: list[object]):
            return _FakeCursor(rowcount=0)

        def rollback(self) -> None:  # pragma: no cover - should never be called
            raise AssertionError("rollback should not be called")

        def commit(self) -> None:
            self.commits += 1

    db = KnowledgeDB(db_path=":memory:")
    db._conn = _IgnoreConn()  # type: ignore[assignment]

    inserted = db._insert_if_absent("episodes", {"episode_id": "ep_1"})

    assert inserted is False
    assert db._conn.commits == 1  # type: ignore[union-attr]


def test_bulk_put_atoms_defers_commit_until_batch_end() -> None:
    class _BatchConn:
        def __init__(self) -> None:
            self.commits = 0
            self.statements: list[str] = []

        def execute(self, sql: str, params: list[object]):
            self.statements.append(sql)
            return _FakeCursor(rowcount=1)

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:  # pragma: no cover - should never be called
            raise AssertionError("rollback should not be called")

    db = KnowledgeDB(db_path=":memory:")
    db._conn = _BatchConn()  # type: ignore[assignment]

    atom = type(
        "_Atom",
        (),
        {
            "hash": "hash-1",
            "to_row": lambda self: {"atom_id": "at_1"},
            "compute_hash": lambda self: None,
        },
    )()

    db.bulk_put_atoms([atom])  # type: ignore[arg-type]

    assert db._conn.commits == 1  # type: ignore[union-attr]


def test_insert_uses_process_local_write_lock() -> None:
    db = KnowledgeDB(db_path=":memory:")
    fake_conn = _RetryThenPassConn(failures=0)
    fake_lock = _RecordingLock()
    db._conn = fake_conn  # type: ignore[assignment]
    db._write_lock = fake_lock  # type: ignore[assignment]

    db._insert("atoms", {"atom_id": "at_1"})

    assert fake_lock.entered == 1
    assert fake_lock.exited == 1
    assert fake_conn.commits == 1
