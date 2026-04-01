from __future__ import annotations

import json
import sqlite3

from ops.run_openclaw_telemetry_plugin_live_smoke import (
    evaluate_coverage,
    expected_task_ref,
    extract_session_candidates,
    latest_matching_run_start_rowid,
    matching_openclaw_activity_atoms,
    task_ref_candidates,
)


def test_expected_task_ref_hashes_session_id() -> None:
    task_ref = expected_task_ref(session_id="sess-123", agent_id="main", prefix="openclaw")

    assert task_ref == "openclaw:main:ef5006fefdd6724eeee655ad782834f6748f8321"


def test_matching_openclaw_activity_atoms_filters_for_task_ref(tmp_path) -> None:
    db_path = tmp_path / "evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE atoms (atom_id TEXT PRIMARY KEY, episode_id TEXT, canonical_question TEXT)")
        conn.execute("CREATE TABLE episodes (episode_id TEXT PRIMARY KEY, source_ext TEXT)")
        rows = [
            ("at-1", "ep-1", "activity: team.run.created", {"task_ref": "openclaw:main:abc", "event_id": "evt-1"}),
            ("at-2", "ep-2", "activity: workflow.completed", {"task_ref": "openclaw:main:abc", "event_id": "evt-2"}),
            ("at-3", "ep-3", "activity: team.run.created", {"task_ref": "openclaw:main:other", "event_id": "evt-3"}),
        ]
        for atom_id, episode_id, canonical_question, source_ext in rows:
            conn.execute(
                "INSERT INTO atoms(atom_id, episode_id, canonical_question) VALUES (?, ?, ?)",
                (atom_id, episode_id, canonical_question),
            )
            conn.execute(
                "INSERT INTO episodes(episode_id, source_ext) VALUES (?, ?)",
                (episode_id, json.dumps(source_ext)),
            )
        conn.commit()
    finally:
        conn.close()

    matches = matching_openclaw_activity_atoms(str(db_path), task_refs=["openclaw:main:abc"], session_ids=[])
    assert matches == [
        {
            "rowid": "1",
            "atom_id": "at-1",
            "canonical_question": "activity: team.run.created",
            "task_ref": "openclaw:main:abc",
            "event_id": "evt-1",
            "session_id": "",
        },
        {
            "rowid": "2",
            "atom_id": "at-2",
            "canonical_question": "activity: workflow.completed",
            "task_ref": "openclaw:main:abc",
            "event_id": "evt-2",
            "session_id": "",
        },
    ]


def test_matching_openclaw_activity_atoms_filters_for_session_id(tmp_path) -> None:
    db_path = tmp_path / "evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE atoms (atom_id TEXT PRIMARY KEY, episode_id TEXT, canonical_question TEXT)")
        conn.execute("CREATE TABLE episodes (episode_id TEXT PRIMARY KEY, source_ext TEXT)")
        rows = [
            (
                "at-1",
                "ep-1",
                "activity: team.run.created",
                {"task_ref": "openclaw:main:unexpected", "event_id": "evt-1", "session_id": "sess-live"},
            ),
            (
                "at-2",
                "ep-2",
                "activity: workflow.failed",
                {"task_ref": "openclaw:main:unexpected", "event_id": "evt-2", "session_id": "sess-live"},
            ),
            (
                "at-3",
                "ep-3",
                "activity: team.run.created",
                {"task_ref": "openclaw:main:other", "event_id": "evt-3", "session_id": "other"},
            ),
        ]
        for atom_id, episode_id, canonical_question, source_ext in rows:
            conn.execute(
                "INSERT INTO atoms(atom_id, episode_id, canonical_question) VALUES (?, ?, ?)",
                (atom_id, episode_id, canonical_question),
            )
            conn.execute(
                "INSERT INTO episodes(episode_id, source_ext) VALUES (?, ?)",
                (episode_id, json.dumps(source_ext)),
            )
        conn.commit()
    finally:
        conn.close()

    matches = matching_openclaw_activity_atoms(str(db_path), task_refs=[], session_ids=["sess-live"])
    assert matches == [
        {
            "rowid": "1",
            "atom_id": "at-1",
            "canonical_question": "activity: team.run.created",
            "task_ref": "openclaw:main:unexpected",
            "event_id": "evt-1",
            "session_id": "sess-live",
        },
        {
            "rowid": "2",
            "atom_id": "at-2",
            "canonical_question": "activity: workflow.failed",
            "task_ref": "openclaw:main:unexpected",
            "event_id": "evt-2",
            "session_id": "sess-live",
        },
    ]


