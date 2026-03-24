from __future__ import annotations

import json

from chatgptrest.core.db import connect
from chatgptrest.worker.worker import _min_chars_guard_should_complete_under_min_chars


def _insert_min_chars_downgrade(*, conn, job_id: str, ts: float, answer_chars: int) -> None:
    payload = {
        "reason": "answer_too_short_for_min_chars",
        "answer_chars": int(answer_chars),
        "min_chars_required": 4000,
    }
    conn.execute(
        "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
        (job_id, float(ts), "completion_guard_downgraded", json.dumps(payload, ensure_ascii=False)),
    )


def test_min_chars_guard_near_miss_completes(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j1",
            answer_chars=3947,
            min_chars_required=4000,
            now_ts=123.0,
        )
    assert should_complete is True
    assert details.get("decision_reason") == "near_miss"
    assert details.get("missing_chars") == 53


def test_min_chars_guard_waits_initially_when_far_short(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j2",
            answer_chars=1000,
            min_chars_required=4000,
            now_ts=123.0,
        )
    assert should_complete is False
    assert details.get("decision_reason") == "waiting"


def test_min_chars_guard_semantic_final_short_answer_completes(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j-semantic",
            answer_chars=190,
            min_chars_required=400,
            semantically_final=True,
            now_ts=123.0,
        )
    assert should_complete is True
    assert details.get("decision_reason") == "semantic_final_short_answer"


def test_min_chars_guard_completes_when_stalled(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="j3", ts=10.0, answer_chars=1000)
        _insert_min_chars_downgrade(conn=conn, job_id="j3", ts=20.0, answer_chars=1000)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j3",
            answer_chars=1000,
            min_chars_required=4000,
            now_ts=123.0,
        )
    assert should_complete is True
    assert details.get("decision_reason") == "stalled"
    assert details.get("previous_downgrades") == 2


def test_min_chars_guard_completes_when_cap_exceeded(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        for i in range(10):
            _insert_min_chars_downgrade(conn=conn, job_id="j4", ts=float(i), answer_chars=1000)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j4",
            answer_chars=1001,
            min_chars_required=4000,
            now_ts=123.0,
        )
    assert should_complete is True
    assert details.get("decision_reason") == "cap_exceeded"


def test_min_chars_guard_deep_research_waits_when_stalled_quickly(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="j5", ts=10.0, answer_chars=1000)
        _insert_min_chars_downgrade(conn=conn, job_id="j5", ts=20.0, answer_chars=1000)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j5",
            answer_chars=1000,
            min_chars_required=4000,
            deep_research=True,
            now_ts=123.0,
        )
    assert should_complete is False
    assert details.get("decision_reason") == "waiting"


def test_min_chars_guard_deep_research_can_complete_when_stalled_long_enough(tmp_path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    with connect(db_path) as conn:
        _insert_min_chars_downgrade(conn=conn, job_id="j6", ts=10.0, answer_chars=1000)
        _insert_min_chars_downgrade(conn=conn, job_id="j6", ts=20.0, answer_chars=1000)
        conn.commit()
        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
            conn=conn,
            job_id="j6",
            answer_chars=1000,
            min_chars_required=4000,
            deep_research=True,
            now_ts=1211.0,
        )
    assert should_complete is True
    assert details.get("decision_reason") == "stalled"
