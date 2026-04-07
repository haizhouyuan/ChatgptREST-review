"""Route-level business work-sample validation for /v3/agent/turn."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.eval.datasets import EvalDataset, EvalItem


_EXPECTED_FIELD_MAP = {
    "expected_status": "response_status",
    "expected_response_route": "response_route",
    "expected_source": "source",
    "expected_ingress_lane": "ingress_lane",
    "expected_scenario": "scenario",
    "expected_output_shape": "output_shape",
    "expected_profile": "scenario_pack_profile",
    "expected_route_hint": "strategy_route_hint",
    "expected_execution_preference": "scenario_pack_execution_preference",
    "expected_clarify_required": "strategy_clarify_required",
    "expected_task_template": "contract_task_template",
    "expected_acceptance_profile": "acceptance_profile",
    "expected_controller_called": "controller_called",
}


@dataclass
class AgentV3RouteWorkSampleSnapshot:
    input: str
    http_status: int
    response_status: str
    response_route: str
    response_error: str = ""
    source: str = ""
    ingress_lane: str = ""
    scenario: str = ""
    output_shape: str = ""
    acceptance_profile: str = ""
    min_evidence_items: int = 0
    scenario_pack_profile: str = ""
    scenario_pack_route_hint: str = ""
    scenario_pack_execution_preference: str = ""
    contract_task_template: str = ""
    contract_risk_class: str = ""
    strategy_route_hint: str = ""
    strategy_clarify_required: bool = False
    strategy_clarify_question_count: int = 0
    controller_called: bool = False
    controller_route: str = ""
    branch_taken: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentV3RouteWorkSampleValidationResult:
    item_input: str
    passed: bool
    snapshot: AgentV3RouteWorkSampleSnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class AgentV3RouteWorkSampleValidationReport:
    dataset_name: str
    num_items: int
    num_passed: int
    num_failed: int
    results: list[AgentV3RouteWorkSampleValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "num_items": self.num_items,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def snapshot_agent_v3_route_work_sample(
    item: EvalItem,
    *,
    trace_prefix: str = "agent-v3-route-work-sample",
) -> AgentV3RouteWorkSampleSnapshot:
    meta = dict(item.metadata or {})
    body = _build_request_body(item, meta=meta, trace_prefix=trace_prefix)
    captured: dict[str, Any] = {}

    original_build_strategy_plan = routes_agent_v3.build_strategy_plan

    def _wrapped_build_strategy_plan(*args, **kwargs):
        plan = original_build_strategy_plan(*args, **kwargs)
        context = _maybe_mapping(kwargs.get("context"))
        contract = kwargs.get("contract")
        captured["task_intake"] = _maybe_mapping(context.get("task_intake"))
        captured["scenario_pack"] = _maybe_mapping(context.get("scenario_pack"))
        captured["contract"] = contract.to_dict() if hasattr(contract, "to_dict") else _maybe_mapping(contract)
        captured["strategy"] = plan.to_dict() if hasattr(plan, "to_dict") else _maybe_mapping(plan)
        return plan

    class _FakeController:
        def __init__(self, _state: object) -> None:
            pass

        def ask(self, **kwargs):
            captured["controller_kwargs"] = kwargs
            captured["branch_taken"] = "controller"
            stable_context = _maybe_mapping(kwargs.get("stable_context"))
            strategy = _maybe_mapping(stable_context.get("ask_strategy"))
            route = str(strategy.get("route_hint") or "quick_ask")
            return {
                "run_id": f"route-run-{abs(hash((item.input, route))) % 1_000_000}",
                "job_id": f"route-job-{abs(hash((item.input, route, 'job'))) % 1_000_000}",
                "route": route,
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": f"{route} answer",
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "unused"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    def _submit_direct_job(**kwargs):
        captured["branch_taken"] = "direct_job"
        captured["direct_job_kwargs"] = kwargs
        return "job-unexpected"

    def _wait_for_job_completion(**kwargs):
        return {
            "job_id": str(kwargs.get("job_id") or "job-unexpected"),
            "job_status": "completed",
            "agent_status": "completed",
            "answer": "unexpected direct answer",
            "conversation_url": "https://example.invalid/job-unexpected",
        }

    def _submit_consultation(**kwargs):
        captured["branch_taken"] = "consult"
        captured["consult_kwargs"] = kwargs
        return {
            "consultation_id": "cons-unexpected",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
        }

    def _wait_for_consultation_completion(**kwargs):
        return {
            "consultation_id": str(kwargs.get("consultation_id") or "cons-unexpected"),
            "status": "completed",
            "agent_status": "completed",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
            "answer": "unexpected consult answer",
        }

    with tempfile.TemporaryDirectory(prefix="phase9-agent-sessions-") as session_dir:
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        "OPENMIND_API_KEY": "test-openmind-key",
                        "OPENMIND_AUTH_MODE": "strict",
                        "CHATGPTREST_AGENT_SESSION_DIR": session_dir,
                    },
                    clear=False,
                )
            )
            stack.enter_context(patch.object(routes_agent_v3, "_advisor_runtime", lambda: {}))
            stack.enter_context(patch.object(routes_agent_v3, "ControllerEngine", _FakeController))
            stack.enter_context(patch.object(routes_agent_v3, "build_strategy_plan", _wrapped_build_strategy_plan))
            stack.enter_context(patch.object(routes_agent_v3, "_emit_runtime_event", lambda *args, **kwargs: None))
            stack.enter_context(patch.object(routes_agent_v3, "_submit_direct_job", _submit_direct_job))
            stack.enter_context(patch.object(routes_agent_v3, "_wait_for_job_completion", _wait_for_job_completion))
            stack.enter_context(patch.object(routes_agent_v3, "_submit_consultation", _submit_consultation))
            stack.enter_context(
                patch.object(
                    routes_agent_v3,
                    "_wait_for_consultation_completion",
                    _wait_for_consultation_completion,
                )
            )
            stack.enter_context(patch.object(routes_agent_v3, "_cancel_job", lambda **kwargs: None))

            app = FastAPI()
            app.include_router(routes_agent_v3.make_v3_agent_router())
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/v3/agent/turn",
                json=body,
                headers={"X-Api-Key": "test-openmind-key"},
            )

    payload = _decode_json(response)
    task_intake = _maybe_mapping(captured.get("task_intake"))
    scenario_pack = _maybe_mapping(captured.get("scenario_pack"))
    contract = _maybe_mapping(captured.get("contract"))
    strategy = _maybe_mapping(captured.get("strategy"))
    controller_kwargs = _maybe_mapping(captured.get("controller_kwargs"))
    provenance = _maybe_mapping(payload.get("provenance"))

    return AgentV3RouteWorkSampleSnapshot(
        input=item.input,
        http_status=int(response.status_code),
        response_status=str(payload.get("status") or ""),
        response_route=str(provenance.get("route") or payload.get("route") or ""),
        response_error=str(payload.get("error") or payload.get("detail") or ""),
        source=str(task_intake.get("source") or ""),
        ingress_lane=str(task_intake.get("ingress_lane") or ""),
        scenario=str(task_intake.get("scenario") or ""),
        output_shape=str(task_intake.get("output_shape") or ""),
        acceptance_profile=str(_maybe_mapping(task_intake.get("acceptance")).get("profile") or ""),
        min_evidence_items=int(_maybe_mapping(task_intake.get("acceptance")).get("min_evidence_items") or 0),
        scenario_pack_profile=str(scenario_pack.get("profile") or ""),
        scenario_pack_route_hint=str(scenario_pack.get("route_hint") or ""),
        scenario_pack_execution_preference=str(scenario_pack.get("execution_preference") or ""),
        contract_task_template=str(contract.get("task_template") or ""),
        contract_risk_class=str(contract.get("risk_class") or ""),
        strategy_route_hint=str(strategy.get("route_hint") or ""),
        strategy_clarify_required=bool(strategy.get("clarify_required") or False),
        strategy_clarify_question_count=len(list(strategy.get("clarify_questions") or [])),
        controller_called=bool(controller_kwargs),
        controller_route=str(_maybe_mapping(controller_kwargs.get("stable_context")).get("ask_strategy", {}).get("route_hint") or ""),
        branch_taken=str(captured.get("branch_taken") or ("clarify" if not controller_kwargs else "controller")),
    )


def validate_agent_v3_route_work_sample(item: EvalItem) -> AgentV3RouteWorkSampleValidationResult:
    snapshot = snapshot_agent_v3_route_work_sample(item)
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

    if snapshot.http_status != 200:
        mismatches["http_status"] = {"expected": 200, "actual": snapshot.http_status}

    if snapshot.branch_taken not in {"controller", "clarify"}:
        mismatches["branch_taken"] = {"expected": "controller|clarify", "actual": snapshot.branch_taken}

    return AgentV3RouteWorkSampleValidationResult(
        item_input=item.input,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_agent_v3_route_work_sample_validation(
    dataset: EvalDataset,
) -> AgentV3RouteWorkSampleValidationReport:
    results = [validate_agent_v3_route_work_sample(item) for item in dataset]
    num_passed = sum(1 for result in results if result.passed)
    num_failed = len(results) - num_passed
    return AgentV3RouteWorkSampleValidationReport(
        dataset_name=dataset.name,
        num_items=len(results),
        num_passed=num_passed,
        num_failed=num_failed,
        results=results,
    )


def render_agent_v3_route_work_sample_report_markdown(
    report: AgentV3RouteWorkSampleValidationReport,
) -> str:
    lines = [
        f"# Agent V3 Route Work Sample Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Input | Pass | Status | Route | Profile | Branch | Mismatch |",
        "|---|---:|---|---|---|---|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {input} | {passed} | {status} | {route} | {profile} | {branch} | {mismatch} |".format(
                input=_escape_pipe(snapshot.input[:80]),
                passed="yes" if result.passed else "no",
                status=_escape_pipe(snapshot.response_status or "-"),
                route=_escape_pipe(snapshot.response_route or "-"),
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                branch=_escape_pipe(snapshot.branch_taken or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_agent_v3_route_work_sample_report(
    report: AgentV3RouteWorkSampleValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_agent_v3_route_work_sample_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_request_body(
    item: EvalItem,
    *,
    meta: Mapping[str, Any],
    trace_prefix: str,
) -> dict[str, Any]:
    trace_id = str(meta.get("trace_id") or f"{trace_prefix}:{abs(hash(item.input)) % 1_000_000}")
    body: dict[str, Any] = {
        "message": item.input,
        "trace_id": trace_id,
    }
    goal_hint = str(meta.get("goal_hint") or "").strip()
    if goal_hint:
        body["goal_hint"] = goal_hint
    for key in (
        "task_intake",
        "contract",
        "context",
        "attachments",
        "objective",
        "decision_to_support",
        "audience",
        "constraints",
        "available_inputs",
        "missing_inputs",
        "output_shape",
        "risk_class",
        "task_template",
        "depth",
        "delivery_mode",
    ):
        if key in meta:
            body[key] = meta[key]
    body.update(dict(meta.get("body_overrides") or {}))
    return body


def _decode_json(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _maybe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
