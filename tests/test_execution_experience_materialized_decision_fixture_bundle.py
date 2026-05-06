from __future__ import annotations

import json
from pathlib import Path

from ops.merge_execution_experience_review_outputs import materialize_reviewed_candidates


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311")


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_summary(summary: dict) -> dict:
    normalized = json.loads(json.dumps(summary, ensure_ascii=False))
    if normalized.get("output_dir"):
        normalized["output_dir"] = Path(str(normalized["output_dir"])).name
    if normalized.get("summary_path"):
        normalized["summary_path"] = Path(str(normalized["summary_path"])).name
    if normalized.get("files"):
        normalized["files"] = [
            str(Path(str(item)).relative_to(Path(summary["output_dir"]))) for item in summary.get("files", [])
        ]
    if normalized.get("decision_files"):
        normalized["decision_files"] = {
            decision: {
                "json_path": str(Path(str(paths["json_path"])).relative_to(Path(summary["output_dir"]))),
                "tsv_path": str(Path(str(paths["tsv_path"])).relative_to(Path(summary["output_dir"]))),
            }
            for decision, paths in summary.get("decision_files", {}).items()
        }
    return normalized


def test_execution_experience_materialized_decision_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates_v1.json"
    decisions_path = tmp_path / "execution_experience_review_decisions_v1.tsv"
    output_dir = tmp_path / "reviewed"
    candidates_path.write_text((FIXTURE_DIR / "experience_candidates_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    decisions_path.write_text(
        (FIXTURE_DIR / "execution_experience_review_decisions_v1.tsv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = materialize_reviewed_candidates(
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        output_dir=output_dir,
    )

    assert _normalize_summary(summary) == _load_json(FIXTURE_DIR / "summary_v1.json")
    assert _load_json(output_dir / "reviewed_experience_candidates.json") == _load_json(
        FIXTURE_DIR / "reviewed_experience_candidates_v1.json"
    )
    assert (output_dir / "reviewed_experience_candidates.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "reviewed_experience_candidates_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "accepted_review_candidates.json") == _load_json(
        FIXTURE_DIR / "accepted_review_candidates_v1.json"
    )
    assert (output_dir / "accepted_review_candidates.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "accepted_review_candidates_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "by_decision" / "accept.json") == _load_json(
        FIXTURE_DIR / "by_decision" / "accept_v1.json"
    )
    assert (output_dir / "by_decision" / "accept.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "by_decision" / "accept_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "by_decision" / "revise.json") == _load_json(
        FIXTURE_DIR / "by_decision" / "revise_v1.json"
    )
    assert (output_dir / "by_decision" / "revise.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "by_decision" / "revise_v1.tsv"
    ).read_text(encoding="utf-8")
