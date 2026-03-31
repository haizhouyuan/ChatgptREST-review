"""Multi-ingress business work-sample validation for planning/research asks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from chatgptrest.advisor.ask_contract import normalize_ask_contract
from chatgptrest.advisor.ask_strategist import build_strategy_plan
from chatgptrest.advisor.feishu_ws_gateway import _build_advisor_api_payload
from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.standard_entry import normalize_request
from chatgptrest.advisor.task_intake import (
    TaskIntakeSpec,
    build_task_intake_spec,
    summarize_task_intake,
    task_intake_to_contract_seed,
)
from chatgptrest.api.routes_consult import _select_consult_models, summarize_scenario_pack
from chatgptrest.eval.datasets import EvalDataset, EvalItem


_DEFAULT_INGRESS_PROFILES = (
    "agent_v3_rest",
    "standard_entry_codex",
    "feishu_ws",
    "consult_rest",
)

_EXPECTED_FIELD_MAP = {
    "expected_source": "source",
    "expected_ingress_lane": "ingress_lane",
    "expected_scenario": "scenario",
    "expected_output_shape": "output_shape",
    "expected_profile": "scenario_pack_profile",
    "expected_route_hint": "effective_route_hint",
    "expected_execution_preference": "scenario_pack_execution_preference",
    "expected_clarify_required": "strategy_clarify_required",
    "expected_task_template": "contract_task_template",
    "expected_acceptance_profile": "acceptance_profile",
    "expected_consult_models": "consult_models",
}

_EXPECTED_FIELDS_BY_INGRESS = {
    "agent_v3_rest": set(_EXPECTED_FIELD_MAP.keys()) - {"expected_consult_models"},
    "standard_entry_codex": set(_EXPECTED_FIELD_MAP.keys()) - {"expected_consult_models"},
    "feishu_ws": set(_EXPECTED_FIELD_MAP.keys()) - {"expected_consult_models"},
    "consult_rest": {
        "expected_source",
        "expected_ingress_lane",
        "expected_scenario",
        "expected_output_shape",
        "expected_profile",
        "expected_route_hint",
        "expected_execution_preference",
        "expected_consult_models",
    },
}


@dataclass
class MultiIngressWorkSampleSnapshot:
    ingress_profile: str
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
    consult_models: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MultiIngressWorkSampleValidationResult:
    item_input: str
    ingress_profile: str
    passed: bool
    snapshot: MultiIngressWorkSampleSnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "ingress_profile": self.ingress_profile,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class MultiIngressWorkSampleValidationReport:
    dataset_name: str
    ingress_profiles: list[str]
    num_items: int
    num_cases: int
    num_passed: int
    num_failed: int
    results: list[MultiIngressWorkSampleValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "ingress_profiles": list(self.ingress_profiles),
            "num_items": self.num_items,
            "num_cases": self.num_cases,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def snapshot_multi_ingress_work_sample(
    item: EvalItem,
    *,
    ingress_profile: str,
    trace_prefix: str = "multi-ingress-work-sample",
) -> MultiIngressWorkSampleSnapshot:
    meta = dict(item.metadata or {})
    if ingress_profile == "agent_v3_rest":
        return _snapshot_agent_v3_rest(item, meta=meta, trace_prefix=trace_prefix)
    if ingress_profile == "standard_entry_codex":
        return _snapshot_standard_entry_codex(item, meta=meta, trace_prefix=trace_prefix)
    if ingress_profile == "feishu_ws":
        return _snapshot_feishu_ws(item, meta=meta)
    if ingress_profile == "consult_rest":
        return _snapshot_consult_rest(item, meta=meta, trace_prefix=trace_prefix)
    raise ValueError(f"unsupported ingress profile: {ingress_profile}")


def validate_multi_ingress_work_sample(
    item: EvalItem,
    *,
    ingress_profile: str,
) -> MultiIngressWorkSampleValidationResult:
    snapshot = snapshot_multi_ingress_work_sample(item, ingress_profile=ingress_profile)
    expected = _expected_fields_for_ingress(item, ingress_profile=ingress_profile)
    snapshot_dict = snapshot.to_dict()
    mismatches: dict[str, dict[str, Any]] = {}

    for expected_key, snapshot_key in _EXPECTED_FIELD_MAP.items():
        if expected_key not in expected:
            continue
        actual = snapshot_dict.get(snapshot_key)
        wanted = expected[expected_key]
        if actual != wanted:
            mismatches[expected_key] = {"expected": wanted, "actual": actual}

    return MultiIngressWorkSampleValidationResult(
        item_input=item.input,
        ingress_profile=ingress_profile,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_multi_ingress_work_sample_validation(
    dataset: EvalDataset,
    *,
    ingress_profiles: list[str] | tuple[str, ...] | None = None,
) -> MultiIngressWorkSampleValidationReport:
    active_profiles = list(ingress_profiles or _DEFAULT_INGRESS_PROFILES)
    results = [
        validate_multi_ingress_work_sample(item, ingress_profile=ingress_profile)
        for item in dataset
        for ingress_profile in active_profiles
    ]
    num_passed = sum(1 for result in results if result.passed)
    num_failed = len(results) - num_passed
    return MultiIngressWorkSampleValidationReport(
        dataset_name=dataset.name,
        ingress_profiles=active_profiles,
        num_items=len(dataset),
        num_cases=len(results),
        num_passed=num_passed,
        num_failed=num_failed,
        results=results,
    )


def render_multi_ingress_work_sample_report_markdown(
    report: MultiIngressWorkSampleValidationReport,
) -> str:
    lines = [
        f"# Multi-Ingress Work Sample Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- ingress_profiles: {', '.join(report.ingress_profiles)}",
        f"- cases: {report.num_cases}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Ingress | Input | Pass | Profile | Route | Models | Mismatch |",
        "|---|---|---:|---|---|---|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        models = ", ".join(snapshot.consult_models) if snapshot.consult_models else "-"
        lines.append(
            "| {ingress} | {input} | {passed} | {profile} | {route} | {models} | {mismatch} |".format(
                ingress=_escape_pipe(snapshot.ingress_profile),
                input=_escape_pipe(snapshot.input[:80]),
                passed="yes" if result.passed else "no",
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                route=_escape_pipe(snapshot.effective_route_hint or "-"),
                models=_escape_pipe(models),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_multi_ingress_work_sample_report(
    report: MultiIngressWorkSampleValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_multi_ingress_work_sample_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _snapshot_agent_v3_rest(
    item: EvalItem,
    *,
    meta: Mapping[str, Any],
    trace_prefix: str,
) -> MultiIngressWorkSampleSnapshot:
    context = dict(meta.get("context") or {})
    task_intake = build_task_intake_spec(
        ingress_lane="agent_v3",
        default_source="rest",
        raw_source=str(meta.get("source") or ""),
        raw_task_intake=_maybe_mapping(meta.get("task_intake")),
        raw_contract=_maybe_mapping(meta.get("contract")),
        message=item.input,
        goal_hint=str(meta.get("goal_hint") or ""),
        trace_id=str(meta.get("trace_id") or f"{trace_prefix}:{abs(hash((item.input, 'agent_v3'))) % 1_000_000}"),
        session_id=str(meta.get("session_id") or f"session-{abs(hash((item.input, 'agent_v3_s'))) % 1_000_000}"),
        user_id=str(meta.get("user_id") or "eval-user"),
        account_id=str(meta.get("account_id") or ""),
        thread_id=str(meta.get("thread_id") or ""),
        agent_id=str(meta.get("agent_id") or ""),
        role_id=str(meta.get("role_id") or ""),
        context=context,
        attachments=list(meta.get("attachments") or []),
        client_name=str(meta.get("client_name") or ""),
    )
    return _semantic_snapshot_from_task_intake(
        item,
        ingress_profile="agent_v3_rest",
        task_intake=task_intake,
        goal_hint=str(meta.get("goal_hint") or ""),
        raw_contract=_maybe_mapping(meta.get("contract")),
        context=context,
    )


def _snapshot_standard_entry_codex(
    item: EvalItem,
    *,
    meta: Mapping[str, Any],
    trace_prefix: str,
) -> MultiIngressWorkSampleSnapshot:
    metadata = {
        "goal_hint": str(meta.get("goal_hint") or ""),
        "intent_hint": str(meta.get("intent_hint") or ""),
        "task_intake": _maybe_mapping(meta.get("task_intake")),
        "trace_id": str(meta.get("trace_id") or f"{trace_prefix}:{abs(hash((item.input, 'std'))) % 1_000_000}"),
        "session_id": str(meta.get("session_id") or f"session-{abs(hash((item.input, 'std_s'))) % 1_000_000}"),
        "user_id": str(meta.get("user_id") or "eval-user"),
        "account_id": str(meta.get("account_id") or ""),
        "thread_id": str(meta.get("thread_id") or ""),
        "agent_id": str(meta.get("agent_id") or ""),
        "role_id": str(meta.get("role_id") or ""),
        "client_name": str(meta.get("client_name") or "work-sample-validation"),
    }
    context = dict(meta.get("context") or {})
    metadata.update(context)
    request = normalize_request(
        item.input,
        source="codex",
        target_agent="main",
        preset="auto",
        file_paths=list(meta.get("attachments") or []),
        metadata=metadata,
    )
    if request.task_intake is None:
        raise RuntimeError("standard entry failed to build task intake")
    return _semantic_snapshot_from_task_intake(
        item,
        ingress_profile="standard_entry_codex",
        task_intake=request.task_intake,
        goal_hint=str(meta.get("goal_hint") or ""),
        raw_contract=_maybe_mapping(meta.get("contract")),
        context=request.task_intake.context,
    )


def _snapshot_feishu_ws(
    item: EvalItem,
    *,
    meta: Mapping[str, Any],
) -> MultiIngressWorkSampleSnapshot:
    payload = _build_advisor_api_payload(
        chat_id=str(meta.get("feishu_chat_id") or "eval-chat"),
        message_id=str(meta.get("feishu_message_id") or f"msg-{abs(hash(item.input)) % 1_000_000}"),
        text=item.input,
        user_id=str(meta.get("feishu_user_id") or "feishu-eval-user"),
    )
    task_intake = TaskIntakeSpec(**dict(payload["task_intake"]))
    return _semantic_snapshot_from_task_intake(
        item,
        ingress_profile="feishu_ws",
        task_intake=task_intake,
        goal_hint="",
        raw_contract=_maybe_mapping(meta.get("contract")),
        context=task_intake.context,
    )


def _snapshot_consult_rest(
    item: EvalItem,
    *,
    meta: Mapping[str, Any],
    trace_prefix: str,
) -> MultiIngressWorkSampleSnapshot:
    context = dict(meta.get("context") or {})
    task_intake = build_task_intake_spec(
        ingress_lane="other",
        default_source="rest",
        raw_source=str(meta.get("source") or "rest"),
        raw_task_intake=_maybe_mapping(meta.get("task_intake")),
        raw_contract=_maybe_mapping(meta.get("contract")),
        question=item.input,
        goal_hint=str(meta.get("goal_hint") or ""),
        intent_hint=str(meta.get("intent_hint") or ""),
        trace_id=str(meta.get("trace_id") or f"{trace_prefix}:{abs(hash((item.input, 'consult'))) % 1_000_000}"),
        session_id=str(meta.get("session_id") or f"session-{abs(hash((item.input, 'consult_s'))) % 1_000_000}"),
        user_id=str(meta.get("user_id") or "eval-user"),
        account_id=str(meta.get("account_id") or ""),
        thread_id=str(meta.get("thread_id") or ""),
        agent_id=str(meta.get("agent_id") or ""),
        role_id=str(meta.get("role_id") or ""),
        context=context,
        attachments=list(meta.get("attachments") or []),
        client_name=str(meta.get("client_name") or ""),
    )
    scenario_pack = resolve_scenario_pack(
        task_intake,
        goal_hint=str(meta.get("goal_hint") or ""),
        context=context,
    )
    if scenario_pack is not None:
        task_intake = apply_scenario_pack(task_intake, scenario_pack)
    task_intake_summary = summarize_task_intake(task_intake)
    scenario_pack_summary = summarize_scenario_pack(scenario_pack) or {}
    consult_models = _select_consult_models(
        explicit_models=None,
        mode="",
        task_intake_summary=task_intake_summary,
        scenario_pack_summary=scenario_pack_summary,
    )
    return _semantic_snapshot_from_task_intake(
        item,
        ingress_profile="consult_rest",
        task_intake=task_intake,
        goal_hint=str(meta.get("goal_hint") or ""),
        raw_contract=_maybe_mapping(meta.get("contract")),
        context=context,
        precomputed_pack=scenario_pack_summary,
        consult_models=consult_models,
    )


def _semantic_snapshot_from_task_intake(
    item: EvalItem,
    *,
    ingress_profile: str,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    raw_contract: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
    precomputed_pack: Mapping[str, Any] | None = None,
    consult_models: list[str] | None = None,
) -> MultiIngressWorkSampleSnapshot:
    context_dict = dict(context or task_intake.context or {})
    pack_dict: dict[str, Any] = {}
    if precomputed_pack is not None:
        pack_dict = dict(precomputed_pack)
    else:
        scenario_pack = resolve_scenario_pack(task_intake, goal_hint=goal_hint, context=context_dict)
        if scenario_pack is not None:
            task_intake = apply_scenario_pack(task_intake, scenario_pack)
            pack_dict = scenario_pack.to_dict()
    if pack_dict:
        context_dict["scenario_pack"] = dict(pack_dict)
    context_dict["task_intake"] = task_intake.to_dict()

    merged_contract = task_intake_to_contract_seed(task_intake)
    merged_contract.update(dict(raw_contract or {}))
    contract, _ = normalize_ask_contract(
        message=item.input,
        raw_contract=merged_contract,
        goal_hint=goal_hint,
        context=context_dict,
    )
    strategy = build_strategy_plan(
        message=item.input,
        contract=contract,
        goal_hint=goal_hint,
        context=context_dict,
    )
    return MultiIngressWorkSampleSnapshot(
        ingress_profile=ingress_profile,
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
        consult_models=list(consult_models or []),
    )


def _expected_fields_for_ingress(item: EvalItem, *, ingress_profile: str) -> dict[str, Any]:
    meta = dict(item.metadata or {})
    allowed_fields = _EXPECTED_FIELDS_BY_INGRESS.get(ingress_profile, set(_EXPECTED_FIELD_MAP.keys()))
    expected = {
        key: value
        for key, value in meta.items()
        if key in _EXPECTED_FIELD_MAP and key in allowed_fields
    }
    ingress_expectations = dict(meta.get("ingress_expectations") or {})
    expected.update(
        {
            key: value
            for key, value in dict(ingress_expectations.get(ingress_profile) or {}).items()
            if key in allowed_fields
        }
    )
    return expected


def _maybe_mapping(value: Any) -> Mapping[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
