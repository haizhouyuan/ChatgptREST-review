from __future__ import annotations

from pathlib import Path

from ops.build_execution_lineage_review_scaffold import build_scaffold


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311")


def test_build_execution_lineage_review_scaffold_matches_fixture_output(tmp_path: Path) -> None:
    input_json = FIXTURE_DIR / "review_decision_input_v1.json"
    expected_tsv = (FIXTURE_DIR / "review_decisions_scaffold_v1.tsv").read_text(encoding="utf-8")
    output_tsv = tmp_path / "review_decisions_scaffold.tsv"

    result = build_scaffold(input_json=input_json, output_tsv=output_tsv)

    assert result["ok"] is True
    assert result["selected_rows"] == 3
    assert result["suggested_review_ready"] == 1
    assert result["suggested_remediation_candidate"] == 1
    assert result["suggested_manual_review_required"] == 1
    assert output_tsv.read_text(encoding="utf-8") == expected_tsv
