from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.build_planning_review_maintenance_fixture_bundle import build_fixture_bundle


def test_build_fixture_bundle_writes_expected_files(tmp_path: Path) -> None:
    out = tmp_path / "fixtures"
    result = build_fixture_bundle(output_dir=out)

    assert result["ok"] is True
    assert result["fixture_count"] == 4
    assert (out / "fixture_summary.json").exists()
    assert (out / "fixture_cases.tsv").exists()
    assert (out / "README.md").exists()

    summary = json.loads((out / "fixture_summary.json").read_text(encoding="utf-8"))
    assert summary["fixture_count"] == 4
    with (out / "fixture_cases.tsv").open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert len(rows) == 4
    assert {row["scenario"] for row in rows} == {
        "allowlist_missing_live_atom",
        "stale_bootstrap_outside_allowlist",
        "latest_output_backlog_hotspot",
        "archive_only_should_not_enter_candidate_pool",
    }
