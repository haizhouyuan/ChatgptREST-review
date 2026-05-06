"""L6-2: DB corruption recovery.

Tests how the system handles various forms of SQLite corruption:
- Missing file (auto-creates via init_db)
- Zero-byte file
- Corrupted data (non-SQLite content)
- Missing tables (init_db recreates)
- WAL checkpoint survival
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from chatgptrest.core.advisor_runs import (
    create_run,
    get_run,
)
from chatgptrest.core.db import connect, init_db


# ---------------------------------------------------------------------------
# L6-2a: Missing DB file auto-creates
# ---------------------------------------------------------------------------

def test_missing_db_auto_creates(tmp_path: Path):
    """When the DB file doesn't exist, init_db should create it."""
    db_path = tmp_path / "new_db.sqlite3"
    assert not db_path.exists()

    init_db(db_path)
    assert db_path.exists()

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="run-new-001",
            request_id="req-new",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="new db test",
            normalized_question="new db test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        run = get_run(conn, run_id="run-new-001")
        assert run is not None


# ---------------------------------------------------------------------------
# L6-2b: Empty file (zero bytes) handled gracefully
# ---------------------------------------------------------------------------

def test_zero_byte_db_handled(tmp_path: Path):
    """A zero-byte DB file should be handled by init_db."""
    db_path = tmp_path / "empty.sqlite3"
    db_path.write_bytes(b"")

    init_db(db_path)
    with connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "jobs" in tables
        assert "advisor_runs" in tables

        run = create_run(
            conn,
            run_id="run-zerob-001",
            request_id="req-z",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="zero byte test",
            normalized_question="zero byte test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()
        assert run is not None


# ---------------------------------------------------------------------------
# L6-2c: Corrupted file (non-SQLite content) handled
# ---------------------------------------------------------------------------

def test_corrupted_db_raises_error(tmp_path: Path):
    """A file with non-SQLite content should raise DatabaseError."""
    db_path = tmp_path / "corrupt.sqlite3"
    db_path.write_bytes(b"this is not a sqlite database at all" * 10)

    with pytest.raises((sqlite3.DatabaseError, sqlite3.OperationalError)):
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT * FROM sqlite_master")


# ---------------------------------------------------------------------------
# L6-2d: Table missing — init_db recreates
# ---------------------------------------------------------------------------

def test_missing_table_recreated(tmp_path: Path):
    """If advisor_runs table is missing, init_db should create it."""
    db_path = tmp_path / "no_table.sqlite3"

    # Create empty DB (no tables)
    raw_conn = sqlite3.connect(str(db_path))
    raw_conn.close()

    # init_db should create all tables
    init_db(db_path)
    with connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='advisor_runs'"
        ).fetchall()
        assert len(tables) == 1


# ---------------------------------------------------------------------------
# L6-2e: Data survives WAL checkpoint
# ---------------------------------------------------------------------------

def test_data_survives_wal_checkpoint(tmp_path: Path):
    """Data written in WAL mode survives a checkpoint and reopen."""
    db_path = tmp_path / "wal_test.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        create_run(
            conn,
            run_id="run-wal-001",
            request_id="req-wal",
            mode="balanced",
            status="COMPLETED",
            route="quick_ask",
            raw_question="WAL test",
            normalized_question="WAL test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(FULL)")

    # Reopen and verify
    with connect(db_path) as conn:
        run = get_run(conn, run_id="run-wal-001")
        assert run is not None
        assert run["status"] == "COMPLETED"
