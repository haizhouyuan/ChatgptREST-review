from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    DEFAULT_PLUGIN_SOURCE,
    DEFAULT_TYPEBOX_PATH,
    _execute_openclaw_plugin_tool,
)


SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "meeting_sedimentation",
        "message": "请整理今天项目例会的会议纪要和行动项",
        "continue_message": "继续补齐这条会议沉淀线程的行动项和结论",
        "goal_hint": "report",
        "route": "report",
        "task_type": "meeting_sedimentation",
        "task_prefix": "mtg_",
        "checkpoint_version": "meeting-sedimentation-checkpoint-v1",
        "attachment_name": "meeting_transcript.md",
        "attachment_text": "# 例会转写\n- Alice: 本周需要确认供应商恢复计划。\n",
        "attachment_mode": "media",
        "answer": "## Meeting Context\n- Participants: Alice, Bob\n\n## Decisions\n- Freeze the rollout baseline.\n",
        "continue_answer": "## Meeting Update\n- 补充行动项：Alice 跟进供应商恢复计划。\n",
    },
    {
        "scenario_id": "workforce_planning",
        "message": "请给我做一份未来两个季度的人力规划方案",
        "continue_message": "继续补齐这份人力规划方案的岗位动作",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "workforce_planning",
        "task_prefix": "wfp_",
        "checkpoint_version": "workforce-planning-checkpoint-v1",
        "attachment_name": "headcount.csv",
        "attachment_text": "role,count\nPM,1\n采购,1\n",
        "attachment_mode": "files",
        "answer": "## Staffing Goal\n- 支撑未来两个季度业务导入。\n\n## Headcount Plan\n- PM 1\n- 采购 1\n",
        "continue_answer": "## Headcount Update\n- 继续补充质量岗位 1。\n",
    },
    {
        "scenario_id": "implementation_plan",
        "message": "请给我做一个供应链系统改造实施计划",
        "continue_message": "继续补齐这份实施计划的阶段安排",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "implementation_plan",
        "task_prefix": "impl_",
        "checkpoint_version": "implementation-plan-checkpoint-v1",
        "attachment_name": "requirements.md",
        "attachment_text": "# 需求\n- 供应链系统改造分三阶段推进。\n",
        "attachment_mode": "files",
        "answer": "## Goal\n- 完成供应链系统改造。\n\n## Plan\n- Phase 1: baseline\n- Phase 2: rollout\n",
        "continue_answer": "## Plan Update\n- Phase 3: validation\n",
    },
    {
        "scenario_id": "project_diagnosis",
        "message": "请判断 Robovance 项目当前阶段、下一里程碑和主要风险",
        "continue_message": "继续完善这条项目诊断线程并补下一步动作",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "project_diagnosis",
        "task_prefix": "diag_",
        "checkpoint_version": "project-diagnosis-checkpoint-v1",
        "attachment_name": "project_status.md",
        "attachment_text": "# 项目状态\n- 当前样件验证中。\n- 供应链恢复窗口待确认。\n",
        "attachment_mode": "files",
        "answer": "## Current Stage\n- 样件验证\n\n## Next Milestone\n- 锁定量产节奏\n\n## Risks\n- 供应链恢复窗口未锁定\n",
        "continue_answer": "## Diagnosis Update\n- 下一步先锁定供应链恢复窗口。\n",
    },
    {
        "scenario_id": "research_decision",
        "message": "请把这份调研材料转成可拍板的判断稿",
        "continue_message": "继续完善这条研究判断线程的建议动作",
        "goal_hint": "research",
        "route": "report",
        "task_type": "research_decision",
        "task_prefix": "res_",
        "checkpoint_version": "research-decision-checkpoint-v1",
        "attachment_name": "research_packet.md",
        "attachment_text": "# 调研\n- 北美客户窗口明确，但供应链恢复节奏不稳定。\n",
        "attachment_mode": "files",
        "answer": "## Core Judgment\n- 可推进，但需锁定供应链恢复窗口。\n\n## Suggested Action\n- 先确认恢复窗口，再给客户量产承诺。\n",
        "continue_answer": "## Judgment Update\n- 建议把恢复窗口写入项目周计划。\n",
    },
    {
        "scenario_id": "leadership_report",
        "message": "请给我整理一版董事长汇报摘要",
        "continue_message": "继续完善这份董事长汇报摘要的拍板建议",
        "goal_hint": "report",
        "route": "report",
        "task_type": "leadership_report",
        "task_prefix": "rpt_",
        "checkpoint_version": "leadership-report-checkpoint-v1",
        "attachment_name": "briefing.md",
        "attachment_text": "# 汇报底稿\n- 当前阶段：样件验证。\n- 风险：供应链恢复窗口待确认。\n",
        "attachment_mode": "files",
        "answer": "## 董事长摘要\n- 当前处于样件验证阶段。\n- 需先锁定供应链恢复窗口，再承诺量产节奏。\n",
        "continue_answer": "## 汇报补充\n- 建议拍板：先锁定供应链恢复窗口。\n",
    },
    {
        "scenario_id": "planning_general",
        "message": "请整理一版业务推进方案和下一步计划",
        "continue_message": "继续完善这份业务推进方案的责任人和节奏",
        "goal_hint": "planning",
        "route": "report",
        "task_type": "planning_general",
        "task_prefix": "pln_",
        "checkpoint_version": "planning-general-checkpoint-v1",
        "attachment_name": "biz_plan.md",
        "attachment_text": "# 业务推进\n- 先做客户导入节奏和资源规划。\n",
        "attachment_mode": "files",
        "answer": "## Working Plan\n- 先锁定客户导入节奏。\n- 再补资源规划与风险清单。\n",
        "continue_answer": "## Planning Update\n- 增加责任人与周节奏安排。\n",
    },
]

