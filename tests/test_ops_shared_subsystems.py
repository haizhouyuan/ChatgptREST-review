from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from chatgptrest.core.db import init_db
from chatgptrest.core.pause import get_pause_state
from chatgptrest.ops_shared.subsystem import TickContext
from chatgptrest.ops_shared.subsystems import BlockedStateSubsystem


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def test_blocked_state_subsystem_auto_pause_uses_pause_module(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)

    blocked_state_path = tmp_path / "chatgptmcp_state.json"
    blocked_state_path.write_text(
        json.dumps(
            {
                "blocked_until": time.time() + 300.0,
                "reason": "conversation_busy",
                "phase": "send",
                "url": "https://chatgpt.com/c/test",
            }
        ),
        encoding="utf-8",
    )

    subsystem = BlockedStateSubsystem(interval_seconds=1.0)
    with _connect(db_path) as conn:
        observations = subsystem.tick(
            TickContext(
                now=time.time(),
                args=None,
                conn=conn,
                state={
                    "chatgptmcp_state_path": blocked_state_path,
                    "legacy_blocked_path": None,
                    "enable_auto_pause": True,
                    "auto_pause_mode": "send",
                    "auto_pause_default_seconds": 300,
                    "log_path": tmp_path / "maint.jsonl",
                },
            )
        )
        pause = get_pause_state(conn)

    assert pause.is_active(now=time.time())
    assert pause.mode == "send"
    assert str(pause.reason or "").startswith("auto_blocked:")
    assert any(obs.data.get("type") == "auto_pause_set" for obs in observations)
    assert all(obs.data.get("type") != "auto_pause_error" for obs in observations)
