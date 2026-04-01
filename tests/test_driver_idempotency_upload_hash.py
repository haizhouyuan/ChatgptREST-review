from __future__ import annotations

import asyncio
import os
from pathlib import Path

from chatgpt_web_mcp import _tools_impl as driver

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
