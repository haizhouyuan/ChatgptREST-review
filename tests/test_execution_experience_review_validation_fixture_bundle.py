from __future__ import annotations

import json
from pathlib import Path

from ops.validate_execution_experience_review_outputs import validate_review_outputs


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(summary: dict) -> dict:
    normalized = json.loads(json.dumps(summary, ensure_ascii=False))
    normalized["candidates_path"] = Path(normalized["candidates_path"]).name
    normalized["reviewer_manifest_path"] = Path(normalized["reviewer_manifest_path"]).name
    normalized["review_outputs"] = [Path(item).name for item in normalized["review_outputs"]]
    for row in normalized["per_reviewer"]:
        row["path"] = Path(row["path"]).name
    return normalized


def test_execution_experience_review_validation_fixture_bundle_matches_expected_summary(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates_v1.json"
    manifest_path = tmp_path / "reviewer_manifest_v1.json"
    gemini_path = tmp_path / "gemini_no_mcp.json"
    claude_path = tmp_path / "claudeminmax.json"
    codex_path = tmp_path / "codex_auth_only.json"

    candidates_path.write_text((FIXTURE_DIR / "experience_candidates_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    manifest_path.write_text((FIXTURE_DIR / "reviewer_manifest_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    gemini_path.write_text((FIXTURE_DIR / "gemini_no_mcp_valid_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    claude_path.write_text((FIXTURE_DIR / "claudeminmax_unknown_candidate_v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    codex_invalid = _load_json(FIXTURE_DIR / "codex_auth_only_invalid_decision_v1.json")
    codex_duplicate = _load_json(FIXTURE_DIR / "codex_auth_only_duplicate_candidate_v1.json")
    codex_path.write_text(
        json.dumps(
            {
                "items": list(codex_invalid.get("items", [])) + list(codex_duplicate.get("items", [])),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = validate_review_outputs(
        candidates_path=candidates_path,
        review_json_paths=[gemini_path, claude_path, codex_path],
        reviewer_manifest_path=manifest_path,
        top_n=5,
    )

    expected = _load_json(FIXTURE_DIR / "validation_summary_expected_v1.json")
    assert _normalize(summary) == expected
