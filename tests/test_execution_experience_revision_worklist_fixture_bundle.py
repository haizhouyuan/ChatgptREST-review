from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_revision_worklist import build_worklist


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_summary(summary: dict) -> dict:
    normalized = json.loads(json.dumps(summary, ensure_ascii=False))
    for key in ("candidates_path", "decisions_path", "output_tsv", "summary_path"):
        if normalized.get(key):
            normalized[key] = Path(str(normalized[key])).name
    return normalized


def test_execution_experience_revision_worklist_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates_v1.json"
    decisions_path = tmp_path / "execution_experience_review_decisions_v1.tsv"
    output_tsv = tmp_path / "revision_worklist_v1.tsv"

    candidates_path.write_text((FIXTURE_DIR / "experience_candidates_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    decisions_path.write_text(
        (FIXTURE_DIR / "execution_experience_review_decisions_v1.tsv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = build_worklist(
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        output_tsv=output_tsv,
    )

    assert output_tsv.read_text(encoding="utf-8") == (FIXTURE_DIR / "revision_worklist_v1.tsv").read_text(encoding="utf-8")
    assert _normalize_summary(summary) == _load_json(FIXTURE_DIR / "revision_worklist_v1_summary.json")
