from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.agent_v3_route_work_sample_validation import (
    render_agent_v3_route_work_sample_report_markdown,
    run_agent_v3_route_work_sample_validation,
    snapshot_agent_v3_route_work_sample,
    write_agent_v3_route_work_sample_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase9_agent_v3_route_work_samples_v1.json")


def test_phase9_agent_v3_route_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_agent_v3_route_work_sample_validation(dataset)

    assert report.num_items == 7
    assert report.num_failed == 0


def test_agent_v3_route_snapshot_clarify_case_preserves_pack_context() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "例会纪要" in entry.input)

    snapshot = snapshot_agent_v3_route_work_sample(item)

    assert snapshot.response_status == "needs_followup"
    assert snapshot.response_route == "clarify"
    assert snapshot.scenario_pack_profile == "meeting_summary"
    assert snapshot.strategy_route_hint == "report"
    assert snapshot.strategy_clarify_required is True
    assert snapshot.controller_called is False
    assert snapshot.branch_taken == "clarify"


def test_agent_v3_route_snapshot_business_planning_reaches_controller_report_lane() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "业务规划框架" in entry.input)

    snapshot = snapshot_agent_v3_route_work_sample(item)

    assert snapshot.response_status == "completed"
    assert snapshot.response_route == "report"
    assert snapshot.scenario_pack_profile == "business_planning"
    assert snapshot.strategy_route_hint == "report"
    assert snapshot.controller_called is True
    assert snapshot.controller_route == "report"
    assert snapshot.branch_taken == "controller"


def test_agent_v3_route_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_agent_v3_route_work_sample_validation(dataset)

    json_path, md_path = write_agent_v3_route_work_sample_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_agent_v3_route_work_sample_report_markdown(report)
    assert "phase9_agent_v3_route_work_samples_v1" in markdown
    assert "| Input | Pass | Status | Route | Profile | Branch | Mismatch |" in markdown
