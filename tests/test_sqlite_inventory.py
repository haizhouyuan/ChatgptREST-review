from __future__ import annotations

import sqlite3
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.sqlite_inventory import (
    analyze_sqlite_database,
    discover_sqlite_databases,
    filter_sqlite_databases,
    ingest_sqlite_inventory,
)


def _make_sample_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, payload BLOB)")
    conn.execute("CREATE VIEW task_titles AS SELECT id, title FROM tasks")
    conn.execute(
        "INSERT INTO tasks (title, payload) VALUES (?, ?), (?, ?)",
        ("alpha", b"\x00\x01\x02", "beta", b"\x03\x04"),
    )
    conn.commit()
    conn.close()


def test_analyze_sqlite_database_collects_tables_views_and_samples(tmp_path: Path) -> None:
    db_path = tmp_path / "sample.sqlite3"
    _make_sample_db(db_path)

    inventory = analyze_sqlite_database(db_path, sample_rows=2)

    assert inventory.project == "external"
    assert inventory.table_count == 1
    assert inventory.view_count == 1
    assert inventory.total_rows == 4
    tasks = next(item for item in inventory.tables if item.name == "tasks")
    assert tasks.row_count == 2
    assert any(col["name"] == "payload" for col in tasks.columns)
    assert tasks.sample_rows[0]["payload"]["type"] == "bytes"
    assert tasks.sample_rows[0]["title"]["type"] == "text"
    assert tasks.sample_rows[0]["title"]["redacted"] is True


def test_analyze_sqlite_database_handles_zero_byte_file(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    db_path.write_bytes(b"")

    inventory = analyze_sqlite_database(db_path)

    assert inventory.errors == ["zero-byte sqlite file"]
    assert inventory.tables == []


def test_analyze_sqlite_database_handles_non_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "neo.db"
    db_path.write_bytes(b"not-sqlite-data")

    inventory = analyze_sqlite_database(db_path)

    assert inventory.errors == ["not a sqlite database file"]
    assert inventory.tables == []


def test_discover_and_ingest_sqlite_inventory(tmp_path: Path) -> None:
    root = tmp_path / "roots"
    root.mkdir()
    db_path = root / "sample.sqlite3"
    _make_sample_db(db_path)
    zero_path = root / "empty.db"
    zero_path.write_bytes(b"")

    discovered = discover_sqlite_databases([root])
    assert discovered == sorted([db_path.resolve(), zero_path.resolve()])

    inventories = [analyze_sqlite_database(path, sample_rows=1) for path in discovered]

    evomap_path = tmp_path / "evomap_knowledge.db"
    kb = KnowledgeDB(str(evomap_path))
    kb.init_schema()

    stats = ingest_sqlite_inventory(kb, inventories)
    db_stats = kb.stats()

    assert stats.analyzed == 2
    assert stats.ingested_documents == 2
    assert stats.ingested_atoms >= 3
    assert db_stats["documents"] == 2
    assert db_stats["episodes"] >= 3
    assert db_stats["atoms"] >= 3
    atom = kb.search_fts("sqlite database inventory", limit=5)
    assert atom
    assert any("sample.sqlite3" in item.answer for item in atom)


def test_analyze_sqlite_database_redacts_sensitive_operational_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY,
            status TEXT,
            input_json TEXT,
            params_json TEXT,
            conversation_url TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO jobs (status, input_json, params_json, conversation_url) VALUES (?, ?, ?, ?)",
        (
            "completed",
            '{"prompt":"secret"}',
            '{"deep_research":true}',
            "https://chatgpt.com/c/example",
        ),
    )
    conn.commit()
    conn.close()

    inventory = analyze_sqlite_database(db_path, sample_rows=1)

    jobs = next(item for item in inventory.tables if item.name == "jobs")
    assert jobs.sample_rows[0]["status"] == "completed"
    assert jobs.sample_rows[0]["input_json"]["redacted"] is True
    assert jobs.sample_rows[0]["params_json"]["redacted"] is True
    assert jobs.sample_rows[0]["conversation_url"]["type"] == "url_like"
    assert jobs.sample_rows[0]["conversation_url"]["redacted"] is True


def test_filter_sqlite_databases_excludes_target_db_by_default(tmp_path: Path) -> None:
    root = tmp_path / "roots"
    root.mkdir()
    sample_db = root / "sample.sqlite3"
    target_db = root / "evomap_knowledge.db"
    _make_sample_db(sample_db)
    _make_sample_db(target_db)

    discovered = discover_sqlite_databases([root])
    filtered = filter_sqlite_databases(discovered, exclude_paths=[target_db])

    assert sample_db.resolve() in filtered
    assert target_db.resolve() not in filtered
