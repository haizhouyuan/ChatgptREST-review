from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3


@dataclass
class PlanningUserReadinessCase:
    case_id: str
    message: str
    goal_hint: str
    route: str
    answer: str
    task_type: str = ""
    expected_profile: str = ""
    expected_route: str = ""
    expected_required_sections: tuple[str, ...] = ()
    account_id: str = ""
    thread_id: str = ""
    context: dict[str, Any] | None = None


@dataclass
class PlanningUserReadinessResult:
    case_id: str
    checklist: dict[str, bool]
    evidence_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "checklist": dict(self.checklist),
            "evidence_path": self.evidence_path,
        }


_PROFILE_CASES: tuple[PlanningUserReadinessCase, ...] = (
    PlanningUserReadinessCase(
        case_id="project_diagnosis_profile",
        message="请判断 Robovance 项目当前阶段、下一里程碑和主要风险",
        goal_hint="planning",
        route="funnel",
        answer=(
            "## Current Stage\n- 样件验证\n\n"
            "## Key Findings\n- 量产窗口还没锁定。\n\n"
            "## Next Milestone\n- 锁定供应链恢复窗口。\n\n"
            "## Risks\n- 恢复窗口未锁定会影响承诺。\n\n"
            "## Next Steps\n- 先补供应链确认，再推进客户承诺。\n"
        ),
        expected_profile="project_diagnosis",
        expected_route="funnel",
        expected_required_sections=("current_stage", "key_findings", "next_milestone", "risks", "next_steps"),
        account_id="acct-readiness-diag",
        thread_id="thread-readiness-diag",
    ),
    PlanningUserReadinessCase(
        case_id="research_decision_profile",
        message="请把这份调研材料转成可拍板的判断稿",
        goal_hint="research",
        route="report",
        answer=(
            "## Core Judgment\n- 可以推进，但先锁定供应链恢复窗口。\n\n"
            "## Supporting Evidence\n- 客户窗口明确，但恢复节奏仍波动。\n\n"
            "## Suggested Action\n- 先确认恢复窗口，再承诺导入节奏。\n\n"
            "## Risks\n- 若恢复窗口漂移，拍板会失真。\n\n"
            "## Next Steps\n- 补一版带恢复窗口的判断稿。\n"
        ),
        expected_profile="research_decision",
        expected_route="report",
        expected_required_sections=("core_judgment", "supporting_evidence", "suggested_action", "risks", "next_steps"),
        account_id="acct-readiness-res",
        thread_id="thread-readiness-res",
    ),
    PlanningUserReadinessCase(
        case_id="leadership_report_profile",
        message="请给我整理一版董事长汇报摘要",
        goal_hint="report",
        route="report",
        answer=(
            "## 董事长摘要\n- 当前处于样件验证阶段。\n\n"
            "## Key Updates\n- 客户窗口和内部节奏已基本对齐。\n\n"
            "## Key Risks\n- 供应链恢复窗口未锁定。\n\n"
            "## 决策请求\n- 请先拍板恢复窗口再承诺量产节奏。\n\n"
            "## Next Steps\n- 本周补一版锁定恢复窗口后的汇报。\n"
        ),
        expected_profile="leadership_report",
        expected_route="report",
        expected_required_sections=("chairman_summary", "key_updates", "key_risks", "decision_needed", "next_steps"),
        account_id="acct-readiness-rpt",
        thread_id="thread-readiness-rpt",
    ),
    PlanningUserReadinessCase(
        case_id="planning_general_profile",
        message="请整理一版业务推进方案和下一步计划",
        goal_hint="planning",
        route="funnel",
        answer=(
            "## Objective\n- 明确客户导入节奏和资源投入。\n\n"
            "## Current State\n- 需求清单齐了，但责任人还没锁定。\n\n"
            "## Recommended Plan\n- 先锁定客户导入节奏，再补资源和责任人。\n\n"
            "## Risks\n- 若责任人不清，推进节奏会漂移。\n\n"
            "## Next Steps\n- 这周补责任人与周节奏。\n"
        ),
        expected_profile="planning_general",
        expected_route="funnel",
        expected_required_sections=("objective", "current_state", "recommended_plan", "risks", "next_steps"),
        account_id="acct-readiness-plan",
        thread_id="thread-readiness-plan",
    ),
    PlanningUserReadinessCase(
        case_id="meeting_summary_attachment_profile",
        message="请先帮我整理一下今天材料",
        goal_hint="planning",
        route="report",
        answer=(
            "## Meeting Context\n- 今天是项目同步会，重点讨论恢复窗口。\n\n"
            "## Key Points\n- 客户节奏已明确，但供应链恢复窗口待锁定。\n\n"
            "## Decisions\n- 先补恢复窗口，再对外承诺量产节奏。\n\n"
            "## Action Items\n- 供应链负责人本周补恢复窗口。\n\n"
            "## Open Questions\n- 恢复窗口是否会影响客户导入批次。\n"
        ),
        expected_profile="meeting_summary",
        expected_route="report",
        expected_required_sections=("meeting_context", "key_points", "decisions", "action_items", "open_questions"),
        account_id="acct-readiness-meeting",
        thread_id="thread-readiness-meeting",
        context={
            "attachment_inventory": {
                "files": ["team_sync_transcript.md"],
                "notes": ["meeting transcript uploaded"],
                "preflight": {
                    "planning_roles": ["meeting_transcript"],
                    "material_families": ["document"],
                },
                "items": [
                    {
                        "planning_role": "meeting_transcript",
                        "family": "document",
                        "path": "team_sync_transcript.md",
                        "handling": "direct_review",
                    }
                ],
            }
        },
    ),
)

