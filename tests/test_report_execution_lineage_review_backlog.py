from __future__ import annotations

import json
from pathlib import Path

from ops.report_execution_lineage_review_backlog import report_backlog


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311")


def test_report_execution_lineage_review_backlog_matches_scaffold_fixture() -> None:
    summary = report_backlog(input_tsv=FIXTURE_DIR / "review_decisions_scaffold_v1.tsv", top_n=5)
    summary["input_tsv"] = "__INPUT__"
    expected = json.loads((FIXTURE_DIR / "review_decisions_scaffold_backlog_summary_v1.json").read_text(encoding="utf-8"))
    assert summary == expected


def test_report_execution_lineage_review_backlog_matches_merged_fixture() -> None:
    summary = report_backlog(input_tsv=FIXTURE_DIR / "review_decisions_merged_v1.tsv", top_n=5)
    summary["input_tsv"] = "__INPUT__"
    expected = json.loads((FIXTURE_DIR / "review_decisions_merged_backlog_summary_v1.json").read_text(encoding="utf-8"))
    assert summary == expected