BRANCH_CASE = {
    "source_scenario_id": "project_diagnosis",
    "message": "把同一项目诊断整理成董事长汇报摘要",
    "goal_hint": "report",
    "route": "report",
    "expected_task_type": "leadership_report",
    "expected_prefix": "rpt_",
    "answer": "## 董事长摘要\n- 当前阶段：样件验证。\n- 建议：锁定量产窗口后再推进量产承诺。\n",
}


@dataclass
class OpenClawPlanningScenarioResult:
    scenario_id: str
    task_id: str
    task_type: str
    checks: dict[str, bool]
    evidence_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "checks": dict(self.checks),
            "evidence_dir": self.evidence_dir,
        }


@dataclass
class OpenClawPlanningBranchResult:
    source_scenario_id: str
    branch_task_id: str
    checks: dict[str, bool]
    evidence_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_scenario_id": self.source_scenario_id,
            "branch_task_id": self.branch_task_id,
            "checks": dict(self.checks),
            "evidence_dir": self.evidence_dir,
        }


@dataclass
class OpenClawPlanningAcceptanceReport:
    ok: bool
    overall_pass: bool
    scenario_results: list[OpenClawPlanningScenarioResult]
    branch_result: OpenClawPlanningBranchResult | None
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "overall_pass": self.overall_pass,
            "scenario_results": [item.to_dict() for item in self.scenario_results],
            "branch_result": self.branch_result.to_dict() if self.branch_result else None,
            "output_dir": self.output_dir,
        }


class _PlanningTaskPlaneProxyHandler(BaseHTTPRequestHandler):
    server: "_PlanningTaskPlaneProxyServer"

    def do_GET(self) -> None:  # noqa: N802
        self._proxy_request("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._proxy_request("POST")

    def _proxy_request(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b""
        json_body = None
        if raw_body:
            try:
                json_body = json.loads(raw_body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                json_body = None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "accept-encoding", "connection"}
        }
        response = self.server.client.request(
            method,
            self.path,
            headers=headers,
            json=json_body,
        )
        payload = response.content
        self.send_response(response.status_code)
        self.send_header("Content-Type", response.headers.get("content-type", "application/json; charset=utf-8"))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class _PlanningTaskPlaneProxyServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, app: FastAPI) -> None:
        super().__init__(("127.0.0.1", 0), _PlanningTaskPlaneProxyHandler)
        self.client = TestClient(app, raise_server_exceptions=False)
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.shutdown()
        self.server_close()
        self.client.close()
        self._thread.join(timeout=5.0)