def test_extract_session_candidates_uses_runtime_meta() -> None:
    payload = {
        "result": {
            "meta": {
                "agentMeta": {"sessionId": "agent-meta-session"},
                "systemPromptReport": {
                    "sessionId": "prompt-session",
                    "sessionKey": "agent:main:main",
                },
            }
        }
    }
    candidates = extract_session_candidates(json.dumps(payload), requested_session_id="cli-session")
    assert candidates == ["cli-session", "agent-meta-session", "prompt-session", "agent:main:main"]


def test_task_ref_candidates_deduplicate() -> None:
    refs = task_ref_candidates(
        session_ids=["sess-a", "sess-a", "  ", "sess-b"],
        agent_id="main",
        prefix="openclaw",
    )
    assert refs == [
        expected_task_ref(session_id="sess-a"),
        expected_task_ref(session_id="sess-b"),
    ]


def test_latest_matching_run_start_rowid_returns_recent_created(tmp_path) -> None:
    db_path = tmp_path / "evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE atoms (atom_id TEXT PRIMARY KEY, episode_id TEXT, canonical_question TEXT)")
        conn.execute("CREATE TABLE episodes (episode_id TEXT PRIMARY KEY, source_ext TEXT)")
        rows = [
            ("at-1", "ep-1", "activity: team.run.created", {"task_ref": "openclaw:main:abc", "session_id": "sess-live"}),
            ("at-2", "ep-2", "activity: workflow.completed", {"task_ref": "openclaw:main:abc", "session_id": "sess-live"}),
            ("at-3", "ep-3", "activity: team.run.created", {"task_ref": "openclaw:main:abc", "session_id": "sess-live"}),
        ]
        for atom_id, episode_id, canonical_question, source_ext in rows:
            conn.execute(
                "INSERT INTO atoms(atom_id, episode_id, canonical_question) VALUES (?, ?, ?)",
                (atom_id, episode_id, canonical_question),
            )
            conn.execute(
                "INSERT INTO episodes(episode_id, source_ext) VALUES (?, ?)",
                (episode_id, json.dumps(source_ext)),
            )
        conn.commit()
    finally:
        conn.close()

    rowid = latest_matching_run_start_rowid(
        str(db_path),
        task_refs=["openclaw:main:abc"],
        session_ids=["sess-live"],
        max_rowid=3,
    )
    assert rowid == 3


def test_evaluate_coverage_accepts_recent_created_history_for_reused_session(tmp_path) -> None:
    db_path = tmp_path / "evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE atoms (atom_id TEXT PRIMARY KEY, episode_id TEXT, canonical_question TEXT)")
        conn.execute("CREATE TABLE episodes (episode_id TEXT PRIMARY KEY, source_ext TEXT)")
        rows = [
            ("at-1", "ep-1", "activity: team.run.created", {"task_ref": "openclaw:main:abc", "session_id": "sess-live"}),
            ("at-2", "ep-2", "activity: workflow.completed", {"task_ref": "openclaw:main:abc", "session_id": "sess-live"}),
        ]
        for atom_id, episode_id, canonical_question, source_ext in rows:
            conn.execute(
                "INSERT INTO atoms(atom_id, episode_id, canonical_question) VALUES (?, ?, ?)",
                (atom_id, episode_id, canonical_question),
            )
            conn.execute(
                "INSERT INTO episodes(episode_id, source_ext) VALUES (?, ?)",
                (episode_id, json.dumps(source_ext)),
            )
        conn.commit()
    finally:
        conn.close()

    coverage = evaluate_coverage(
        db_path=str(db_path),
        after=[
            {
                "rowid": "2",
                "atom_id": "at-2",
                "canonical_question": "activity: workflow.completed",
                "task_ref": "openclaw:main:abc",
                "event_id": "evt-2",
                "session_id": "sess-live",
            }
        ],
        task_refs=["openclaw:main:abc"],
        session_ids=["sess-live"],
        before_rowid=2,
        created_lookback_rows=5,
    )

    assert coverage["coverage_ok"] is True
    assert coverage["fresh_created_seen"] is False
    assert coverage["created_reused_from_recent_history"] is True
