from __future__ import annotations

from pathlib import Path

from ops.run_skill_market_candidate_lifecycle_validation import run_skill_market_candidate_lifecycle_validation


def test_run_skill_market_candidate_lifecycle_validation_roundtrip(tmp_path: Path) -> None:
    report = run_skill_market_candidate_lifecycle_validation(
        out_dir=tmp_path / "report",
        db_path=tmp_path / "skill_platform.db",
        evomap_db_path=tmp_path / "evomap.db",
    )

    assert report["checks"]["lifecycle_roundtrip_ok"] is True
    assert Path(report["report_json_path"]).exists()
    assert Path(report["report_md_path"]).exists()
    assert report["register"]["status"] == "quarantine"
    assert report["evaluate"]["status"] == "evaluated"
    assert report["promote"]["status"] == "promoted"
    assert report["deprecate"]["status"] == "deprecated"
