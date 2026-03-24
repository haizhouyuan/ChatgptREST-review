from __future__ import annotations

import json
from pathlib import Path

from ops.build_skill_suite_validation_bundle import build_bundle


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def test_build_bundle_materializes_cases_and_evaluates_checks(tmp_path: Path) -> None:
    input_file = tmp_path / "inputs" / "source.md"
    qa_report = tmp_path / "run" / "qa" / "qa_report.json"
    summary = tmp_path / "run" / "summary.json"
    artifact_note = tmp_path / "run" / "notes.txt"
    _write(input_file, "# source\n")
    _write_json(qa_report, {"issue_count": 0, "issues": []})
    _write_json(summary, {"selected_backend": "pdfplumber", "selection_confidence": "medium"})
    _write(artifact_note, "hello\n")

    config = {
        "validation_id": "skill_suite_test_bundle",
        "captures": [{"id": "echo", "command": ["python3", "-c", "print('ok')"]}],
        "runner_files": [{"alias": "runner", "path": str(input_file)}],
        "cases": [
            {
                "case_id": "report_positive",
                "suite": "report",
                "variant": "positive",
                "expected_outcome": "pass",
                "inputs": [{"alias": "source_material", "path": str(input_file)}],
                "artifacts": [
                    {"alias": "run_dir", "path": str(tmp_path / "run"), "type": "dir", "role": "run_dir"},
                    {"alias": "qa_report", "path": str(qa_report), "type": "file", "role": "qa"},
                    {"alias": "summary", "path": str(summary), "type": "file", "role": "summary"},
                ],
                "checks": [
                    {"id": "qa_issue_count_zero", "source_alias": "qa_report", "path": "issue_count", "op": "eq", "value": 0},
                    {
                        "id": "summary_backend",
                        "source_alias": "summary",
                        "path": "selected_backend",
                        "op": "eq",
                        "value": "pdfplumber"
                    }
                ]
            }
        ]
    }
    config_path = tmp_path / "config.json"
    _write_json(config_path, config)

    out = tmp_path / "bundle"
    result = build_bundle(config_path=config_path, output_dir=out, mode="copy")

    assert result["ok"] is True
    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["case_count"] == 1
    matrix = json.loads((out / "case_matrix.json").read_text(encoding="utf-8"))
    case = matrix["cases"][0]
    assert case["checks_ok"] is True
    assert case["verdict_matches_expectation"] is True
    assert (out / "captures" / "echo.stdout.txt").read_text(encoding="utf-8").strip() == "ok"
    assert (out / "cases" / "report_positive" / "evidence" / "run_dir" / "qa" / "qa_report.json").exists()


def test_build_bundle_flags_missing_json_source_alias(tmp_path: Path) -> None:
    input_file = tmp_path / "inputs" / "source.md"
    _write(input_file, "x\n")
    config = {
        "validation_id": "skill_suite_test_bundle_missing",
        "cases": [
            {
                "case_id": "missing_source_alias",
                "suite": "report",
                "variant": "negative",
                "expected_outcome": "fail",
                "inputs": [{"alias": "source_material", "path": str(input_file)}],
                "artifacts": [],
                "checks": [
                    {"id": "missing_alias", "source_alias": "qa_report", "path": "issue_count", "op": "eq", "value": 0}
                ]
            }
        ]
    }
    config_path = tmp_path / "config.json"
    _write_json(config_path, config)

    out = tmp_path / "bundle"
    build_bundle(config_path=config_path, output_dir=out, mode="copy")
    matrix = json.loads((out / "case_matrix.json").read_text(encoding="utf-8"))
    assert matrix["cases"][0]["checks_ok"] is False
    assert matrix["cases"][0]["verdict_matches_expectation"] is True
