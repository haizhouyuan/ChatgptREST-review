from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from chatgptrest.advisor.runtime import reset_advisor_runtime
from ops.build_skill_suite_validation_bundle import build_bundle
from ops.ingest_skill_suite_validation_to_evomap import ingest_bundle


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


def test_ingest_bundle_writes_telemetry_registry_and_review_plane(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _build_fixture_bundle(tmp_path, validation_id="skill_suite_ingest_fixture")
    db_path = tmp_path / "evomap_knowledge.db"
    registry_path = tmp_path / "registry.json"
    output_dir = tmp_path / "ingest_output"

    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(db_path))
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", str(tmp_path / "events.db"))
    monkeypatch.setenv("OPENMIND_KB_DB", str(tmp_path / "kb_registry.db"))
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(tmp_path / "kb_search.db"))
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", str(tmp_path / "kb_vectors.db"))
    monkeypatch.setenv("OPENMIND_MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("OPENMIND_DB_PATH", str(tmp_path / "effects.db"))
    monkeypatch.setenv("OPENMIND_DEDUP_DB", str(tmp_path / "dedup.db"))
    monkeypatch.setenv("OPENMIND_CHECKPOINT_DB", str(tmp_path / "checkpoint.db"))

    reset_advisor_runtime()
    try:
        result = ingest_bundle(
            bundle_dir=bundle_dir,
            db_path=db_path,
            registry_path=registry_path,
            owner="codex",
            stage="offline_replay",
            output_dir=output_dir,
            emit_telemetry=True,
            session_id="session-skill-suite-ingest",
            trace_id="trace-skill-suite-ingest",
            agent_name="codex",
        )
    finally:
        reset_advisor_runtime()

    assert result["ok"] is True
    assert result["telemetry"]["recorded"] == 2
    assert result["telemetry"]["signal_types"] == [
        "workflow.completed",
        "tool.completed",
    ]
    assert result["review_plane_import"]["case_docs"] == 1
    assert result["registry"]["run"]["outcome"] == "passed"

    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert len(registry_payload["candidates"]) == 1
    assert len(registry_payload["runs"]) == 1
    assert registry_payload["candidates"][0]["candidate_id"] == "skill_suite_validation::skill_suite_ingest_fixture"

    conn = sqlite3.connect(db_path)
    try:
        bundle_activity = conn.execute(
            "select count(*) from atoms where canonical_question = ?",
            ("activity: workflow.completed",),
        ).fetchone()[0]
        case_activity = conn.execute(
            "select count(*) from atoms where canonical_question = ?",
            ("activity: tool.completed",),
        ).fetchone()[0]
        bundle_review = conn.execute(
            "select count(*) from atoms where canonical_question = ?",
            ("skill suite validation bundle skill_suite_ingest_fixture",),
        ).fetchone()[0]
        assert bundle_activity == 1
        assert case_activity == 1
        assert bundle_review == 1
    finally:
        conn.close()

    assert (output_dir / "summary.json").exists()
    assert (output_dir / "registry_result.json").exists()
    assert (output_dir / "telemetry_result.json").exists()
    assert (output_dir / "review_plane_import.json").exists()
