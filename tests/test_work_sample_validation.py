from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.work_sample_validation import (
    render_work_sample_report_markdown,
    run_work_sample_validation,
    snapshot_work_sample,
    write_work_sample_report,
)


DATASET_PATH = Path("eval_datasets/phase7_business_work_samples_v1.json")


def test_phase7_business_work_sample_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_work_sample_validation(dataset)

    assert report.num_items == 7
    assert report.num_failed == 0


def test_snapshot_work_sample_includes_front_door_fields() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "行业研究报告" in entry.input)

    snapshot = snapshot_work_sample(item)

    assert snapshot.scenario_pack_profile == "research_report"
    assert snapshot.effective_route_hint == "report"
    assert snapshot.contract_task_template == "report_generation"
    assert snapshot.strategy_clarify_question_count >= 1


def test_write_work_sample_report_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_work_sample_validation(dataset)

    json_path, md_path = write_work_sample_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_work_sample_report_markdown(report)
    assert "phase7_business_work_samples_v1" in markdown
    assert "| Input | Pass | Profile | Route | Clarify | Mismatch |" in markdown
