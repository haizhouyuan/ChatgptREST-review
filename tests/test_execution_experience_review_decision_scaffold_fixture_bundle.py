from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_review_decision_scaffold import build_scaffold


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_summary(summary: dict) -> dict:
    normalized = json.loads(json.dumps(summary, ensure_ascii=False))
    for key in ("candidates_path", "decisions_path", "reviewer_manifest_path", "output_tsv", "summary_path"):
        if normalized.get(key):
            normalized[key] = Path(str(normalized[key])).name
    return normalized


def _assert_scaffold_matches_fixture(
    *,
    tmp_path: Path,
    output_name: str,
    expected_tsv_name: str,
    expected_summary_name: str,
    decisions_name: str | None = None,
) -> None:
    candidates_path = tmp_path / "experience_candidates_v1.json"
    reviewer_manifest_path = tmp_path / "reviewer_manifest_v1.json"
    output_tsv = tmp_path / output_name
    decisions_path = tmp_path / decisions_name if decisions_name else None

    candidates_path.write_text((FIXTURE_DIR / "experience_candidates_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    reviewer_manifest_path.write_text((FIXTURE_DIR / "reviewer_manifest_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    if decisions_path is not None:
        decisions_path.write_text((FIXTURE_DIR / decisions_name).read_text(encoding="utf-8"), encoding="utf-8")

    summary = build_scaffold(
        candidates_path=candidates_path,
        output_tsv=output_tsv,
        decisions_path=decisions_path,
        reviewer_manifest_path=reviewer_manifest_path,
    )

    assert output_tsv.read_text(encoding="utf-8") == (FIXTURE_DIR / expected_tsv_name).read_text(encoding="utf-8")
    assert _normalize_summary(summary) == _load_json(FIXTURE_DIR / expected_summary_name)


def test_execution_experience_review_decision_scaffold_fixture_bundle_review_pending(tmp_path: Path) -> None:
    _assert_scaffold_matches_fixture(
        tmp_path=tmp_path,
        output_name="review_decision_scaffold_review_pending_v1.tsv",
        expected_tsv_name="review_decision_scaffold_review_pending_v1.tsv",
        expected_summary_name="review_decision_scaffold_review_pending_v1_summary.json",
    )


def test_execution_experience_review_decision_scaffold_fixture_bundle_under_reviewed(tmp_path: Path) -> None:
    _assert_scaffold_matches_fixture(
        tmp_path=tmp_path,
        output_name="review_decision_scaffold_under_reviewed_v1.tsv",
        expected_tsv_name="review_decision_scaffold_under_reviewed_v1.tsv",
        expected_summary_name="review_decision_scaffold_under_reviewed_v1_summary.json",
        decisions_name="execution_experience_review_decisions_partial_v1.tsv",
    )


def test_execution_experience_review_decision_scaffold_fixture_bundle_decision_ready(tmp_path: Path) -> None:
    _assert_scaffold_matches_fixture(
        tmp_path=tmp_path,
        output_name="review_decision_scaffold_decision_ready_v1.tsv",
        expected_tsv_name="review_decision_scaffold_decision_ready_v1.tsv",
        expected_summary_name="review_decision_scaffold_decision_ready_v1_summary.json",
        decisions_name="execution_experience_review_decisions_complete_v1.tsv",
    )
