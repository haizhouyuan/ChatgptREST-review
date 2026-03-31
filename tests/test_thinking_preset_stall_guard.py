"""Tests for the thinking-preset stall guard in min_chars completion guard."""
from __future__ import annotations

import json

from chatgptrest.core.db import connect
from chatgptrest.worker.worker import _min_chars_guard_should_complete_under_min_chars


def _insert_min_chars_downgrade(*, conn, job_id: str, ts: float, answer_chars: int) -> None:
    payload = {
        "reason": "answer_too_short_for_min_chars",
        "answer_chars": int(answer_chars),
        "min_chars_required": 2500,
    }
    conn.execute(
        "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
        (job_id, float(ts), "completion_guard_downgraded", json.dumps(payload, ensure_ascii=False)),
    )


def test_thinking_preset_waits_when_stalled_quickly(tmp_path) -> None:
    """Thinking preset should NOT declare stall after just 2 downgrades if age < 10 min."""
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="tp1", ts=10.0, answer_chars=321)
        _insert_min_chars_downgrade(conn=conn, job_id="tp1", ts=80.0, answer_chars=321)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="tp1",
            answer_chars=321,
            min_chars_required=2500,
            thinking_preset=True,
            now_ts=200.0,  # ~3 min since first downgrade — should still wait
        )
    assert should_complete is False
    assert details.get("decision_reason") == "waiting"


def test_thinking_preset_completes_when_stalled_long_enough(tmp_path) -> None:
    """Thinking preset should declare stall after 10 minutes of no progress."""
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="tp2", ts=10.0, answer_chars=321)
        _insert_min_chars_downgrade(conn=conn, job_id="tp2", ts=80.0, answer_chars=321)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="tp2",
            answer_chars=321,
            min_chars_required=2500,
            thinking_preset=True,
            now_ts=620.0,  # 10+ min since first downgrade — should stall
        )
    assert should_complete is True
    assert details.get("decision_reason") == "stalled"


def test_non_thinking_preset_stalls_immediately(tmp_path) -> None:
    """Regular (non-thinking) preset should stall after 2 downgrades regardless of age."""
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="reg1", ts=10.0, answer_chars=321)
        _insert_min_chars_downgrade(conn=conn, job_id="reg1", ts=80.0, answer_chars=321)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="reg1",
            answer_chars=321,
            min_chars_required=2500,
            thinking_preset=False,
            now_ts=90.0,  # Very short age — should still stall for regular presets
        )
    assert should_complete is True
    assert details.get("decision_reason") == "stalled"
