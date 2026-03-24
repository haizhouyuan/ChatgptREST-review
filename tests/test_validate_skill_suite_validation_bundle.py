from __future__ import annotations

import json
from pathlib import Path

from ops.build_skill_suite_validation_bundle import build_bundle
from ops.validate_skill_suite_validation_bundle import validate_bundle


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _build_fixture_bundle(tmp_path: Path) -> Path:
    input_file = tmp_path / "inputs" / "source.md"
    qa_report = tmp_path / "run" / "qa" / "qa_report.json"
    _write(input_file, "# source\n")
    _write_json(qa_report, {"issue_count": 1, "issues": [{"type": "duplicate_sections"}]})
    config = {
        "validation_id": "skill_suite_validate_bundle",
        "cases": [
            {
                "case_id": "report_negative",
                "suite": "report",
                "variant": "negative",
                "expected_outcome": "fail",
                "inputs": [{"alias": "source_material", "path": str(input_file)}],
                "artifacts": [{"alias": "qa_report", "path": str(qa_report), "type": "file", "role": "qa"}],
                "checks": [
                    {
                        "id": "duplicate_section_detected",
                        "source_alias": "qa_report",
                        "path": "issues.*.type",
                        "op": "contains",
                        "value": "duplicate_sections"
                    }
                ]
            }
        ]
    }
    config_path = tmp_path / "config.json"
    _write_json(config_path, config)
    out = tmp_path / "bundle"
    build_bundle(config_path=config_path, output_dir=out, mode="copy")
    return out


def test_validate_bundle_passes_for_consistent_bundle(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path)
    result = validate_bundle(bundle_dir=bundle)
    assert result["ok"] is True
    assert all(result["checks"].values())


def test_validate_bundle_flags_missing_required_file(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(tmp_path)
    (bundle / "README.md").unlink()
    result = validate_bundle(bundle_dir=bundle)
    assert result["ok"] is False
    assert result["checks"]["required_files_ok"] is False
