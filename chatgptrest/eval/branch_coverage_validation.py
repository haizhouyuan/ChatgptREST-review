"""Phase 11 branch coverage validation across public-route and controller surfaces."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from chatgptrest.advisor.ask_contract import normalize_ask_contract
from chatgptrest.advisor.ask_strategist import build_strategy_plan
from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import build_task_intake_spec, task_intake_to_contract_seed
from chatgptrest.controller.engine import ControllerEngine
from chatgptrest.eval.agent_v3_route_work_sample_validation import snapshot_agent_v3_route_work_sample
from chatgptrest.eval.datasets import EvalDataset, EvalItem


_EXPECTED_FIELD_MAP = {
    "expected_validation_surface": "validation_surface",
    "expected_status": "response_status",
    "expected_route": "route",
    "expected_controller_called": "controller_called",
    "expected_execution_kind": "controller_execution_kind",
    "expected_objective_kind": "controller_objective_kind",
    "expected_kb_used": "kb_used",
    "expected_provider": "provider",
    "expected_profile": "scenario_pack_profile",
}


class _RuntimeState(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(name) from exc


@dataclass
class BranchCoverageSnapshot:
    case_type: str
    validation_surface: str
    input: str
    response_status: str = ""
    route: str = ""
    provider: str = ""
    controller_called: bool = False
    controller_execution_kind: str = ""
    controller_objective_kind: str = ""
    kb_used: bool = False
    scenario_pack_profile: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BranchCoverageValidationResult:
    item_input: str
    passed: bool
    snapshot: BranchCoverageSnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class BranchCoverageValidationReport:
    dataset_name: str
    num_items: int
    num_passed: int
    num_failed: int
    results: list[BranchCoverageValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "num_items": self.num_items,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def snapshot_branch_coverage_sample(item: EvalItem) -> BranchCoverageSnapshot:
    meta = dict(item.metadata or {})
    case_type = str(meta.get("case_type") or "").strip()
    if case_type == "agent_v3_clarify":
        return _snapshot_agent_v3_clarify(item)
    if case_type == "controller_kb_direct":
        return _snapshot_controller_kb_direct(item)
    if case_type == "controller_no_pack_fallback":
        return _snapshot_controller_no_pack_fallback(item)
    if case_type == "controller_team_fallback":
        return _snapshot_controller_team_fallback(item)
    raise ValueError(f"unsupported branch coverage case_type: {case_type}")


def validate_branch_coverage_sample(item: EvalItem) -> BranchCoverageValidationResult:
    snapshot = snapshot_branch_coverage_sample(item)
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
    return BranchCoverageValidationResult(
        item_input=item.input,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_branch_coverage_validation(dataset: EvalDataset) -> BranchCoverageValidationReport:
    results = [validate_branch_coverage_sample(item) for item in dataset]
    num_passed = sum(1 for result in results if result.passed)
    num_failed = len(results) - num_passed
    return BranchCoverageValidationReport(
        dataset_name=dataset.name,
        num_items=len(results),
        num_passed=num_passed,
        num_failed=num_failed,
        results=results,
    )


def render_branch_coverage_report_markdown(report: BranchCoverageValidationReport) -> str:
    lines = [
        f"# Branch Coverage Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Case | Surface | Pass | Route | Exec Kind | KB Used | Profile | Mismatch |",
        "|---|---|---:|---|---|---:|---|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {case} | {surface} | {passed} | {route} | {kind} | {kb} | {profile} | {mismatch} |".format(
                case=_escape_pipe(snapshot.case_type),
                surface=_escape_pipe(snapshot.validation_surface),
                passed="yes" if result.passed else "no",
                route=_escape_pipe(snapshot.route or "-"),
                kind=_escape_pipe(snapshot.controller_execution_kind or "-"),
                kb="yes" if snapshot.kb_used else "no",
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_branch_coverage_report(
    report: BranchCoverageValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_branch_coverage_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _snapshot_agent_v3_clarify(item: EvalItem) -> BranchCoverageSnapshot:
    snapshot = snapshot_agent_v3_route_work_sample(item)
    return BranchCoverageSnapshot(
        case_type="agent_v3_clarify",
        validation_surface="agent_v3_public_route",
        input=item.input,
        response_status=snapshot.response_status,
        route=snapshot.response_route,
        controller_called=snapshot.controller_called,
        scenario_pack_profile=snapshot.scenario_pack_profile,
        note=snapshot.branch_taken,
    )


def _snapshot_controller_kb_direct(item: EvalItem) -> BranchCoverageSnapshot:
    meta = dict(item.metadata or {})
    with tempfile.TemporaryDirectory(prefix="phase11-kb-direct-") as tmp_dir:
        db_path = os.path.join(tmp_dir, "jobdb.sqlite3")
        artifacts_dir = os.path.join(tmp_dir, "artifacts")
        engine = ControllerEngine(_RuntimeState())

        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        "CHATGPTREST_DB_PATH": db_path,
                        "CHATGPTREST_ARTIFACTS_DIR": artifacts_dir,
                    },
                    clear=False,
                )
            )
            import chatgptrest.advisor.graph as advisor_graph

            stack.enter_context(
                patch.object(
                    advisor_graph,
                    "normalize",
                    lambda state: {"normalized_message": state["user_message"]},
                )
            )
            stack.enter_context(
                patch.object(
                    advisor_graph,
                    "kb_probe",
                    lambda state: {
                        "kb_has_answer": True,
                        "kb_answerability": 0.95,
                        "kb_top_chunks": [
                            {
                                "title": "Runbook",
                                "snippet": "先检查 API health，再检查 worker backlog。",
                                "artifact_id": "art-runbook",
                            }
                        ],
                    },
                )
            )
            stack.enter_context(
                patch.object(
                    advisor_graph,
                    "analyze_intent",
                    lambda state: {
                        "intent_top": "QUICK_QUESTION",
                        "intent_confidence": 0.9,
                        "multi_intent": False,
                        "step_count_est": 1,
                        "constraint_count": 0,
                        "open_endedness": 0.1,
                        "verification_need": False,
                        "action_required": False,
                    },
                )
            )
            stack.enter_context(
                patch.object(
                    advisor_graph,
                    "route_decision",
                    lambda state: {"selected_route": "kb_answer", "route_rationale": "phase11 kb direct"},
                )
            )

            result = engine.ask(
                question=item.input,
                trace_id="phase11-kb-direct",
                intent_hint="quick",
                role_id="",
                session_id="phase11-kb-direct",
                account_id="",
                thread_id="",
                agent_id="",
                user_id="eval-user",
                stable_context={},
                idempotency_key="phase11-kb-direct",
                request_fingerprint="phase11-kb-direct",
                timeout_seconds=30,
                max_retries=1,
                quality_threshold=0,
                request_metadata={},
                degradation=[],
                route_mapping={"quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"}},
                kb_direct_completion_allowed=lambda graph_state: True,
                kb_direct_synthesis_enabled=lambda: False,
                sanitize_context_hash="",
            )

    return BranchCoverageSnapshot(
        case_type="controller_kb_direct",
        validation_surface="controller_ask_kb_direct",
        input=item.input,
        response_status=str(result.get("status") or ""),
        route=str(result.get("route") or ""),
        provider=str(result.get("provider") or ""),
        controller_called=True,
        controller_execution_kind="kb_direct",
        controller_objective_kind="answer",
        kb_used=bool(result.get("kb_used") or False),
        note=str(result.get("route_rationale") or ""),
    )


def _snapshot_controller_no_pack_fallback(item: EvalItem) -> BranchCoverageSnapshot:
    meta = dict(item.metadata or {})
    context = dict(meta.get("context") or {})
    goal_hint = str(meta.get("goal_hint") or "")
    task_intake = build_task_intake_spec(
        ingress_lane="other",
        default_source="rest",
        raw_source="rest",
        raw_task_intake=dict(meta.get("task_intake") or {}),
        raw_contract=dict(meta.get("contract") or {}),
        message=item.input,
        goal_hint=goal_hint,
        trace_id="phase11-no-pack",
        session_id="phase11-no-pack",
        user_id="eval-user",
        context=context,
        attachments=[],
        client_name="",
    )
    scenario_pack = resolve_scenario_pack(task_intake, goal_hint=goal_hint, context=context)
    context["task_intake"] = task_intake.to_dict()
    contract_seed = task_intake_to_contract_seed(task_intake)
    contract, _ = normalize_ask_contract(
        message=item.input,
        raw_contract=contract_seed,
        goal_hint=goal_hint,
        context=context,
    )
    strategy = build_strategy_plan(
        message=item.input,
        contract=contract,
        goal_hint=goal_hint,
        context=context,
    )

    engine = ControllerEngine(_RuntimeState(cc_native=None, kb_hub=None, memory=None, event_bus=None))
    route_plan = engine._plan_async_route(
        question=item.input,
        trace_id="phase11-no-pack",
        intent_hint="",
        session_id="phase11-no-pack",
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
        intent_hint="",
        stable_context=context,
    )
    return BranchCoverageSnapshot(
        case_type="controller_no_pack_fallback",
        validation_surface="controller_plan_fallback",
        input=item.input,
        response_status="planned",
        route=str(route_plan.get("route") or ""),
        provider="controller",
        controller_called=False,
        controller_execution_kind=str(execution_kind or ""),
        controller_objective_kind=str(objective_plan.get("objective_kind") or ""),
        kb_used=bool(route_plan.get("kb_used") or False),
        scenario_pack_profile=str((scenario_pack.to_dict() if scenario_pack else {}).get("profile") or ""),
        note=str(strategy.route_hint or ""),
    )


def _snapshot_controller_team_fallback(item: EvalItem) -> BranchCoverageSnapshot:
    meta = dict(item.metadata or {})
    route_plan = dict(meta.get("route_plan") or {})
    stable_context = dict(meta.get("stable_context") or {})
    engine = ControllerEngine(_RuntimeState(cc_native=object(), kb_hub=None, memory=None, event_bus=None))
    execution_kind = engine._resolve_execution_kind(route_plan=route_plan, stable_context=stable_context)
    objective_plan = engine._build_objective_plan(
        question=item.input,
        route_plan=route_plan,
        intent_hint=str(meta.get("intent_hint") or ""),
        stable_context=stable_context,
    )
    return BranchCoverageSnapshot(
        case_type="controller_team_fallback",
        validation_surface="controller_execution_fallback",
        input=item.input,
        response_status="planned",
        route=str(route_plan.get("route") or ""),
        provider=("team_control_plane" if str(execution_kind or "") == "team" else "controller"),
        controller_called=False,
        controller_execution_kind=str(execution_kind or ""),
        controller_objective_kind=str(objective_plan.get("objective_kind") or ""),
        kb_used=False,
        scenario_pack_profile=str(dict(stable_context.get("scenario_pack") or {}).get("profile") or ""),
        note=str(route_plan.get("executor_lane") or ""),
    )


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