_CONTINUITY_CASE = PlanningUserReadinessCase(
    case_id="same_task_continuity",
    message="请给我做一份未来两个季度的人力规划方案",
    goal_hint="planning",
    route="funnel",
    answer=(
        "## Staffing Goal\n- 支撑未来两个季度业务导入。\n\n"
        "## Current State\n- PM 与采购存在缺口。\n\n"
        "## Demand Drivers\n- 客户导入节奏要求前置补岗。\n\n"
        "## Headcount Plan\n- PM 1，采购 1。\n\n"
        "## Hiring Sequence\n- 先补 PM，再补采购。\n\n"
        "## Risks\n- 若预算未锁定，招聘节奏会后移。\n"
    ),
    task_type="workforce_planning",
    expected_profile="workforce_planning",
    expected_route="funnel",
    expected_required_sections=("staffing_goal", "current_state", "demand_drivers", "headcount_plan", "hiring_sequence", "risks"),
    account_id="acct-readiness-cont",
    thread_id="thread-readiness-cont",
)

_CONTINUITY_CONTINUE_ANSWER = (
    "## Staffing Goal\n- 继续保持两个季度导入节奏。\n\n"
    "## Current State\n- 预算结论已补齐。\n\n"
    "## Demand Drivers\n- 客户导入节奏维持不变。\n\n"
    "## Headcount Plan\n- 继续补质量岗位 1。\n\n"
    "## Hiring Sequence\n- PM -> 采购 -> 质量。\n\n"
    "## Risks\n- 若质量岗位延迟，交付节奏会拖慢。\n"
)

_REPO_BACKED_CASE = PlanningUserReadinessCase(
    case_id="repo_backed_implementation_defaults_to_coding_agent",
    message="请基于当前仓库给我一份实施计划，覆盖目标、计划、依赖、风险和验证。",
    goal_hint="planning",
    route="funnel",
    answer=(
        "## Goal\n- 冻结一版可交付的仓库实施计划。\n\n"
        "## Plan\n- 先梳理现状，再冻结改动批次，最后跑验收。\n\n"
        "## Dependencies\n- 依赖当前仓库上下文和 acceptance gate。\n\n"
        "## Risks\n- 若执行车道漂移，结果会失去可用性。\n\n"
        "## Validation\n- 复跑 acceptance 并确认同一 task 可继续。\n"
    ),
    task_type="implementation_plan",
    expected_profile="implementation_plan",
    expected_route="funnel",
    expected_required_sections=("goal", "plan", "dependencies", "risks", "validation"),
    account_id="acct-readiness-repo",
    thread_id="thread-readiness-repo",
    context={"github_repo": "openai/openai-python"},
)

