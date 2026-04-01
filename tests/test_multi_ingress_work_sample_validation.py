from __future__ import annotations

from pathlib import Path

import pytest

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.multi_ingress_work_sample_validation import (
    render_multi_ingress_work_sample_report_markdown,
    run_multi_ingress_work_sample_validation,
    snapshot_multi_ingress_work_sample,
    write_multi_ingress_work_sample_report,
)


DATASET_PATH = Path("eval_datasets/phase8_multi_ingress_work_samples_v1.json")


def test_phase8_multi_ingress_dataset_passes() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)

    report = run_multi_ingress_work_sample_validation(dataset)

    assert report.num_items == 7
    assert report.num_cases == 28
    assert report.num_failed == 0


def test_snapshot_multi_ingress_feishu_preserves_research_report_semantics() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "行业研究报告" in entry.input)

    snapshot = snapshot_multi_ingress_work_sample(item, ingress_profile="feishu_ws")

    assert snapshot.source == "feishu"
    assert snapshot.ingress_lane == "advisor_advise_v2"
    assert snapshot.scenario_pack_profile == "research_report"
    assert snapshot.effective_route_hint == "report"
    assert snapshot.strategy_clarify_required is True


def test_snapshot_multi_ingress_consult_selects_deep_research_models() -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "国产替代进展" in entry.input)

    snapshot = snapshot_multi_ingress_work_sample(item, ingress_profile="consult_rest")

    assert snapshot.scenario_pack_profile == "topic_research"
    assert snapshot.consult_models == ["chatgpt_dr", "gemini_dr"]


def test_consult_snapshot_reuses_live_consult_summary_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
    from chatgptrest.advisor.task_intake import build_task_intake_spec, summarize_task_intake
    from chatgptrest.api.routes_consult import summarize_scenario_pack
    import chatgptrest.eval.multi_ingress_work_sample_validation as validation

    dataset = EvalDataset.from_file(DATASET_PATH)
    item = next(entry for entry in dataset if "行业研究报告" in entry.input)
    captured: dict[str, object] = {}

    def _fake_select_consult_models(**kwargs):
        captured.update(kwargs)
        return ["chatgpt_pro", "gemini_deepthink"]

    monkeypatch.setattr(validation, "_select_consult_models", _fake_select_consult_models)

    snapshot = snapshot_multi_ingress_work_sample(item, ingress_profile="consult_rest")

    task_intake = build_task_intake_spec(
        ingress_lane="other",
        default_source="rest",
        raw_source="rest",
        raw_task_intake=item.metadata.get("task_intake"),
        question=item.input,
        goal_hint=str(item.metadata.get("goal_hint") or ""),
        trace_id="test-trace",
        context={},
        attachments=[],
    )
    scenario_pack = resolve_scenario_pack(
        task_intake,
        goal_hint=str(item.metadata.get("goal_hint") or ""),
        context={},
    )
    if scenario_pack is not None:
        task_intake = apply_scenario_pack(task_intake, scenario_pack)

    assert snapshot.consult_models == ["chatgpt_pro", "gemini_deepthink"]
    assert captured["task_intake_summary"] == summarize_task_intake(task_intake)
    assert captured["scenario_pack_summary"] == (summarize_scenario_pack(scenario_pack) or {})


def test_write_multi_ingress_report_emits_json_and_markdown(tmp_path: Path) -> None:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_multi_ingress_work_sample_validation(dataset)

    json_path, md_path = write_multi_ingress_work_sample_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_multi_ingress_work_sample_report_markdown(report)
    assert "phase8_multi_ingress_work_samples_v1" in markdown
    assert "| Ingress | Input | Pass | Profile | Route | Models | Mismatch |" in markdown
