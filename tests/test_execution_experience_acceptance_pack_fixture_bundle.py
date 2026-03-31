from __future__ import annotations

import json
from pathlib import Path

from ops.export_execution_experience_acceptance_pack import export_pack


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311")


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_manifest(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    if normalized.get("source"):
        for key in ("candidates_path", "decisions_path"):
            if normalized["source"].get(key):
                normalized["source"][key] = Path(str(normalized["source"][key])).name
    if normalized.get("files"):
        for key in ("accepted_candidates_json", "accepted_candidates_tsv"):
            if normalized["files"].get(key):
                normalized["files"][key] = Path(str(normalized["files"][key])).name
    return normalized


def test_execution_experience_acceptance_pack_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates_v1.json"
    decisions_path = tmp_path / "execution_experience_review_decisions_v1.tsv"
    output_dir = tmp_path / "accepted_pack"

    candidates_path.write_text((FIXTURE_DIR / "experience_candidates_v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    decisions_path.write_text(
        (FIXTURE_DIR / "execution_experience_review_decisions_v1.tsv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = export_pack(
        candidates_path=candidates_path,
        decisions_path=decisions_path,
        output_dir=output_dir,
    )

    assert result["accepted_candidates"] == 1
    assert sorted(Path(path).name for path in result["files"]) == [
        "accepted_candidates.json",
        "accepted_candidates.tsv",
        "manifest.json",
        "smoke_manifest.json",
    ]
    assert _load_json(output_dir / "accepted_candidates.json") == _load_json(FIXTURE_DIR / "accepted_candidates_v1.json")
    assert (output_dir / "accepted_candidates.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "accepted_candidates_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _normalize_manifest(_load_json(output_dir / "manifest.json")) == _load_json(FIXTURE_DIR / "manifest_v1.json")
    assert _load_json(output_dir / "smoke_manifest.json") == _load_json(FIXTURE_DIR / "smoke_manifest_v1.json")
