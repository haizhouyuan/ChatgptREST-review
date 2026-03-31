from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.controller_route_parity_validation import (
    render_controller_route_parity_report_markdown,
    run_controller_route_parity_validation,
    snapshot_controller_route_parity_sample,
    write_controller_route_parity_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase10_controller_route_parity_samples_v1.json")


def test_phase10_controller_route_parity_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_controller_route_parity_validation(dataset)

    assert report.num_items == 5
    assert report.num_failed == 0


def test_controller_route_parity_snapshot_stays_job_for_workforce_planning() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "人力规划方案" in entry.input)

    snapshot = snapshot_controller_route_parity_sample(item)

    assert snapshot.scenario_pack_profile == "workforce_planning"
    assert snapshot.strategy_route_hint == "funnel"
    assert snapshot.controller_route == "funnel"
    assert snapshot.controller_execution_kind == "job"
    assert snapshot.controller_objective_kind == "answer"
    assert snapshot.route_parity is True


def test_controller_route_parity_snapshot_keeps_report_lane_for_research_report() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "行业研究报告" in entry.input)

    snapshot = snapshot_controller_route_parity_sample(item)

    assert snapshot.scenario_pack_profile == "research_report"
    assert snapshot.strategy_route_hint == "report"
    assert snapshot.controller_route == "report"
    assert snapshot.controller_execution_kind == "job"
    assert snapshot.route_parity is True


def test_controller_route_parity_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_controller_route_parity_validation(dataset)

    json_path, md_path = write_controller_route_parity_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_controller_route_parity_report_markdown(report)
    assert "phase10_controller_route_parity_samples_v1" in markdown
    assert "| Input | Pass | Profile | Strategy Route | Controller Route | Exec Kind | Parity | Mismatch |" in markdown
