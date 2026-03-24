"""Business work-sample validation for front-door planning/research asks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from chatgptrest.advisor.ask_contract import normalize_ask_contract
from chatgptrest.advisor.ask_strategist import build_strategy_plan
from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import build_task_intake_spec, task_intake_to_contract_seed
from chatgptrest.eval.datasets import EvalDataset, EvalItem


_EXPECTED_FIELD_MAP = {
    "expected_scenario": "scenario",
    "expected_output_shape": "output_shape",
    "expected_profile": "scenario_pack_profile",
    "expected_route_hint": "effective_route_hint",
    "expected_execution_preference": "scenario_pack_execution_preference",
    "expected_clarify_required": "strategy_clarify_required",
    "expected_task_template": "contract_task_template",
    "expected_acceptance_profile": "acceptance_profile",
}


@dataclass
class WorkSampleSnapshot:
    input: str
    source: str
    ingress_lane: str
    scenario: str
    output_shape: str
    acceptance_profile: str
    min_evidence_items: int
    scenario_pack_profile: str = ""
    scenario_pack_route_hint: str = ""
    scenario_pack_execution_preference: str = ""
    scenario_pack_prompt_template_override: str = ""
    scenario_pack_watch_checkpoint: str = ""
    contract_task_template: str = ""
    contract_risk_class: str = ""
    contract_completeness: float = 0.0
    effective_route_hint: str = ""
    strategy_clarify_required: bool = False
    strategy_clarify_question_count: int = 0
    strategy_model_family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkSampleValidationResult:
    item_input: str
    passed: bool
    snapshot: WorkSampleSnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class WorkSampleValidationReport:
    dataset_name: str
    num_items: int
    num_passed: int
    num_failed: int
    results: list[WorkSampleValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "num_items": self.num_items,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def snapshot_work_sample(item: EvalItem, *, trace_prefix: str = "work-sample") -> WorkSampleSnapshot:
    meta = dict(item.metadata or {})
    context = dict(meta.get("context") or {})
    raw_task_intake = dict(meta.get("task_intake") or {})
    raw_contract = dict(meta.get("contract") or {})
    attachments = list(meta.get("attachments") or [])
    goal_hint = str(meta.get("goal_hint") or "")
    ingress_lane = str(meta.get("ingress_lane") or "agent_v3")
    default_source = str(meta.get("default_source") or "rest")
    raw_source = str(meta.get("source") or "")
    trace_id = str(meta.get("trace_id") or f"{trace_prefix}:{abs(hash(item.input)) % 1_000_000}")
    session_id = str(meta.get("session_id") or f"session-{abs(hash((item.input, 's'))) % 1_000_000}")
    user_id = str(meta.get("user_id") or "eval-user")

    task_intake = build_task_intake_spec(
        ingress_lane=ingress_lane,
        default_source=default_source,
        raw_source=raw_source,
        raw_task_intake=raw_task_intake,
        raw_contract=raw_contract,
        message=item.input,
        goal_hint=goal_hint,
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        context=context,
        attachments=attachments,
        client_name=str(meta.get("client_name") or ""),
    )

    scenario_pack = resolve_scenario_pack(task_intake, goal_hint=goal_hint, context=context)
    if scenario_pack is not None:
        task_intake = apply_scenario_pack(task_intake, scenario_pack)
        context["scenario_pack"] = scenario_pack.to_dict()
    context["task_intake"] = task_intake.to_dict()

    contract_seed = task_intake_to_contract_seed(task_intake)
    merged_contract = dict(contract_seed)
    merged_contract.update(raw_contract)
    contract, _ = normalize_ask_contract(
        message=item.input,
        raw_contract=merged_contract,
        goal_hint=goal_hint,
        context=context,
    )
    strategy = build_strategy_plan(
        message=item.input,
        contract=contract,
        goal_hint=goal_hint,
        context=context,
    )

    pack_dict = scenario_pack.to_dict() if scenario_pack is not None else {}
    return WorkSampleSnapshot(
        input=item.input,
        source=task_intake.source,
        ingress_lane=task_intake.ingress_lane,
        scenario=task_intake.scenario,
        output_shape=task_intake.output_shape,
        acceptance_profile=str(task_intake.acceptance.profile),
        min_evidence_items=int(task_intake.acceptance.min_evidence_items),
        scenario_pack_profile=str(pack_dict.get("profile") or ""),
        scenario_pack_route_hint=str(pack_dict.get("route_hint") or ""),
        scenario_pack_execution_preference=str(pack_dict.get("execution_preference") or ""),
        scenario_pack_prompt_template_override=str(pack_dict.get("prompt_template_override") or ""),
        scenario_pack_watch_checkpoint=str(dict(pack_dict.get("watch_policy") or {}).get("checkpoint") or ""),
        contract_task_template=str(contract.task_template or ""),
        contract_risk_class=str(contract.risk_class or ""),
        contract_completeness=float(contract.contract_completeness or 0.0),
        effective_route_hint=str(strategy.route_hint or ""),
        strategy_clarify_required=bool(strategy.clarify_required),
        strategy_clarify_question_count=len(list(strategy.clarify_questions or [])),
        strategy_model_family=str(strategy.model_family or ""),
    )


def validate_work_sample(item: EvalItem) -> WorkSampleValidationResult:
    snapshot = snapshot_work_sample(item)
    expected = {
        key: value
        for key, value in dict(item.metadata or {}).items()
        if key in _EXPECTED_FIELD_MAP
    }
    mismatches: dict[str, dict[str, Any]] = {}
    snapshot_dict = snapshot.to_dict()

    for expected_key, snapshot_key in _EXPECTED_FIELD_MAP.items():
        if expected_key not in expected:
            continue
        actual = snapshot_dict.get(snapshot_key)
        wanted = expected[expected_key]
        if actual != wanted:
            mismatches[expected_key] = {"expected": wanted, "actual": actual}

    return WorkSampleValidationResult(
        item_input=item.input,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_work_sample_validation(dataset: EvalDataset) -> WorkSampleValidationReport:
    results = [validate_work_sample(item) for item in dataset]
    num_passed = sum(1 for result in results if result.passed)
    num_failed = len(results) - num_passed
    return WorkSampleValidationReport(
        dataset_name=dataset.name,
        num_items=len(results),
        num_passed=num_passed,
        num_failed=num_failed,
        results=results,
    )


def render_work_sample_report_markdown(report: WorkSampleValidationReport) -> str:
    lines = [
        f"# Work Sample Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Input | Pass | Profile | Route | Clarify | Mismatch |",
        "|---|---:|---|---|---:|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {input} | {passed} | {profile} | {route} | {clarify} | {mismatch} |".format(
                input=_escape_pipe(snapshot.input[:80]),
                passed="yes" if result.passed else "no",
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                route=_escape_pipe(snapshot.effective_route_hint or "-"),
                clarify="yes" if snapshot.strategy_clarify_required else "no",
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_work_sample_report(report: WorkSampleValidationReport, *, out_dir: str | Path) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_work_sample_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