def export_pack(
    *,
    output_dir: str | Path,
    scenario_ids: list[str] | None = None,
    include_branch: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runtime_dir = out / "planning_tasks_runtime"
    env = dict(os.environ)
    env["OPENMIND_API_KEY"] = "test-key"
    env["OPENMIND_AUTH_MODE"] = "strict"
    env["OPENMIND_RATE_LIMIT"] = "1000"
    env["CHATGPTREST_PLANNING_TASK_DIR"] = str(runtime_dir.resolve())

    selected = [
        item for item in SCENARIOS
        if not scenario_ids or item["scenario_id"] in set(scenario_ids)
    ]
    scenario_by_id = {item["scenario_id"]: item for item in selected}
    controller_cls = _build_controller(selected, BRANCH_CASE if include_branch else None)

    with patch.dict(os.environ, env, clear=False), patch.object(routes_agent_v3, "_advisor_runtime", lambda: {}), patch.object(routes_agent_v3, "ControllerEngine", controller_cls):
        app = FastAPI()
        app.include_router(routes_agent_v3.make_v3_agent_router())
        proxy = _PlanningTaskPlaneProxyServer(app)
        try:
            scenario_results: list[OpenClawPlanningScenarioResult] = []
            scenario_task_ids: dict[str, str] = {}
            scenario_indices: dict[str, int] = {}
            for index, scenario in enumerate(selected, start=1):
                scenario_indices[scenario["scenario_id"]] = index
                scenario_dir = out / scenario["scenario_id"]
                scenario_dir.mkdir(parents=True, exist_ok=True)
                attachment_path = scenario_dir / scenario["attachment_name"]
                attachment_path.write_text(scenario["attachment_text"], encoding="utf-8")
                runtime_ctx = _runtime_ctx(scenario["scenario_id"], index=index, turn="first")
                first_context = _scenario_context(scenario, attachment_path)
                first = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    question=scenario["message"],
                    goal_hint=scenario["goal_hint"],
                    timeout_seconds=60,
                    context=first_context,
                    runtime_ctx=runtime_ctx,
                    request_timeout_ms=30000,
                )
                first_details = _tool_details(first)
                task_id = str(first_details.get("task_id") or "").strip()
                scenario_task_ids[scenario["scenario_id"]] = task_id

                retrieve = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_task_get",
                    tool_params={"taskId": task_id},
                )
                retrieve_details = _tool_details(retrieve)

                task_list = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_task_list",
                    tool_params={"taskType": scenario["task_type"], "limit": 10},
                )
                task_list_details = _tool_details(task_list)

                session_get = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_session_get",
                    tool_params={},
                )
                session_get_details = _tool_details(session_get)

                continue_runtime_ctx = _runtime_ctx(scenario["scenario_id"], index=index, turn="continue")
                continue_context = dict(first_context)
                continue_context["planning_task_type"] = scenario["task_type"]
                continue_context["planning_task_action"] = "continue"
                continue_result = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=continue_runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_ask",
                    tool_params={
                        "question": scenario["continue_message"],
                        "goalHint": scenario["goal_hint"],
                        "timeoutSeconds": 60,
                        "context": continue_context,
                        "taskId": task_id,
                        "taskAction": "continue",
                    },
                )
                continue_details = _tool_details(continue_result)

                retrieve_after_continue = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=continue_runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_task_get",
                    tool_params={"taskId": task_id},
                )
                retrieve_after_continue_details = _tool_details(retrieve_after_continue)

                session_cancel = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=continue_runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_session_cancel",
                    tool_params={},
                )
                session_cancel_details = _tool_details(session_cancel)

                session_get_after_cancel = _execute_openclaw_plugin_tool(
                    base_url=proxy.base_url,
                    api_key="test-key",
                    plugin_source=DEFAULT_PLUGIN_SOURCE,
                    typebox_path=DEFAULT_TYPEBOX_PATH,
                    runtime_ctx=continue_runtime_ctx,
                    request_timeout_ms=30000,
                    tool_name="openmind_advisor_session_get",
                    tool_params={},
                )
                session_get_after_cancel_details = _tool_details(session_get_after_cancel)

                checkpoint = dict((retrieve_details.get("planning_task") or {}).get("checkpoint") or {})
                checkpoint_after_continue = dict((retrieve_after_continue_details.get("planning_task") or {}).get("checkpoint") or {})
                listed_tasks = list(task_list_details.get("planning_tasks") or [])
                checks = {
                    "first_response_ok": task_id.startswith(scenario["task_prefix"]),
                    "retrieve_ok": str((retrieve_details.get("planning_task") or {}).get("task_type") or "").strip() == scenario["task_type"],
                    "task_list_ok": (
                        int(task_list_details.get("count") or 0) >= 1
                        and any(str(item.get("task_id") or "").strip() == task_id for item in listed_tasks if isinstance(item, dict))
                    ),
                    "session_get_ok": (
                        str(session_get_details.get("session_id") or "").strip() == str(first_details.get("session_id") or "").strip()
                        and str(session_get_details.get("status") or "").strip() in {"running", "completed", "needs_followup", "needs_input"}
                    ),
                    "source_material_capture_ok": str(attachment_path) in list(checkpoint.get("source_materials") or []),
                    "explicit_continue_ok": (
                        str(continue_details.get("task_id") or "").strip() == task_id
                        and str((continue_details.get("planning_task") or {}).get("resolution") or "").strip() == "continue_explicit"
                    ),
                    "post_continue_retrieve_ok": (
                        str((retrieve_after_continue_details.get("planning_task") or {}).get("latest_session_id") or "").strip()
                        == str(continue_details.get("session_id") or "").strip()
                        and str(checkpoint_after_continue.get("latest_output") or "").strip() == str(scenario["continue_answer"]).strip()
                    ),
                    "session_cancel_ok": (
                        str(session_cancel_details.get("status") or "").strip() == "cancelled"
                        and str(session_get_after_cancel_details.get("status") or "").strip() == "cancelled"
                    ),
                    "checkpoint_version_ok": str(checkpoint.get("checkpoint_version") or "").strip() == scenario["checkpoint_version"],
                }
                scenario_payload = {
                    "first": first,
                    "retrieve": retrieve,
                    "task_list": task_list,
                    "session_get": session_get,
                    "continue": continue_result,
                    "retrieve_after_continue": retrieve_after_continue,
                    "session_cancel": session_cancel,
                    "session_get_after_cancel": session_get_after_cancel,
                    "checks": checks,
                }
                (scenario_dir / "scenario_result.json").write_text(
                    json.dumps(scenario_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                scenario_results.append(
                    OpenClawPlanningScenarioResult(
                        scenario_id=scenario["scenario_id"],
                        task_id=task_id,
                        task_type=scenario["task_type"],
                        checks=checks,
                        evidence_dir=str(scenario_dir),
                    )
                )

            branch_result = _run_branch_case(
                proxy_base_url=proxy.base_url,
                source_task_id=scenario_task_ids.get(BRANCH_CASE["source_scenario_id"], ""),
                source_index=int(scenario_indices.get(BRANCH_CASE["source_scenario_id"], 99)),
                out_dir=out / "branch_case",
            ) if include_branch and BRANCH_CASE["source_scenario_id"] in scenario_by_id else None
        finally:
            proxy.close()

    overall_pass = all(all(item.checks.values()) for item in scenario_results)
    if branch_result is not None:
        overall_pass = overall_pass and all(branch_result.checks.values())

    manifest = {
        "ok": True,
        "overall_pass": overall_pass,
        "counts": {
            "scenarios": len(scenario_results),
            "passed": sum(1 for item in scenario_results if all(item.checks.values())),
            "failed": sum(1 for item in scenario_results if not all(item.checks.values())),
            "branch_passed": bool(branch_result and all(branch_result.checks.values())),
        },
        "scenario_ids": [item.scenario_id for item in scenario_results],
        "scope": {
            "openclaw_plugin_entry": True,
            "canonical_agent_v3_path": True,
            "task_get_surface": True,
            "task_list_surface": True,
            "session_get_surface": True,
            "session_cancel_surface": True,
            "explicit_continue_surface": True,
            "branch_surface": bool(branch_result is not None),
            "rate_limit_override": "OPENMIND_RATE_LIMIT=1000",
        },
        "scenario_results": [item.to_dict() for item in scenario_results],
        "branch_result": branch_result.to_dict() if branch_result else None,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = _render_report(manifest)
    (out / "report_v1.md").write_text(report, encoding="utf-8")
    return manifest


def _run_branch_case(
    *,
    proxy_base_url: str,
    source_task_id: str,
    source_index: int,
    out_dir: Path,
) -> OpenClawPlanningBranchResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime_ctx = _runtime_ctx(BRANCH_CASE["source_scenario_id"], index=source_index, turn="branch")
    result = _execute_openclaw_plugin_tool(
        base_url=proxy_base_url,
        api_key="test-key",
        plugin_source=DEFAULT_PLUGIN_SOURCE,
        typebox_path=DEFAULT_TYPEBOX_PATH,
        runtime_ctx=runtime_ctx,
        request_timeout_ms=30000,
        tool_name="openmind_advisor_ask",
        tool_params={
            "question": BRANCH_CASE["message"],
            "goalHint": BRANCH_CASE["goal_hint"],
            "timeoutSeconds": 60,
            "taskId": source_task_id,
            "taskAction": "branch",
            "context": {
                "planning_task_action": "branch",
                "planning_task_type": "leadership_report",
                "project_or_topic_ref": "Robovance",
            },
        },
    )
    details = _tool_details(result)
    branch_task_id = str(details.get("task_id") or "").strip()
    retrieve = _execute_openclaw_plugin_tool(
        base_url=proxy_base_url,
        api_key="test-key",
        plugin_source=DEFAULT_PLUGIN_SOURCE,
        typebox_path=DEFAULT_TYPEBOX_PATH,
        runtime_ctx=runtime_ctx,
        request_timeout_ms=30000,
        tool_name="openmind_advisor_task_get",
        tool_params={"taskId": branch_task_id},
    )
    retrieve_details = _tool_details(retrieve)
    checks = {
        "branch_new_task_ok": branch_task_id.startswith(BRANCH_CASE["expected_prefix"]) and branch_task_id != source_task_id,
        "branch_parent_ok": str((details.get("planning_task") or {}).get("parent_task_id") or "").strip() == source_task_id,
        "branch_retrieve_ok": str((retrieve_details.get("planning_task") or {}).get("task_type") or "").strip() == BRANCH_CASE["expected_task_type"],
    }
    (out_dir / "scenario_result.json").write_text(
        json.dumps({"branch": result, "retrieve": retrieve, "checks": checks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return OpenClawPlanningBranchResult(
        source_scenario_id=BRANCH_CASE["source_scenario_id"],
        branch_task_id=branch_task_id,
        checks=checks,
        evidence_dir=str(out_dir),
    )


def _tool_details(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result.get("result") or {})
    details = payload.get("details")
    return dict(details or {}) if isinstance(details, dict) else {}


def _runtime_ctx(scenario_id: str, *, index: int, turn: str) -> dict[str, Any]:
    return {
        "sessionKey": f"oc-{scenario_id}-{turn}-session",
        "sessionId": f"oc-{scenario_id}-thread",
        "agentAccountId": f"acct-{index}",
        "agentId": "openclawbot",
    }


def _scenario_context(scenario: dict[str, Any], attachment_path: Path) -> dict[str, Any]:
    if scenario.get("attachment_mode") == "media":
        return {
            "MediaPath": str(attachment_path),
            "MediaPaths": [str(attachment_path)],
        }
    return {"files": [str(attachment_path)]}


def _build_controller(scenarios: list[dict[str, Any]], branch_case: dict[str, Any] | None):
    scenario_by_message: dict[str, dict[str, Any]] = {}
    for item in scenarios:
        scenario_by_message[str(item["message"])] = {"route": item["route"], "answer": item["answer"]}
        scenario_by_message[str(item["continue_message"])] = {"route": item["route"], "answer": item["continue_answer"]}
    if branch_case:
        scenario_by_message[str(branch_case["message"])] = {"route": branch_case["route"], "answer": branch_case["answer"]}

    class _Controller:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            message = str(kwargs.get("question") or kwargs.get("message") or "").strip()
            scenario = scenario_by_message.get(message)
            if scenario is None:
                raise AssertionError(f"unexpected planning acceptance message: {message}")
            route = str(scenario["route"])
            answer = str(scenario["answer"])
            return {
                "run_id": f"run-{abs(hash((route, message))) % 10_000_000}",
                "job_id": f"job-{abs(hash((message, route))) % 10_000_000}",
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
                    "route": "report",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "done"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    return _Controller


def _render_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# OpenClawBot Planning Task Plane Acceptance Pack",
        "",
        f"- overall_pass: `{manifest['overall_pass']}`",
        f"- scenarios: `{manifest['counts']['scenarios']}`",
        f"- passed: `{manifest['counts']['passed']}`",
        f"- failed: `{manifest['counts']['failed']}`",
        "",
    ]
    for item in manifest["scenario_results"]:
        lines.extend(
            [
                f"## {item['scenario_id']}",
                "",
                f"- `task_id`: `{item['task_id']}`",
                f"- `task_type`: `{item['task_type']}`",
            ]
        )
        for key, value in item["checks"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append(f"- `evidence_dir`: `{item['evidence_dir']}`")
        lines.append("")
    if manifest.get("branch_result"):
        branch = manifest["branch_result"]
        lines.extend(
            [
                "## branch_case",
                "",
                f"- `source_scenario_id`: `{branch['source_scenario_id']}`",
                f"- `branch_task_id`: `{branch['branch_task_id']}`",
            ]
        )
        for key, value in branch["checks"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append(f"- `evidence_dir`: `{branch['evidence_dir']}`")
        lines.append("")
    return "\n".join(lines)