_THIN_FAIL_CLOSED_CASE = PlanningUserReadinessCase(
    case_id="thin_full_planning_fail_closed",
    message="请给我一份实施计划，覆盖目标、计划、依赖、风险和验证。",
    goal_hint="planning",
    route="funnel",
    answer="先推进一版方案，后面再细化。",
    task_type="implementation_plan",
    expected_profile="implementation_plan",
    expected_route="funnel",
    expected_required_sections=("goal", "plan", "dependencies", "risks", "validation"),
    account_id="acct-readiness-thin",
    thread_id="thread-readiness-thin",
)

_PARTIAL_FAIL_CLOSED_CASE = PlanningUserReadinessCase(
    case_id="missing_sections_fail_closed",
    message="请给我一份实施计划，覆盖目标、计划、依赖、风险和验证，但先按你理解整理现状。",
    goal_hint="planning",
    route="funnel",
    answer=(
        "## Goal\n- 冻结一版实施计划。\n\n"
        "## Plan\n- 先梳理现状，再拆批次推进。\n\n"
        "## Risks\n- 如果入口漂移，执行会变形。\n\n"
        "补充说明：这份方案已经整理了当前背景、上下游协同、节奏安排、执行假设和对外承诺边界，"
        "也同步考虑了资源限制、上线窗口、责任人切换和常见回滚场景，"
        "但配套条件与检查动作暂时还没有展开，需要后续再补。"
    ),
    task_type="implementation_plan",
    expected_profile="implementation_plan",
    expected_route="funnel",
    expected_required_sections=("goal", "plan", "dependencies", "risks", "validation"),
    account_id="acct-readiness-partial",
    thread_id="thread-readiness-partial",
)

_BRANCH_SOURCE_CASE = PlanningUserReadinessCase(
    case_id="branch_source_project_diagnosis",
    message="请判断 Robovance 项目当前阶段、下一里程碑和主要风险",
    goal_hint="planning",
    route="funnel",
    answer=(
        "## Current Stage\n- 样件验证\n\n"
        "## Key Findings\n- 恢复窗口待锁定。\n\n"
        "## Next Milestone\n- 锁定恢复窗口。\n\n"
        "## Risks\n- 客户承诺会受影响。\n\n"
        "## Next Steps\n- 先补恢复窗口结论。\n"
    ),
    task_type="project_diagnosis",
    expected_profile="project_diagnosis",
    expected_route="funnel",
    expected_required_sections=("current_stage", "key_findings", "next_milestone", "risks", "next_steps"),
    account_id="acct-readiness-branch",
    thread_id="thread-readiness-branch",
)

_BRANCH_TARGET_ANSWER = (
    "## 董事长摘要\n- 当前仍处于样件验证阶段。\n\n"
    "## Key Updates\n- 量产窗口与客户承诺需要重新对齐。\n\n"
    "## Key Risks\n- 恢复窗口未锁定会影响拍板。\n\n"
    "## 决策请求\n- 请先拍板恢复窗口，再承诺量产节奏。\n\n"
    "## Next Steps\n- 一周内补一版锁定恢复窗口后的汇报。\n"
)


