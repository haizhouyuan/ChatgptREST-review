from __future__ import annotations

import json
import sqlite3

from ops.run_evomap_archive_envelope_live_smoke import build_payload, matching_archive_atoms


def test_build_payload_uses_archive_envelope_shape() -> None:
    payload = build_payload(
        trace_id="trace-1",
        session_id="session-1",
        task_ref="archive-envelope/live-smoke",
        commit_sha="abc123def4567890",
    )
    assert payload["trace_id"] == "trace-1"
    assert payload["session_key"] == "session-1"
    assert len(payload["events"]) == 2
    closeout, commit = payload["events"]
    assert closeout["type"] == "agent.task.closeout"
    assert closeout["data"]["schema_version"] == "openmind-v3-agent-ops-v1"
    assert closeout["data"]["closeout"]["status"] == "completed"
    assert commit["type"] == "agent.git.commit"
    assert commit["data"]["commit"]["commit"] == "abc123def4567890"


def test_matching_archive_atoms_counts_closeout_and_commit(tmp_path) -> None:
    db_path = tmp_path / "evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE atoms (atom_id TEXT PRIMARY KEY, canonical_question TEXT)")
        conn.execute(
            "INSERT INTO atoms(atom_id, canonical_question) VALUES (?, ?)",
            ("at-closeout", "task result: archive-envelope/live-smoke by codex"),
        )
        conn.execute(
            "INSERT INTO atoms(atom_id, canonical_question) VALUES (?, ?)",
            ("at-commit", "commit abc123de in ChatgptREST"),
        )
        conn.commit()
    finally:
        conn.close()

    counts = matching_archive_atoms(
        str(db_path),
        task_ref="archive-envelope/live-smoke",
        commit_sha="abc123def4567890",
    )
    assert counts == {
        "closeout_count": 1,
        "commit_count": 1,
    }
