from __future__ import annotations

import json
from pathlib import Path

from ops.export_execution_experience_governance_queues import export_queues


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311")


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_summary(summary: dict) -> dict:
    normalized = json.loads(json.dumps(summary, ensure_ascii=False))
    for key in ("input_tsv", "output_dir", "summary_path"):
        if normalized.get(key):
            normalized[key] = Path(str(normalized[key])).name
    for bucket_key in ("queue_files", "action_files"):
        if bucket_key not in normalized:
            continue
        for item in normalized[bucket_key].values():
            if item.get("json_path"):
                item["json_path"] = str(Path(str(item["json_path"])).relative_to(Path(summary["output_dir"])))
            if item.get("tsv_path"):
                item["tsv_path"] = str(Path(str(item["tsv_path"])).relative_to(Path(summary["output_dir"])))
    return normalized


def test_execution_experience_governance_queue_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    input_tsv = tmp_path / "review_decision_scaffold_input_v1.tsv"
    output_dir = tmp_path / "governance_queues"
    input_tsv.write_text((FIXTURE_DIR / "review_decision_scaffold_input_v1.tsv").read_text(encoding="utf-8"), encoding="utf-8")

    summary = export_queues(input_tsv=input_tsv, output_dir=output_dir)

    assert _normalize_summary(summary) == _load_json(FIXTURE_DIR / "governance_queue_summary_v1.json")
    assert _load_json(output_dir / "review_pending.json") == _load_json(FIXTURE_DIR / "review_pending_v1.json")
    assert (output_dir / "review_pending.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "review_pending_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "under_reviewed.json") == _load_json(FIXTURE_DIR / "under_reviewed_v1.json")
    assert (output_dir / "under_reviewed.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "under_reviewed_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "decision_ready.json") == _load_json(FIXTURE_DIR / "decision_ready_v1.json")
    assert (output_dir / "decision_ready.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "decision_ready_v1.tsv"
    ).read_text(encoding="utf-8")
    assert _load_json(output_dir / "by_action" / "accept_candidate.json") == _load_json(
        FIXTURE_DIR / "by_action" / "accept_candidate_v1.json"
    )
    assert (output_dir / "by_action" / "accept_candidate.tsv").read_text(encoding="utf-8") == (
        FIXTURE_DIR / "by_action" / "accept_candidate_v1.tsv"
    ).read_text(encoding="utf-8")
