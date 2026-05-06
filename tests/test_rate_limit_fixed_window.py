from __future__ import annotations

from pathlib import Path

from chatgptrest.core.db import connect
from chatgptrest.core.rate_limit import try_reserve_fixed_window


def test_try_reserve_fixed_window_enforces_max_per_window(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    key = "k"

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        assert try_reserve_fixed_window(conn, key=key, window_seconds=10, max_per_window=2, now=100.0) == 0.0
        assert try_reserve_fixed_window(conn, key=key, window_seconds=10, max_per_window=2, now=101.0) == 0.0
        wait = try_reserve_fixed_window(conn, key=key, window_seconds=10, max_per_window=2, now=102.0)
        conn.commit()

    assert 7.9 <= float(wait) <= 8.1

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        assert try_reserve_fixed_window(conn, key=key, window_seconds=10, max_per_window=2, now=111.0) == 0.0
        conn.commit()

