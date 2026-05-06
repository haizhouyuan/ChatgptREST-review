from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ops import build_evomap_launch_summary as module


def _create_test_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE documents (
              doc_id TEXT PRIMARY KEY,
              source TEXT NOT NULL
            );
            CREATE TABLE episodes (
              episode_id TEXT PRIMARY KEY,
              doc_id TEXT NOT NULL
            );
            CREATE TABLE atoms (
              atom_id TEXT PRIMARY KEY,
              episode_id TEXT NOT NULL,
              canonical_question TEXT,
              promotion_status TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO documents (doc_id, source) VALUES (?, ?)",
            [
                ("doc-planning", "planning"),
                ("doc-chatgptrest", "chatgptrest"),
            ],
        )
        conn.executemany(
            "INSERT INTO episodes (episode_id, doc_id) VALUES (?, ?)",
            [
                ("ep-planning", "doc-planning"),
                ("ep-chatgptrest", "doc-chatgptrest"),
            ],
        )
        conn.executemany(
            "INSERT INTO atoms (atom_id, episode_id, canonical_question, promotion_status) VALUES (?, ?, ?, ?)",
            [
                ("at-planning-active", "ep-planning", "planning: reviewed slice", "active"),
                ("at-planning-candidate", "ep-planning", "planning: candidate slice", "candidate"),
                ("at-activity", "ep-chatgptrest", "activity: team.run.completed", "staged"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_collect_canonical_db_stats_counts_expected_groups(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _create_test_db(db_path)

    stats = module.collect_canonical_db_stats(db_path)

    assert stats["docs_total"] == 2
    assert stats["atoms_total"] == 3
    assert stats["docs_by_source"][0] == {"source": "planning", "count": 1}
    assert {"promotion_status": "active", "count": 1} in stats["planning_by_promotion"]
    assert stats["activity_by_promotion"] == [{"promotion_status": "staged", "count": 1}]


def test_build_summary_writes_json_and_markdown(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _create_test_db(db_path)

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "release_bundle_manifest.json").write_text(
        json.dumps(
            {
                "ready_for_explicit_consumption": True,
                "pack_dir": str(tmp_path / "pack"),
                "checks": {"validation_green": True},
                "scope": {"reviewed_atoms": 2},
                "validation_summary": {"query_count": 4, "pass_count": 4},
                "sensitivity_summary": {"unresolved_flagged_atoms": 0},
                "observability_summary": {"sample_count": 5},
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "rollback_runbook.md").write_text("# rollback\n", encoding="utf-8")
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle_dir))

    smoke_dir = tmp_path / "smoke" / "20260311T000000Z"
    smoke_dir.mkdir(parents=True)
    (smoke_dir / "launch_smoke.json").write_text(json.dumps({"ok": True, "kind": "launch_smoke"}), encoding="utf-8")

    monkeypatch.setattr(
        module,
        "collect_runtime_health",
        lambda base_url: {
            "ok": True,
            "base_url": base_url,
            "cognitive": {"runtime_ready": True},
            "advisor": {"subsystems": {"auth": {"mode": "strict"}}},
        },
    )
    monkeypatch.setattr(
        module,
        "collect_issue_domain_status",
        lambda base_url: {
            "ok": True,
            "read_plane": "canonical",
            "canonical_issue_count": 246,
            "coverage_gap_count": 0,
        },
    )

    output_dir = tmp_path / "summary"
    result = module.build_summary(
        base_url="http://127.0.0.1:18711",
        db_path=db_path,
        smoke_root=tmp_path / "smoke",
        output_dir=output_dir,
    )

    assert result["ok"] is True
    summary = json.loads((output_dir / "launch_summary.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "launch_summary.md").read_text(encoding="utf-8")

    assert summary["planning_runtime_pack"]["ready"] is True
    assert summary["latest_smoke"]["ok"] is True
    assert summary["launch_flags"]["planning_review_opt_in_available"] is True
    assert "planning_pack_ready: `True`" in markdown
    assert "rollback_runbook" in markdown
