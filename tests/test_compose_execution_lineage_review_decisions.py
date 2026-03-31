from __future__ import annotations

import json
from pathlib import Path

from ops.compose_execution_lineage_review_decisions import compose, next_versioned_decision_name


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311")


def test_compose_execution_lineage_review_decisions_matches_fixture_outputs(tmp_path: Path) -> None:
    base = FIXTURE_DIR / "review_decisions_base_v1.tsv"
    delta = FIXTURE_DIR / "review_decisions_delta_v1.tsv"
    expected_merged = (FIXTURE_DIR / "review_decisions_merged_v1.tsv").read_text(encoding="utf-8")
    expected_summary = json.loads((FIXTURE_DIR / "review_decisions_merged_summary_v1.json").read_text(encoding="utf-8"))
    output = tmp_path / "execution_lineage_review_decisions_v3.tsv"

    summary = compose(base_path=base, delta_path=delta, output_path=output)

    assert next_versioned_decision_name(base) == "review_decisions_base_v2.tsv"
    assert output.read_text(encoding="utf-8") == expected_merged
    summary["output_path"] = "__OUTPUT__"
    assert summary == expected_summary
    actual_summary = json.loads(output.with_suffix(".summary.json").read_text(encoding="utf-8"))
    actual_summary["output_path"] = "__OUTPUT__"
    assert actual_summary == expected_summary
