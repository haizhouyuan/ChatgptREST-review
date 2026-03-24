from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.branch_coverage_validation import (
    render_branch_coverage_report_markdown,
    run_branch_coverage_validation,
    snapshot_branch_coverage_sample,
    write_branch_coverage_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase11_branch_coverage_samples_v1.json")


def test_phase11_branch_coverage_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_branch_coverage_validation(dataset)

    assert report.num_items == 4
    assert report.num_failed == 0


def test_branch_coverage_clarify_case_stays_on_public_clarify_branch() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if entry.metadata.get("case_type") == "agent_v3_clarify")

    snapshot = snapshot_branch_coverage_sample(item)

    assert snapshot.validation_surface == "agent_v3_public_route"
    assert snapshot.response_status == "needs_followup"
    assert snapshot.route == "clarify"
    assert snapshot.controller_called is False
    assert snapshot.scenario_pack_profile == "interview_notes"


def test_branch_coverage_kb_direct_case_hits_kb_provider() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if entry.metadata.get("case_type") == "controller_kb_direct")

    snapshot = snapshot_branch_coverage_sample(item)

    assert snapshot.validation_surface == "controller_ask_kb_direct"
    assert snapshot.route == "kb_answer"
    assert snapshot.provider == "kb"
    assert snapshot.kb_used is True


def test_branch_coverage_implicit_team_fallback_is_removed() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if entry.metadata.get("case_type") == "controller_team_fallback")

    snapshot = snapshot_branch_coverage_sample(item)

    assert snapshot.validation_surface == "controller_execution_fallback"
    assert snapshot.route == "funnel"
    assert snapshot.controller_execution_kind == "job"
    assert snapshot.controller_objective_kind == "answer"
    assert snapshot.provider == "controller"


def test_branch_coverage_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_branch_coverage_validation(dataset)

    json_path, md_path = write_branch_coverage_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_branch_coverage_report_markdown(report)
    assert "phase11_branch_coverage_samples_v1" in markdown
    assert "| Case | Surface | Pass | Route | Exec Kind | KB Used | Profile | Mismatch |" in markdown
