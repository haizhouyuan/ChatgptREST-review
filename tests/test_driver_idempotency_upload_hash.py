from __future__ import annotations

import asyncio
import os
from pathlib import Path

from chatgpt_web_mcp import _tools_impl as driver


def _read_runtime_instance_id(db_path: Path, ctx: object) -> str | None:
    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        row = conn.execute(
            "SELECT runtime_instance_id FROM idempotency WHERE namespace = ? AND tool = ? AND idempotency_key = ?",
            (ctx.namespace, ctx.tool, ctx.key),
        ).fetchone()
    return str(row[0]) if row and row[0] is not None else None

def test_file_fingerprint_for_idempotency_is_stable_across_paths_and_mtime(tmp_path: Path) -> None:
    p1 = tmp_path / "a.txt"
    p1.write_text("hello", encoding="utf-8")

    p2_dir = tmp_path / "sub"
    p2_dir.mkdir()
    p2 = p2_dir / "a.txt"
    p2.write_text("hello", encoding="utf-8")

    os.utime(p1, (1, 1))
    os.utime(p2, (2, 2))

    fp1 = driver._file_fingerprint_for_idempotency(driver._file_fingerprint(p1))
    fp2 = driver._file_fingerprint_for_idempotency(driver._file_fingerprint(p2))

    assert fp1 == fp2
    assert "path" not in fp1
    assert "mtime" not in fp1

    h1 = driver._hash_request({"tool": "chatgpt_web_ask", "file_fingerprints": [fp1]})
    h2 = driver._hash_request({"tool": "chatgpt_web_ask", "file_fingerprints": [fp2]})
    assert h1 == h2


def test_idempotency_begin_sent_hash_mismatch_does_not_wedge(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))

    ctx1 = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx1))
    assert should1 is True
    assert existing1 is None

    asyncio.run(driver._idempotency_update(ctx1, sent=True, status="in_progress"))

    ctx2 = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="k", request_hash="h2")
    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx2))
    assert should2 is False
    assert isinstance(existing2, dict)
    assert existing2.get("request_hash_mismatch") is True
    assert existing2.get("requested_request_hash") == "h2"


def test_idempotency_begin_recovers_blank_unsent_in_progress_after_short_threshold_when_runtime_changed(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.setenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", "30")

    ctx = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="chatgptrest:k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx))
    assert should1 is True
    assert existing1 is None

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            UPDATE idempotency
            SET status = ?, sent = 0, conversation_url = NULL, result_json = NULL, error = NULL,
                updated_at = ?, runtime_instance_id = ?
            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
            """,
            ("in_progress", 1.0, "previous-runtime", ctx.namespace, ctx.tool, ctx.key),
        )
        conn.commit()

    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx))
    assert should2 is True
    assert isinstance(existing2, dict)
    assert existing2.get("empty_in_progress_reset") is True
    assert existing2.get("previous_runtime_instance_id") == "previous-runtime"
    assert float(existing2.get("empty_in_progress_threshold_seconds") or 0) == 30.0


def test_idempotency_begin_does_not_reset_blank_unsent_in_progress_for_same_runtime(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.setenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", "30")

    ctx = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="chatgptrest:k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx))
    assert should1 is True
    assert existing1 is None

    runtime_instance_id = _read_runtime_instance_id(db_path, ctx)
    assert runtime_instance_id

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            UPDATE idempotency
            SET status = ?, sent = 0, conversation_url = NULL, result_json = NULL, error = NULL,
                updated_at = ?, runtime_instance_id = ?
            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
            """,
            ("in_progress", 1.0, runtime_instance_id, ctx.namespace, ctx.tool, ctx.key),
        )
        conn.commit()

    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx))
    assert should2 is False
    assert isinstance(existing2, dict)
    assert existing2.get("empty_in_progress_reset") is not True
    assert existing2.get("runtime_instance_id") == runtime_instance_id


def test_idempotency_begin_recovers_blank_unsent_in_progress_for_same_runtime_gemini_chatgptrest_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.setenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", "30")

    ctx = driver._IdempotencyContext(namespace="ns", tool="gemini_web_ask_pro", key="chatgptrest:k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx))
    assert should1 is True
    assert existing1 is None

    runtime_instance_id = _read_runtime_instance_id(db_path, ctx)
    assert runtime_instance_id

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            UPDATE idempotency
            SET status = ?, sent = 0, conversation_url = NULL, result_json = NULL, error = NULL,
                updated_at = ?, runtime_instance_id = ?
            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
            """,
            ("in_progress", 1.0, runtime_instance_id, ctx.namespace, ctx.tool, ctx.key),
        )
        conn.commit()

    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx))
    assert should2 is True
    assert isinstance(existing2, dict)
    assert existing2.get("empty_in_progress_reset") is True
    assert existing2.get("empty_in_progress_same_runtime_reset") is True
    assert existing2.get("runtime_instance_id") == runtime_instance_id


def test_idempotency_begin_uses_shorter_default_reclaim_window_for_same_runtime_gemini_chatgptrest_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.delenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", raising=False)

    ctx = driver._IdempotencyContext(namespace="ns", tool="gemini_web_ask_pro", key="chatgptrest:k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx))
    assert should1 is True
    assert existing1 is None

    runtime_instance_id = _read_runtime_instance_id(db_path, ctx)
    assert runtime_instance_id

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            UPDATE idempotency
            SET status = ?, sent = 0, conversation_url = NULL, result_json = NULL, error = NULL,
                updated_at = ?, runtime_instance_id = ?
            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
            """,
            ("in_progress", 31.0, runtime_instance_id, ctx.namespace, ctx.tool, ctx.key),
        )
        conn.commit()

    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx))
    assert should2 is True
    assert isinstance(existing2, dict)
    assert existing2.get("empty_in_progress_reset") is True
    assert existing2.get("empty_in_progress_same_runtime_reset") is True
    assert float(existing2.get("empty_in_progress_threshold_seconds") or 0) == 30.0


