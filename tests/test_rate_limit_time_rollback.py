from __future__ import annotations

import time
from pathlib import Path

from chatgptrest.core.db import connect
from chatgptrest.core.rate_limit import try_reserve


def test_try_reserve_clamps_time_rollback(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    key = "chatgpt_web_send"
    interval = 61

    # Simulate system clock rollback: stored last_ts is in the future.
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO rate_limits(k, last_ts) VALUES(?, ?)",
            (key, time.time() + 3600),
        )
        conn.commit()

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        wait = try_reserve(conn, key=key, min_interval_seconds=interval)
        conn.commit()

    assert 60.0 <= float(wait) <= float(interval)
