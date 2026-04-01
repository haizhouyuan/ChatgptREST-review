"""Controller route parity validation for canonical planning/research contexts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.advisor.ask_contract import normalize_ask_contract
from chatgptrest.advisor.ask_strategist import build_strategy_plan
from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import build_task_intake_spec, task_intake_to_contract_seed
from chatgptrest.controller.engine import ControllerEngine
from chatgptrest.eval.datasets import EvalDataset, EvalItem


_EXPECTED_FIELD_MAP = {
    "expected_profile": "scenario_pack_profile",
    "expected_strategy_route_hint": "strategy_route_hint",
    "expected_controller_route": "controller_route",
    "expected_execution_kind": "controller_execution_kind",
    "expected_objective_kind": "controller_objective_kind",
    "expected_controller_route_parity": "route_parity",
}


class _RuntimeState(dict[str, Any]):
    """Compatibility shim for ControllerEngine state and advisor graph service lookup."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - mirrors normal attribute lookup
            raise AttributeError(name) from exc


@dataclass
class ControllerRouteParitySnapshot:
    input: str
    source: str
    ingress_lane: str
    scenario: str
    output_shape: str
    scenario_pack_profile: str = ""
    scenario_pack_route_hint: str = ""
    scenario_pack_execution_preference: str = ""
    contract_task_template: str = ""
    strategy_route_hint: str = ""
    strategy_clarify_required: bool = False
    controller_route: str = ""
    controller_executor_lane: str = ""
    controller_execution_kind: str = ""
    controller_objective_kind: str = ""
    route_parity: bool = False
    kb_used: bool = False
    kb_hit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControllerRouteParityValidationResult:
    item_input: str
    passed: bool
    snapshot: ControllerRouteParitySnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class ControllerRouteParityValidationReport:
    dataset_name: str
    num_items: int
    num_passed: int
    num_failed: int
    results: list[ControllerRouteParityValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "num_items": self.num_items,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def snapshot_controller_route_parity_sample(
    item: EvalItem,
    *,
    trace_prefix: str = "controller-route-parity",
) -> ControllerRouteParitySnapshot:
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
    session_id = str(meta.get("session_id") or f"controller-{abs(hash((item.input, 's'))) % 1_000_000}")
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
    context["ask_contract"] = contract.to_dict()
    context["ask_strategy"] = strategy.to_dict()

    engine = ControllerEngine(
        _RuntimeState(
            cc_native=object(),
            kb_hub=None,
            llm_connector=None,
            evomap_observer=None,
            kb_registry=None,
            memory=None,
            event_bus=None,
            model_router=None,
            mcp_bridge=None,
            cc_executor=None,
            policy_engine=None,
            routing_fabric=None,
            evomap_knowledge_db=None,
            writeback_service=None,
        )
    )
    intent_hint = _derive_intent_hint(goal_hint=goal_hint)
    route_plan = engine._plan_async_route(
        question=item.input,
        trace_id=trace_id,
        intent_hint=intent_hint,
        session_id=session_id,
        account_id="",
        thread_id="",
        agent_id="",
        role_id="",
        stable_context=context,
    )
    execution_kind = engine._resolve_execution_kind(route_plan=route_plan, stable_context=context)
    objective_plan = engine._build_objective_plan(
        question=item.input,
        route_plan=route_plan,
        intent_hint=intent_hint,
        stable_context=context,
    )
    pack_dict = scenario_pack.to_dict() if scenario_pack is not None else {}
    controller_route = str(route_plan.get("route") or "")
    strategy_route = str(strategy.route_hint or "")

    return ControllerRouteParitySnapshot(
        input=item.input,
        source=task_intake.source,
        ingress_lane=task_intake.ingress_lane,
        scenario=task_intake.scenario,
        output_shape=task_intake.output_shape,
        scenario_pack_profile=str(pack_dict.get("profile") or ""),
        scenario_pack_route_hint=str(pack_dict.get("route_hint") or ""),
        scenario_pack_execution_preference=str(pack_dict.get("execution_preference") or ""),
        contract_task_template=str(contract.task_template or ""),
        strategy_route_hint=strategy_route,
        strategy_clarify_required=bool(strategy.clarify_required),
        controller_route=controller_route,
        controller_executor_lane=str(route_plan.get("executor_lane") or ""),
        controller_execution_kind=str(execution_kind or ""),
        controller_objective_kind=str(objective_plan.get("objective_kind") or ""),
        route_parity=(controller_route == strategy_route),
        kb_used=bool(route_plan.get("kb_used") or False),
        kb_hit_count=int(route_plan.get("kb_hit_count") or 0),
    )


def validate_controller_route_parity_sample(item: EvalItem) -> ControllerRouteParityValidationResult:
    snapshot = snapshot_controller_route_parity_sample(item)
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
    return ControllerRouteParityValidationResult(
        item_input=item.input,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_controller_route_parity_validation(
    dataset: EvalDataset,
) -> ControllerRouteParityValidationReport:
    results = [validate_controller_route_parity_sample(item) for item in dataset]
    num_passed = sum(1 for result in results if result.passed)
    num_failed = len(results) - num_passed
    return ControllerRouteParityValidationReport(
        dataset_name=dataset.name,
        num_items=len(results),
        num_passed=num_passed,
        num_failed=num_failed,
        results=results,
    )


def render_controller_route_parity_report_markdown(
    report: ControllerRouteParityValidationReport,
) -> str:
    lines = [
        f"# Controller Route Parity Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Input | Pass | Profile | Strategy Route | Controller Route | Exec Kind | Parity | Mismatch |",
        "|---|---:|---|---|---|---|---:|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {input} | {passed} | {profile} | {strategy} | {controller} | {kind} | {parity} | {mismatch} |".format(
                input=_escape_pipe(snapshot.input[:80]),
                passed="yes" if result.passed else "no",
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                strategy=_escape_pipe(snapshot.strategy_route_hint or "-"),
                controller=_escape_pipe(snapshot.controller_route or "-"),
                kind=_escape_pipe(snapshot.controller_execution_kind or "-"),
                parity="yes" if snapshot.route_parity else "no",
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_controller_route_parity_report(
    report: ControllerRouteParityValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_controller_route_parity_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _derive_intent_hint(*, goal_hint: str) -> str:
    hint = str(goal_hint or "").strip().lower()
    if hint in {"code_review", "research"}:
        return "research"
    if hint == "report":
        return "report"
    if hint == "quick":
        return "quick"
    return ""


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