def _case_map() -> dict[str, dict[str, str]]:
    payload: dict[str, dict[str, str]] = {}
    for case in (*_PROFILE_CASES, _CONTINUITY_CASE, _REPO_BACKED_CASE, _THIN_FAIL_CLOSED_CASE, _BRANCH_SOURCE_CASE):
        payload[case.message] = {"route": case.route, "answer": case.answer}
    payload[_PARTIAL_FAIL_CLOSED_CASE.message] = {"route": _PARTIAL_FAIL_CLOSED_CASE.route, "answer": _PARTIAL_FAIL_CLOSED_CASE.answer}
    payload["继续补齐这份人力规划方案的岗位动作"] = {"route": _CONTINUITY_CASE.route, "answer": _CONTINUITY_CONTINUE_ANSWER}
    payload["把同一项目诊断整理成董事长汇报摘要"] = {"route": "report", "answer": _BRANCH_TARGET_ANSWER}
    return payload


def _build_controller():
    case_by_message = _case_map()

    class _Controller:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            message = str(kwargs.get("question") or kwargs.get("message") or "").strip()
            payload = case_by_message.get(message)
            if payload is None:
                raise AssertionError(f"unexpected readiness message: {message}")
            route = str(payload["route"])
            answer = str(payload["answer"])
            return {
                "run_id": f"run-{abs(hash((message, route))) % 10_000_000}",
                "job_id": f"job-{abs(hash((route, message))) % 10_000_000}",
                "route": route,
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": answer,
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "funnel",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "done"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    return _Controller


def _post_turn(client: TestClient, *, case: PlanningUserReadinessCase, extra_context: dict[str, Any] | None = None, task_id: str = "", task_action: str = "") -> dict[str, Any]:
    context = dict(case.context or {})
    if case.task_type:
        context.setdefault("planning_task_type", case.task_type)
    if extra_context:
        context.update(extra_context)
    payload: dict[str, Any] = {
        "message": case.message,
        "goal_hint": case.goal_hint,
        "account_id": case.account_id,
        "thread_id": case.thread_id,
        "agent_id": "openclawbot",
        "role_id": "planning",
    }
    if context or task_id or task_action:
        payload["task_intake"] = {"context": context}
    if task_id:
        payload.setdefault("task_intake", {}).update({"task_id": task_id})
    if task_action:
        payload.setdefault("task_intake", {}).setdefault("context", {})["planning_task_action"] = task_action
    response = client.post("/v3/agent/turn", json=payload, headers={"X-Api-Key": "test-key"})
    return {"status_code": response.status_code, "body": response.json()}


def _get_task(client: TestClient, *, task_id: str, account_id: str, thread_id: str) -> dict[str, Any]:
    response = client.get(
        f"/v3/agent/planning/task/{task_id}",
        params={"account_id": account_id, "thread_id": thread_id},
        headers={"X-Api-Key": "test-key"},
    )
    return {"status_code": response.status_code, "body": response.json()}


def _get_session(client: TestClient, *, session_id: str) -> dict[str, Any]:
    response = client.get(f"/v3/agent/session/{session_id}", headers={"X-Api-Key": "test-key"})
    return {"status_code": response.status_code, "body": response.json()}


def export_pack(*, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results: list[PlanningUserReadinessResult] = []

    with tempfile.TemporaryDirectory(prefix="planning-user-readiness-") as runtime_root:
        runtime_dir = Path(runtime_root) / "planning_tasks_runtime"
        session_dir = Path(runtime_root) / "agent_sessions_runtime"
        env = dict(os.environ)
        env["OPENMIND_API_KEY"] = "test-key"
        env["OPENMIND_AUTH_MODE"] = "strict"
        env["OPENMIND_RATE_LIMIT"] = "1000"
        env["CHATGPTREST_PLANNING_TASK_DIR"] = str(runtime_dir.resolve())
        env["CHATGPTREST_AGENT_SESSION_DIR"] = str(session_dir.resolve())

        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(routes_agent_v3, "_advisor_runtime", lambda: {}),
            patch.object(routes_agent_v3, "ControllerEngine", _build_controller()),
        ):
            app = FastAPI()
            app.include_router(routes_agent_v3.make_v3_agent_router())
            client = TestClient(app, raise_server_exceptions=False)

            for case in _PROFILE_CASES:
                payload = _post_turn(client, case=case)
                body = dict(payload["body"])
                checklist = {
                    "request_accepted": payload["status_code"] == 200,
                    "profile_selected": str(body.get("scenario_pack", {}).get("profile") or "") == case.expected_profile,
                    "route_selected": str(body.get("scenario_pack", {}).get("route_hint") or "") == case.expected_route,
                    "required_sections_frozen": list(body.get("quality_gate", {}).get("required_sections") or []) == list(case.expected_required_sections),
                    "automatic_main_path_visible": str(body.get("control_plane", {}).get("lane_policy", {}).get("provider_resolution") or "") == "policy_default",
                    "directly_usable": bool(body.get("quality_gate", {}).get("pass")),
                    "completed_without_manual_patch": str(body.get("status") or "") == "completed",
                }
                evidence_path = out / f"{case.case_id}.json"
                evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                results.append(PlanningUserReadinessResult(case_id=case.case_id, checklist=checklist, evidence_path=str(evidence_path)))

            repo_payload = _post_turn(client, case=_REPO_BACKED_CASE)
            repo_body = dict(repo_payload["body"])
            repo_checklist = {
                "request_accepted": repo_payload["status_code"] == 200,
                "profile_selected": str(repo_body.get("scenario_pack", {}).get("profile") or "") == _REPO_BACKED_CASE.expected_profile,
                "execution_lane_is_coding_agent": str(repo_body.get("control_plane", {}).get("execution_layer", {}).get("execution_lane") or "") == "coding_agent",
                "selected_executor_is_codex": str(repo_body.get("control_plane", {}).get("execution_layer", {}).get("selected_executor") or "") == "codex",
                "automatic_default_visible": bool(repo_body.get("control_plane", {}).get("execution_layer", {}).get("automatic_default")),
                "directly_usable": bool(repo_body.get("quality_gate", {}).get("pass")),
            }
            repo_evidence = out / f"{_REPO_BACKED_CASE.case_id}.json"
            repo_evidence.write_text(json.dumps(repo_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(PlanningUserReadinessResult(case_id=_REPO_BACKED_CASE.case_id, checklist=repo_checklist, evidence_path=str(repo_evidence)))

            first = _post_turn(client, case=_CONTINUITY_CASE)
            first_body = dict(first["body"])
            continued = _post_turn(
                client,
                case=PlanningUserReadinessCase(
                    case_id="continuation_followup",
                    message="继续补齐这份人力规划方案的岗位动作",
                    goal_hint=_CONTINUITY_CASE.goal_hint,
                    route=_CONTINUITY_CASE.route,
                    answer=_CONTINUITY_CONTINUE_ANSWER,
                    task_type=_CONTINUITY_CASE.task_type,
                    expected_profile=_CONTINUITY_CASE.expected_profile,
                    expected_route=_CONTINUITY_CASE.expected_route,
                    expected_required_sections=_CONTINUITY_CASE.expected_required_sections,
                    account_id=_CONTINUITY_CASE.account_id,
                    thread_id=_CONTINUITY_CASE.thread_id,
                ),
                task_id=str(first_body.get("task_id") or ""),
                task_action="continue",
            )
            continue_body = dict(continued["body"])
            task_lookup = _get_task(
                client,
                task_id=str(first_body.get("task_id") or ""),
                account_id=_CONTINUITY_CASE.account_id,
                thread_id=_CONTINUITY_CASE.thread_id,
            )
            continuity_checklist = {
                "first_turn_completed": str(first_body.get("status") or "") == "completed",
                "automatic_main_path_visible": str(first_body.get("control_plane", {}).get("lane_policy", {}).get("provider_resolution") or "") == "policy_default",
                "continue_stays_same_task": str(continue_body.get("task_id") or "") == str(first_body.get("task_id") or ""),
                "continue_resolution_explicit": str(continue_body.get("planning_task", {}).get("resolution") or "") == "continue_explicit",
                "task_lookup_ok": task_lookup["status_code"] == 200,
                "latest_output_updated": str(task_lookup["body"].get("planning_task", {}).get("checkpoint", {}).get("latest_output") or "").strip() == _CONTINUITY_CONTINUE_ANSWER.strip(),
                "quality_gate_stays_green": bool(continue_body.get("quality_gate", {}).get("pass")),
            }
            continuity_evidence = out / f"{_CONTINUITY_CASE.case_id}.json"
            continuity_evidence.write_text(
                json.dumps({"first": first, "continue": continued, "task_lookup": task_lookup}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            results.append(PlanningUserReadinessResult(case_id=_CONTINUITY_CASE.case_id, checklist=continuity_checklist, evidence_path=str(continuity_evidence)))

            thin = _post_turn(client, case=_THIN_FAIL_CLOSED_CASE)
            thin_body = dict(thin["body"])
            thin_task_lookup = _get_task(
                client,
                task_id=str(thin_body.get("task_id") or ""),
                account_id=_THIN_FAIL_CLOSED_CASE.account_id,
                thread_id=_THIN_FAIL_CLOSED_CASE.thread_id,
            )
            thin_session_lookup = _get_session(client, session_id=str(thin_body.get("session_id") or ""))
            thin_checklist = {
                "request_accepted": thin["status_code"] == 200,
                "response_fail_closed": str(thin_body.get("status") or "") == "needs_followup",
                "repair_reason_visible": str(thin_body.get("next_action", {}).get("reason") or "") == "planning_quality_gate_failed",
                "session_truth_aligned": str(thin_session_lookup["body"].get("status") or "") == "needs_followup",
                "session_repair_visible": str(thin_session_lookup["body"].get("next_action", {}).get("reason") or "") == "planning_quality_gate_failed",
                "task_checkpoint_truth_aligned": str(thin_task_lookup["body"].get("planning_task", {}).get("checkpoint", {}).get("current_status") or "") == "needs_followup",
            }
            thin_evidence = out / f"{_THIN_FAIL_CLOSED_CASE.case_id}.json"
            thin_evidence.write_text(
                json.dumps({"turn": thin, "task_lookup": thin_task_lookup, "session_lookup": thin_session_lookup}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            results.append(PlanningUserReadinessResult(case_id=_THIN_FAIL_CLOSED_CASE.case_id, checklist=thin_checklist, evidence_path=str(thin_evidence)))

            partial = _post_turn(client, case=_PARTIAL_FAIL_CLOSED_CASE)
            partial_body = dict(partial["body"])
            partial_task_lookup = _get_task(
                client,
                task_id=str(partial_body.get("task_id") or ""),
                account_id=_PARTIAL_FAIL_CLOSED_CASE.account_id,
                thread_id=_PARTIAL_FAIL_CLOSED_CASE.thread_id,
            )
            partial_session_lookup = _get_session(client, session_id=str(partial_body.get("session_id") or ""))
            partial_checklist = {
                "request_accepted": partial["status_code"] == 200,
                "response_fail_closed": str(partial_body.get("status") or "") == "needs_followup",
                "missing_dependencies_visible": "dependencies" in list(partial_body.get("quality_gate", {}).get("missing_sections") or []),
                "missing_validation_visible": "validation" in list(partial_body.get("quality_gate", {}).get("missing_sections") or []),
                "session_truth_aligned": str(partial_session_lookup["body"].get("status") or "") == "needs_followup",
                "task_checkpoint_truth_aligned": str(partial_task_lookup["body"].get("planning_task", {}).get("checkpoint", {}).get("current_status") or "") == "needs_followup",
            }
            partial_evidence = out / f"{_PARTIAL_FAIL_CLOSED_CASE.case_id}.json"
            partial_evidence.write_text(
                json.dumps({"turn": partial, "task_lookup": partial_task_lookup, "session_lookup": partial_session_lookup}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            results.append(PlanningUserReadinessResult(case_id=_PARTIAL_FAIL_CLOSED_CASE.case_id, checklist=partial_checklist, evidence_path=str(partial_evidence)))

            branch_first = _post_turn(client, case=_BRANCH_SOURCE_CASE)
            branch_first_body = dict(branch_first["body"])
            branch_followup = _post_turn(
                client,
                case=PlanningUserReadinessCase(
                    case_id="branch_target_leadership_report",
                    message="把同一项目诊断整理成董事长汇报摘要",
                    goal_hint="report",
                    route="report",
                    answer=_BRANCH_TARGET_ANSWER,
                    task_type="leadership_report",
                    expected_profile="leadership_report",
                    expected_route="report",
                    expected_required_sections=("chairman_summary", "key_updates", "key_risks", "decision_needed", "next_steps"),
                    account_id=_BRANCH_SOURCE_CASE.account_id,
                    thread_id=_BRANCH_SOURCE_CASE.thread_id,
                ),
                task_id=str(branch_first_body.get("task_id") or ""),
                task_action="branch",
            )
            branch_body = dict(branch_followup["body"])
            branch_checklist = {
                "source_turn_completed": str(branch_first_body.get("status") or "") == "completed",
                "branch_creates_new_task": str(branch_body.get("task_id") or "") != str(branch_first_body.get("task_id") or ""),
                "branch_profile_selected": str(branch_body.get("scenario_pack", {}).get("profile") or "") == "leadership_report",
                "branch_task_type_changed": str(branch_body.get("planning_task", {}).get("task_type") or "") == "leadership_report",
                "branch_quality_gate_green": bool(branch_body.get("quality_gate", {}).get("pass")),
                "branch_prefix_ok": str(branch_body.get("task_id") or "").startswith("rpt_"),
            }
            branch_evidence = out / "branch_preserves_task_truth.json"
            branch_evidence.write_text(
                json.dumps({"source": branch_first, "branch": branch_followup}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            results.append(PlanningUserReadinessResult(case_id="branch_preserves_task_truth", checklist=branch_checklist, evidence_path=str(branch_evidence)))

    overall_pass = all(all(item.checklist.values()) for item in results)
    manifest = {
        "ok": True,
        "overall_pass": overall_pass,
        "counts": {
            "cases": len(results),
            "passed": sum(1 for item in results if all(item.checklist.values())),
            "failed": sum(1 for item in results if not all(item.checklist.values())),
        },
        "user_effect_scope": {
            "entry_auto_understands_request": True,
            "attachment_signals_auto_understood": True,
            "stable_planning_profiles_auto_select_main_path": True,
            "same_task_continuity": True,
            "direct_output_usable": True,
            "repo_backed_implementation_auto_selects_coding_agent": True,
            "thin_outputs_fail_closed": True,
            "missing_required_sections_fail_closed": True,
            "session_task_truth_alignment": True,
            "branch_without_corrupting_original_task": True,
        },
        "results": [item.to_dict() for item in results],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = out / "report_v1.md"
    report_path.write_text(_render_report(manifest), encoding="utf-8")
    return manifest


def _render_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# Planning User Readiness Acceptance Pack",
        "",
        f"- overall_pass: `{manifest['overall_pass']}`",
        f"- cases: `{manifest['counts']['cases']}`",
        f"- passed: `{manifest['counts']['passed']}`",
        f"- failed: `{manifest['counts']['failed']}`",
        "",
        "## Scope",
        "",
    ]
    for key, value in manifest["user_effect_scope"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    for item in manifest["results"]:
        lines.extend(
            [
                f"## {item['case_id']}",
                "",
            ]
        )
        for key, value in item["checklist"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append(f"- `evidence_path`: `{item['evidence_path']}`")
        lines.append("")
    return "\n".join(lines)
