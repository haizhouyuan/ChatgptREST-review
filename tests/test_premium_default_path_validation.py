from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.premium_default_path_validation import (
    render_premium_default_path_report_markdown,
    run_premium_default_path_validation,
    snapshot_premium_default_path_sample,
    write_premium_default_path_report,
)


DATASET_PATH = Path("eval_datasets/phase27_premium_default_path_samples_v1.json")


def test_phase27_premium_default_path_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_premium_default_path_validation(dataset)

    assert report.num_items == 6
    assert report.num_failed == 0


def test_thinking_heavy_research_stays_on_chatgpt_default_llm_path() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "快速分析欧洲两轮车车身业务" in entry.input)

    snapshot = snapshot_premium_default_path_sample(item)

    assert snapshot.scenario_pack_profile == "topic_research"
    assert snapshot.route == "analysis_heavy"
    assert snapshot.provider == "chatgpt"
    assert snapshot.preset == "thinking_heavy"
    assert snapshot.job_kind == "chatgpt_web.ask"
    assert snapshot.execution_kind == "job"
    assert snapshot.team_lane is False
    assert snapshot.llm_default_path is True


def test_premium_default_path_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_premium_default_path_validation(dataset)

    json_path, md_path = write_premium_default_path_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_premium_default_path_report_markdown(report)
    assert "phase27_premium_default_path_samples_v1" in markdown
    assert "| Input | Pass | Profile | Route | Provider | Preset | Kind | Exec Kind | Objective Kind | Default LLM Path | Mismatch |" in markdown