def test_idempotency_begin_does_not_reset_blank_unsent_in_progress_for_non_chatgptrest_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.setenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", "30")

    ctx = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="plain:k", request_hash="h1")
    should1, existing1 = asyncio.run(driver._idempotency_begin(ctx))
    assert should1 is True
    assert existing1 is None

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            UPDATE idempotency
            SET status = ?, sent = 0, conversation_url = NULL, result_json = NULL, error = NULL,
                updated_at = ?, runtime_instance_id = ?
            WHERE namespace = ? AND tool = ? AND idempotency_key = ?
            """,
            ("in_progress", 1.0, "previous-runtime", ctx.namespace, ctx.tool, ctx.key),
        )
        conn.commit()

    should2, existing2 = asyncio.run(driver._idempotency_begin(ctx))
    assert should2 is False
    assert isinstance(existing2, dict)
    assert existing2.get("empty_in_progress_reset") is not True


def test_idempotency_begin_migrates_legacy_db_without_runtime_instance_id(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "idem.sqlite3"
    lock_path = tmp_path / "idem.lock"

    monkeypatch.setenv("MCP_IDEMPOTENCY_DB", str(db_path))
    monkeypatch.setenv("MCP_IDEMPOTENCY_LOCK_FILE", str(lock_path))
    monkeypatch.setenv("CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS", "30")

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.execute(
            """
            CREATE TABLE idempotency (
              namespace TEXT NOT NULL,
              tool TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              request_hash TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              sent INTEGER NOT NULL DEFAULT 0,
              conversation_url TEXT,
              result_json TEXT,
              error TEXT,
              PRIMARY KEY (namespace, tool, idempotency_key)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO idempotency(namespace, tool, idempotency_key, request_hash, status, created_at, updated_at, sent, conversation_url, result_json, error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("ns", "chatgpt_web_ask", "chatgptrest:k", "h1", "in_progress", 1.0, 1.0, 0, None, None, None),
        )
        conn.commit()

    ctx = driver._IdempotencyContext(namespace="ns", tool="chatgpt_web_ask", key="chatgptrest:k", request_hash="h1")
    should_execute, existing = asyncio.run(driver._idempotency_begin(ctx))

    assert should_execute is True
    assert isinstance(existing, dict)
    assert existing.get("empty_in_progress_reset") is True

    with driver.sqlite3.connect(str(db_path), timeout=30.0) as conn:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(idempotency)")}
        assert "runtime_instance_id" in columns
        row = conn.execute(
            "SELECT runtime_instance_id FROM idempotency WHERE namespace = ? AND tool = ? AND idempotency_key = ?",
            (ctx.namespace, ctx.tool, ctx.key),
        ).fetchone()

    assert row is not None and row[0]


def test_chatgpt_web_ask_request_hash_uses_stable_file_fingerprints(tmp_path: Path, monkeypatch) -> None:
    upload = tmp_path / "upload.txt"
    upload.write_text("hello", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_hash(payload: dict[str, object]) -> str:
        captured["payload"] = payload
        return "h"

    async def _fake_begin(_ctx):  # type: ignore[no-untyped-def]
        return False, {"sent": False, "result": {"status": "completed", "answer": "ok"}}

    monkeypatch.setattr(driver, "_hash_request", _fake_hash)
    monkeypatch.setattr(driver, "_idempotency_begin", _fake_begin)

    res = asyncio.run(
        driver.ask(
            question="q",
            idempotency_key="k",
            file_paths=[str(upload)],
        )
    )
    assert res.get("replayed") is True

    payload = captured.get("payload")
    assert isinstance(payload, dict)
    fps = payload.get("file_fingerprints")
    assert isinstance(fps, list) and len(fps) == 1
    fp = fps[0]
    assert isinstance(fp, dict)
    assert "name" in fp
    assert "size_bytes" in fp
    assert "sha256" in fp
    assert "path" not in fp
    assert "mtime" not in fp
