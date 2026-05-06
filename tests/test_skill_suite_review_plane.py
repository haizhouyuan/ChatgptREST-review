from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from chatgptrest.evomap.knowledge.skill_suite_review_plane import import_validation_bundle
from ops.build_skill_suite_validation_bundle import build_bundle


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _build_fixture_bundle(tmp_path: Path, *, validation_id: str) -> Path:
    input_file = tmp_path / "inputs" / "source.md"
    qa_report = tmp_path / "run" / "qa" / "qa_report.json"
    summary = tmp_path / "run" / "summary.json"
    _write(input_file, "# source\n")
    _write_json(qa_report, {"issue_count": 0, "issues": []})
    _write_json(summary, {"selected_backend": "pdfplumber", "selection_confidence": "medium"})

    config = {
        "validation_id": validation_id,
        "captures": [{"id": "echo", "command": ["python3", "-c", "print('ok')"]}],
        "cases": [
            {
                "case_id": "report_positive",
                "suite": "report",
                "variant": "positive",
                "classification": "golden",
                "expected_outcome": "pass",
                "inputs": [{"alias": "source_material", "path": str(input_file)}],
                "artifacts": [
                    {"alias": "qa_report", "path": str(qa_report), "type": "file", "role": "qa"},
                    {"alias": "summary", "path": str(summary), "type": "file", "role": "summary"},
                ],
                "checks": [
                    {"id": "qa_issue_count_zero", "source_alias": "qa_report", "path": "issue_count", "op": "eq", "value": 0},
                    {"id": "summary_backend", "source_alias": "summary", "path": "selected_backend", "op": "eq", "value": "pdfplumber"},
                ],
            }
        ],
    }
    config_path = tmp_path / "config.json"
    _write_json(config_path, config)

    bundle_dir = tmp_path / "bundle"
    build_bundle(config_path=config_path, output_dir=bundle_dir, mode="copy")
    return bundle_dir


def test_import_validation_bundle_materializes_bundle_case_and_capture_docs(tmp_path: Path) -> None:
    bundle_dir = _build_fixture_bundle(tmp_path, validation_id="skill_suite_review_plane_fixture")
    db_path = tmp_path / "evomap.db"

    first = import_validation_bundle(db_path=db_path, bundle_dir=bundle_dir)
    second = import_validation_bundle(db_path=db_path, bundle_dir=bundle_dir)

    assert first["ok"] is True
    assert first["case_docs"] == 1
    assert first["suite_entities"] == 1
    assert first["evidence_rows"] == 7
    assert second["db_stats"] == first["db_stats"]

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("select count(*) from documents").fetchone()[0] == 3
        assert conn.execute("select count(*) from episodes").fetchone()[0] == 2
        assert conn.execute("select count(*) from atoms").fetchone()[0] == 2
        assert conn.execute("select count(*) from entities").fetchone()[0] == 1
        assert conn.execute("select count(*) from edges").fetchone()[0] == 4
        assert conn.execute("select count(*) from evidence").fetchone()[0] == 7

        bundle_row = conn.execute(
            "select answer, promotion_status from atoms where canonical_question = ?",
            ("skill suite validation bundle skill_suite_review_plane_fixture",),
        ).fetchone()
        assert bundle_row is not None
        assert "covers 1 skill-suite cases" in bundle_row[0]
        assert bundle_row[1] == "staged"

        case_atom_id = conn.execute(
            "select atom_id from atoms where canonical_question = ?",
            ("skill suite case report_positive",),
        ).fetchone()[0]
        evidence_rows = conn.execute(
            "select evidence_role, span_ref from evidence where atom_id = ? order by evidence_role, span_ref",
            (case_atom_id,),
        ).fetchall()
        assert [row[0] for row in evidence_rows] == ["artifact", "artifact", "input"]
        assert [row[1] for row in evidence_rows] == ["qa_report", "summary", "source_material"]

        capture_doc = conn.execute(
            "select title from documents where raw_ref = ?",
            ("skill-suite://capture/skill_suite_review_plane_fixture/echo",),
        ).fetchone()
        assert capture_doc is not None
        assert capture_doc[0] == "Skill suite capture echo"

        case_edge = conn.execute(
            "select count(*) from edges where edge_type = 'PART_OF_VALIDATION_BUNDLE'"
        ).fetchone()[0]
        assert case_edge == 1
    finally:
        conn.close()
