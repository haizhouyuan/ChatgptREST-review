from __future__ import annotations

import csv
import json
from pathlib import Path

import ops.validate_execution_experience_review_outputs as validation_module
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.compose_execution_activity_review_decisions import FIELDNAMES as ACTIVITY_FIELDNAMES
from ops.execution_experience_review_reviewer_identity import load_expected_reviewers
from ops.run_execution_experience_review_cycle import run_cycle


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_execution_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ACTIVITY_FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_exec",
            source="agent_activity",
            project="ChatgptREST",
            raw_ref="/tmp/doc_exec.json",
            title="doc_exec",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec",
            doc_id="doc_exec",
            episode_type="workflow.completed",
            title="workflow.completed",
            summary="workflow.completed",
            start_ref="doc_exec:1",
            end_ref="doc_exec:1",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_exec",
            episode_id="ep_exec",
            atom_type="lesson",
            question="at_exec",
            answer="execution review cycle complete",
            canonical_question="activity: workflow.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps({"task_ref": "issue-115", "trace_id": "trace-115"}, ensure_ascii=False, sort_keys=True),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()


def _normalize_manifest(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    pack_path = str(payload.get("pack_path") or "")
    normalized["pack_path"] = Path(pack_path).name
    normalized["review_output_dir"] = Path(str(payload.get("review_output_dir") or "")).name
    for index, row in enumerate(normalized.get("reviewers", [])):
        source_row = payload["reviewers"][index]
        output_path = str(source_row.get("output_path") or "")
        row["output_path"] = Path(output_path).name
        row["instruction"] = str(source_row.get("instruction") or "")
        if pack_path:
            row["instruction"] = row["instruction"].replace(pack_path, Path(pack_path).name)
        if output_path:
            row["instruction"] = row["instruction"].replace(output_path, Path(output_path).name)
    return normalized


def _normalize_validation_summary(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["candidates_path"] = Path(str(payload.get("candidates_path") or "")).name
    reviewer_manifest_path = str(payload.get("reviewer_manifest_path") or "")
    normalized["reviewer_manifest_path"] = Path(reviewer_manifest_path).name if reviewer_manifest_path else ""
    normalized["review_outputs"] = [Path(str(item)).name for item in payload.get("review_outputs", [])]
    for index, row in enumerate(normalized.get("per_reviewer", [])):
        row["path"] = Path(str(payload["per_reviewer"][index].get("path") or "")).name
    return normalized


def _normalize_review_backlog(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["candidates_path"] = Path(str(payload.get("candidates_path") or "")).name
    decisions_path = str(payload.get("decisions_path") or "")
    normalized["decisions_path"] = Path(decisions_path).name if decisions_path else ""
    reviewer_manifest_path = str(payload.get("reviewer_manifest_path") or "")
    normalized["reviewer_manifest_path"] = Path(reviewer_manifest_path).name if reviewer_manifest_path else ""
    return normalized


def _normalize_cycle_summary(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["decision_source_dir"] = Path(str(payload.get("decision_source_dir") or "")).name if payload.get("decision_source_dir") else ""
    normalized["execution_decisions_path"] = Path(str(payload.get("execution_decisions_path") or "")).name
    if "candidate_export" in normalized:
        candidate_export = normalized["candidate_export"]
        source_export = payload["candidate_export"]
        candidate_export["output_dir"] = Path(str(source_export.get("output_dir") or "")).name
        candidate_export["summary_path"] = Path(str(source_export.get("summary_path") or "")).name
        candidate_export["files"] = [Path(str(item)).name for item in source_export.get("files", [])]
    if "review_pack" in normalized:
        review_pack = normalized["review_pack"]
        source_pack = payload["review_pack"]
        review_pack["output_dir"] = Path(str(source_pack.get("output_dir") or "")).name
        review_pack["pack_path"] = Path(str(source_pack.get("pack_path") or "")).name
        review_pack["prompt_path"] = Path(str(source_pack.get("prompt_path") or "")).name
        review_pack["summary_path"] = Path(str(source_pack.get("summary_path") or "")).name
    if "reviewer_manifest" in normalized:
        manifest = normalized["reviewer_manifest"]
        source_manifest = payload["reviewer_manifest"]
        manifest["manifest_path"] = Path(str(source_manifest.get("manifest_path") or "")).name
        manifest["review_output_dir"] = Path(str(source_manifest.get("review_output_dir") or "")).name
        pack_path = str(payload.get("review_pack", {}).get("pack_path") or "")
        for index, row in enumerate(manifest.get("reviewers", [])):
            source_row = source_manifest["reviewers"][index]
            output_path = str(source_row.get("output_path") or "")
            row["output_path"] = Path(output_path).name
            row["instruction"] = str(source_row.get("instruction") or "")
            if pack_path:
                row["instruction"] = row["instruction"].replace(pack_path, Path(pack_path).name)
            if output_path:
                row["instruction"] = row["instruction"].replace(output_path, Path(output_path).name)
    if "review_backlog" in normalized:
        normalized["review_backlog"] = _normalize_review_backlog(payload["review_backlog"])
    if "review_output_validation" in normalized:
        normalized["review_output_validation"] = _normalize_validation_summary(payload["review_output_validation"])
    if "review_output_validation_path" in normalized:
        normalized["review_output_validation_path"] = Path(str(payload.get("review_output_validation_path") or "")).name
    if "review_backlog_path" in normalized:
        normalized["review_backlog_path"] = Path(str(payload.get("review_backlog_path") or "")).name
    if "review_output_validation" in normalized:
        normalized["review_output_validation"].pop("review_output_validation_path", None)
    keep_keys = {
        "ok",
        "mode",
        "decision_source_dir",
        "execution_decisions_path",
        "candidate_export",
        "review_pack",
        "reviewer_manifest",
        "review_backlog",
        "review_backlog_path",
        "review_output_validation",
        "review_output_validation_path",
        "validation_errors",
    }
    return {key: normalized[key] for key in keep_keys if key in normalized}


def _prepare_refresh_only_cycle(tmp_path: Path) -> tuple[dict, Path]:
    # The current validator imports the public helper but still calls the old private alias.
    validation_module._load_expected_reviewers = load_expected_reviewers

    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )
    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    return first, Path(first["reviewer_manifest"]["review_output_dir"])


def _assert_refresh_only_artifacts_match_bundle(first: dict) -> None:
    candidates = _load_json(Path(first["candidate_export"]["output_dir"]) / "experience_candidates.json")
    manifest = _load_json(Path(first["reviewer_manifest"]["manifest_path"]))
    assert candidates == _load_json(FIXTURE_DIR / "experience_candidates_v1.json")
    assert _normalize_manifest(manifest) == _load_json(FIXTURE_DIR / "reviewer_manifest_v1.json")


def test_execution_experience_review_validation_failure_fixture_bundle_complete_required(tmp_path: Path) -> None:
    first, review_output_dir = _prepare_refresh_only_cycle(tmp_path)
    _assert_refresh_only_artifacts_match_bundle(first)

    review_output = review_output_dir / "gemini_no_mcp.json"
    review_output.write_text((FIXTURE_DIR / "gemini_no_mcp_only_v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    try:
        run_cycle(
            db_path=tmp_path / "evomap.db",
            output_root=tmp_path / "experience_cycle",
            activity_review_root=tmp_path / "activity_cycle",
            decisions_path=tmp_path / "execution_review_decisions_v1.tsv",
            review_json_paths=[review_output],
            base_experience_decisions_path=None,
            limit=50,
            require_complete_reviews=True,
        )
    except RuntimeError as exc:
        assert "review outputs incomplete" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for require_complete_reviews fixture")

    latest = sorted((tmp_path / "experience_cycle").iterdir())[-1]
    combined = {
        "cycle_summary": _normalize_cycle_summary(_load_json(latest / "cycle_summary.json")),
        "review_output_validation_summary": _normalize_validation_summary(
            _load_json(latest / "review_output_validation_summary.json")
        ),
    }
    assert combined == _load_json(FIXTURE_DIR / "validation_failed_complete_required_summary_v1.json")


def test_execution_experience_review_validation_failure_fixture_bundle_valid_required(tmp_path: Path) -> None:
    first, review_output_dir = _prepare_refresh_only_cycle(tmp_path)
    _assert_refresh_only_artifacts_match_bundle(first)

    review_output = review_output_dir / "gemini_no_mcp.json"
    review_output.write_text(
        (FIXTURE_DIR / "gemini_no_mcp_invalid_decision_v1.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    try:
        run_cycle(
            db_path=tmp_path / "evomap.db",
            output_root=tmp_path / "experience_cycle",
            activity_review_root=tmp_path / "activity_cycle",
            decisions_path=tmp_path / "execution_review_decisions_v1.tsv",
            review_json_paths=[review_output],
            base_experience_decisions_path=None,
            limit=50,
            require_valid_reviews=True,
        )
    except RuntimeError as exc:
        assert "structural validation" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for require_valid_reviews fixture")

    latest = sorted((tmp_path / "experience_cycle").iterdir())[-1]
    combined = {
        "cycle_summary": _normalize_cycle_summary(_load_json(latest / "cycle_summary.json")),
        "review_output_validation_summary": _normalize_validation_summary(
            _load_json(latest / "review_output_validation_summary.json")
        ),
    }
    assert combined == _load_json(FIXTURE_DIR / "validation_failed_valid_required_summary_v1.json")
