from __future__ import annotations

from pathlib import Path

from chatgptrest.dashboard.control_plane import DashboardControlPlane, DashboardControlPlaneConfig


def _config(tmp_path: Path) -> DashboardControlPlaneConfig:
    return DashboardControlPlaneConfig(
        job_db_path=tmp_path / "jobdb.sqlite3",
        artifacts_dir=tmp_path / "artifacts",
        read_db_path=tmp_path / "dashboard_control_plane.sqlite3",
        controller_lane_db_path=tmp_path / "controller_lane.sqlite3",
        openmind_kb_search_db_path=tmp_path / "kb_search.db",
        openmind_kb_registry_db_path=tmp_path / "kb_registry.db",
        openmind_memory_db_path=tmp_path / "memory.db",
        openmind_events_db_path=tmp_path / "events.db",
        evomap_knowledge_db_path=tmp_path / "evomap_knowledge.db",
        evomap_signals_db_path=tmp_path / "evomap_signals.db",
        refresh_interval_seconds=30,
        bootstrap_on_read=False,
    )


def test_connect_read_db_does_not_reinitialize_schema_on_every_read(tmp_path: Path, monkeypatch) -> None:
    plane = DashboardControlPlane(_config(tmp_path))
    calls = {"count": 0}

    def _unexpected_reinit() -> None:
        calls["count"] += 1
        raise AssertionError("connect_read_db should not reinitialize the read db")

    monkeypatch.setattr(plane, "_init_read_db", _unexpected_reinit)

    with plane.connect_read_db() as conn:
        row = conn.execute("SELECT v FROM meta WHERE k = ?", ("schema_version",)).fetchone()

    assert row is not None
    assert int(row["v"]) > 0
    assert calls["count"] == 0


def test_init_read_db_skips_write_bootstrap_for_existing_db(tmp_path: Path, monkeypatch) -> None:
    cfg = _config(tmp_path)
    existing = DashboardControlPlane(cfg)
    existing.get_meta()

    original_connect = existing.__class__.__mro__[1] if False else None
    calls = {"count": 0}
    import sqlite3 as _sqlite3
    real_connect = _sqlite3.connect

    def _counting_connect(*args, **kwargs):
        calls["count"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr("chatgptrest.dashboard.control_plane.sqlite3.connect", _counting_connect)
    plane = DashboardControlPlane(cfg)
    meta = plane.get_meta()

    assert int(meta["schema_version"]) > 0
    assert calls["count"] == 1
