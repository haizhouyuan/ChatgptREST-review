from __future__ import annotations

import time
from pathlib import Path

from chatgptrest.core import incidents
from chatgptrest.core.db import connect, init_db


def test_incidents_roundtrip_and_action_counters(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        inc = incidents.create_incident(
            conn,
            incident_id="inc-1",
            fingerprint="deadbeef0000",
            signature="error:TimeoutError:click timeout",
            category="job",
            severity="P1",
            now=time.time(),
            job_ids=["j1"],
            evidence_dir=str(tmp_path / "evidence"),
        )
        conn.commit()
    assert inc.incident_id == "inc-1"
    assert inc.fingerprint_hash == "deadbeef0000"
    assert inc.status == incidents.INCIDENT_STATUS_OPEN
    assert "j1" in inc.job_ids

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        inc2 = incidents.touch_incident(conn, incident_id="inc-1", now=time.time(), add_job_id="j2")
        action_id = incidents.create_action(
            conn,
            incident_id="inc-1",
            action_type="infra_heal_restart_driver",
            status=incidents.ACTION_STATUS_COMPLETED,
            risk_level="low",
            result={"ok": True},
        )
        conn.commit()
    assert inc2.count >= 1
    assert "j2" in inc2.job_ids
    assert action_id

    with connect(db_path) as conn:
        found = incidents.find_active_incident(conn, fingerprint="deadbeef0000", now=time.time(), dedupe_seconds=3600)
        assert found is not None
        assert found.incident_id == "inc-1"

        n = incidents.count_actions(conn, action_type="infra_heal_restart_driver", since_ts=time.time() - 3600)
        assert n >= 1
        last = incidents.last_action_ts(conn, action_type="infra_heal_restart_driver")
        assert last is not None


def test_daemon_state_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        incidents.save_daemon_state(conn, {"last_event_id": 123, "updated_at": 1.23})
        conn.commit()
    with connect(db_path) as conn:
        state = incidents.load_daemon_state(conn)
    assert state.get("last_event_id") == 123



def test_resolve_stale_incidents(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)

    old_ts = time.time() - 10_000
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        incidents.create_incident(
            conn,
            incident_id="inc-old",
            fingerprint="deadbeef0001",
            signature="error:RuntimeError:old",
            category="job",
            severity="P2",
            now=old_ts,
            job_ids=["j-old"],
        )
        incidents.create_incident(
            conn,
            incident_id="inc-new",
            fingerprint="deadbeef0002",
            signature="error:RuntimeError:new",
            category="job",
            severity="P2",
            now=time.time(),
            job_ids=["j-new"],
        )
        conn.commit()

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        resolved = incidents.resolve_stale_incidents(
            conn,
            stale_before_ts=(time.time() - 3600),
            now=time.time(),
            limit=10,
        )
        conn.commit()

    assert [r.incident_id for r in resolved] == ["inc-old"]
    assert resolved[0].status == incidents.INCIDENT_STATUS_RESOLVED

    with connect(db_path) as conn:
        found_old = incidents.find_active_incident(conn, fingerprint="deadbeef0001", now=time.time(), dedupe_seconds=365 * 86400)
        found_new = incidents.find_active_incident(conn, fingerprint="deadbeef0002", now=time.time(), dedupe_seconds=365 * 86400)

    assert found_old is None
    assert found_new is not None
    assert found_new.incident_id == "inc-new"


def test_resolve_duplicate_open_incidents(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)

    fingerprint = "deadbeef-dupe"
    old_ts = time.time() - 10_000
    new_ts = time.time()

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        incidents.create_incident(
            conn,
            incident_id="inc-old",
            fingerprint=fingerprint,
            signature="error:RuntimeError:old",
            category="job",
            severity="P2",
            now=old_ts,
            job_ids=["j-old"],
        )
        incidents.create_incident(
            conn,
            incident_id="inc-new",
            fingerprint=fingerprint,
            signature="error:RuntimeError:new",
            category="job",
            severity="P2",
            now=new_ts,
            job_ids=["j-new"],
        )
        conn.commit()

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        resolved = incidents.resolve_duplicate_open_incidents(conn, now=time.time(), limit=10)
        conn.commit()

    assert [r.incident_id for r in resolved] == ["inc-old"]

    with connect(db_path) as conn:
        found = incidents.find_active_incident(conn, fingerprint=fingerprint, now=time.time(), dedupe_seconds=365 * 86400)

    assert found is not None
    assert found.incident_id == "inc-new"
