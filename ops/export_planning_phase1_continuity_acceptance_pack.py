#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPLETE_SCRIPT = REPO_ROOT / "scripts" / "planning_task_checkpoint_complete.py"
sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3


SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "meeting_sedimentation",
        "message": "请整理今天项目例会的会议纪要和行动项",
        "continue_message": "继续完善这条会议沉淀线程",
        "goal_hint": "report",
        "route": "report",
        "task_type": "meeting_sedimentation",
        "task_prefix": "mtg_",
        "checkpoint_version": "meeting-sedimentation-checkpoint-v1",
        "attachment_name": "meeting_transcript.md",
        "attachment_text": "# 例会转写\n- Alice: 本周需要确认供应商恢复计划。\n",
        "answer": (
            "## Meeting Context\n"
            "- Participants: Alice, Bob\n\n"
            "## Decisions\n"
            "- Freeze the rollout baseline.\n"
        ),
        "writeback_output": "## Summary\n- 已完成会议沉淀补写。\n",
    },
    {
        "scenario_id": "workforce_planning",
        "message": "请给我做一份未来两个季度的人力规划方案",
        "continue_message": "继续完善这份人力规划方案",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "workforce_planning",
        "task_prefix": "wfp_",
        "checkpoint_version": "workforce-planning-checkpoint-v1",
        "attachment_name": "headcount.xlsx",
        "attachment_text": "role,count\nPM,1\n采购,1\n",
        "answer": (
            "## Staffing Goal\n"
            "- 支撑未来两个季度业务导入。\n\n"
            "## Headcount Plan\n"
            "- PM 1\n"
            "- 采购 1\n"
        ),
        "writeback_output": "## Headcount Plan\n- PM 1\n- 采购 1\n- 质量 1\n",
    },
    {
        "scenario_id": "implementation_plan",
        "message": "请给我做一个供应链系统改造实施计划",
        "continue_message": "继续补齐这份实施计划",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "implementation_plan",
        "task_prefix": "impl_",
        "checkpoint_version": "implementation-plan-checkpoint-v1",
        "attachment_name": "requirements.md",
        "attachment_text": "# 需求\n- 供应链系统改造分三阶段推进。\n",
        "answer": (
            "## Goal\n"
            "- 完成供应链系统改造。\n\n"
            "## Plan\n"
            "- Phase 1: baseline\n"
            "- Phase 2: rollout\n"
        ),
        "writeback_output": "## Plan\n- Phase 1: baseline\n- Phase 2: rollout\n- Phase 3: validation\n",
    },
    {
        "scenario_id": "project_diagnosis",
        "message": "请判断 Robovance 项目当前阶段、下一里程碑和主要风险",
        "continue_message": "继续完善这条项目诊断线程",
        "goal_hint": "planning",
        "route": "funnel",
        "task_type": "project_diagnosis",
        "task_prefix": "diag_",
        "checkpoint_version": "project-diagnosis-checkpoint-v1",
        "attachment_name": "project_status.md",
        "attachment_text": "# 项目状态\n- 当前样件验证中。\n- 供应链恢复窗口待确认。\n",
        "answer": (
            "## Current Stage\n"
            "- 样件验证\n\n"
            "## Next Milestone\n"
            "- 锁定量产节奏\n\n"
            "## Risks\n"
            "- 供应链恢复窗口未锁定\n"
        ),
        "writeback_output": "## Diagnosis Update\n- 需先锁定供应链恢复窗口，再承诺量产时间。\n",
    },
    {
        "scenario_id": "research_decision",
        "message": "请把这份调研材料转成可拍板的判断稿",
        "continue_message": "继续完善这条研究判断线程",
        "goal_hint": "research",
        "route": "report",
        "task_type": "research_decision",
        "task_prefix": "res_",
        "checkpoint_version": "research-decision-checkpoint-v1",
        "attachment_name": "research_packet.md",
        "attachment_text": "# 调研\n- 北美客户窗口明确，但供应链恢复节奏不稳定。\n",
        "answer": (
            "## Core Judgment\n"
            "- 可推进，但需锁定供应链恢复窗口。\n\n"
            "## Suggested Action\n"
            "- 先确认恢复窗口，再给客户量产承诺。\n"
        ),
        "writeback_output": "## Judgment Update\n- 建议先锁定供应链恢复窗口，再进入客户承诺阶段。\n",
    },
    {
        "scenario_id": "leadership_report",
        "message": "请给我整理一版董事长汇报摘要",
        "continue_message": "继续完善这份董事长汇报摘要",
        "goal_hint": "report",
        "route": "report",
        "task_type": "leadership_report",
        "task_prefix": "rpt_",
        "checkpoint_version": "leadership-report-checkpoint-v1",
        "attachment_name": "briefing.md",
        "attachment_text": "# 汇报底稿\n- 当前阶段：样件验证。\n- 风险：供应链恢复窗口待确认。\n",
        "answer": (
            "## 董事长摘要\n"
            "- 当前处于样件验证阶段。\n"
            "- 需先锁定供应链恢复窗口，再承诺量产节奏。\n"
        ),
        "writeback_output": "## 汇报补充\n- 建议拍板：先锁定供应链恢复窗口，再承诺量产节奏。\n",
    },
    {
        "scenario_id": "planning_general",
        "message": "请整理一版业务推进方案和下一步计划",
        "continue_message": "继续完善这份业务推进方案",
        "goal_hint": "planning",
        "route": "report",
        "task_type": "planning_general",
        "task_prefix": "pln_",
        "checkpoint_version": "planning-general-checkpoint-v1",
        "attachment_name": "biz_plan.md",
        "attachment_text": "# 业务推进\n- 先做客户导入节奏和资源规划。\n",
        "answer": (
            "## Working Plan\n"
            "- 先锁定客户导入节奏。\n"
            "- 再补资源规划与风险清单。\n"
        ),
        "writeback_output": "## Planning Update\n- 下一步补齐资源规划、风险清单与责任人。\n",
    },
]


def _make_controller(answer: str, route: str, artifact_path: Path):
    class _Controller:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            return {
                "run_id": f"run-{route}",
                "job_id": f"job-{route}",
                "route": route,
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": answer,
                "artifacts": [{"kind": "report", "path": str(artifact_path)}],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": route,
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "done"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    return _Controller


def _write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _scenario_report_lines(result: dict[str, Any]) -> list[str]:
    lines = [
        f"## {result['scenario_id']}",
        "",
        f"- `task_id`: `{result['task_id']}`",
        f"- `task_type`: `{result['task_type']}`",
        f"- `first_response_ok`: `{result['checks']['first_response_ok']}`",
        f"- `retrieve_ok`: `{result['checks']['retrieve_ok']}`",
        f"- `identity_continue_ok`: `{result['checks']['identity_continue_ok']}`",
        f"- `explicit_continue_ok`: `{result['checks']['explicit_continue_ok']}`",
        f"- `cross_identity_continue_guard_ok`: `{result['checks']['cross_identity_continue_guard_ok']}`",
        f"- `list_ok`: `{result['checks']['list_ok']}`",
        f"- `writeback_ok`: `{result['checks']['writeback_ok']}`",
        f"- `writeback_content_ok`: `{result['checks']['writeback_content_ok']}`",
        f"- `checkpoint_version_ok`: `{result['checks']['checkpoint_version_ok']}`",
        f"- `evidence_dir`: `{result['evidence_dir']}`",
        "",
    ]
    return lines


def _writeback_content_ok(after_writeback_body: dict[str, Any], expected_output: str) -> bool:
    persisted = str(
        (
            after_writeback_body.get("planning_task", {})
            .get("checkpoint", {})
            .get("latest_output", "")
        )
        or ""
    ).strip()
    return persisted == str(expected_output or "").strip()


def export_pack(*, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runtime_dir = out / "planning_tasks_runtime"
    env = dict(os.environ)
    env["OPENMIND_API_KEY"] = "test-key"
    env["OPENMIND_AUTH_MODE"] = "strict"
    env["OPENMIND_RATE_LIMIT"] = "1000"
    env["CHATGPTREST_PLANNING_TASK_DIR"] = str(runtime_dir.resolve())

    with patch.dict(os.environ, env, clear=False), patch.object(routes_agent_v3, "_advisor_runtime", lambda: {}):
        app = FastAPI()
        app.include_router(routes_agent_v3.make_v3_agent_router())
        client = TestClient(app, raise_server_exceptions=False)
        headers = {"X-Api-Key": "test-key"}
        scenario_results: list[dict[str, Any]] = []

        for index, scenario in enumerate(SCENARIOS, start=1):
            scenario_dir = out / scenario["scenario_id"]
            attachment_path = _write_file(scenario_dir / scenario["attachment_name"], scenario["attachment_text"])
            artifact_path = scenario_dir / "controller_artifact.md"
            controller_cls = _make_controller(scenario["answer"], scenario["route"], artifact_path)
            first_account = f"acct-{index}"
            first_thread = f"thread-{index}"

            with patch.object(routes_agent_v3, "ControllerEngine", controller_cls):
                first_payload = {
                    "message": scenario["message"],
                    "goal_hint": scenario["goal_hint"],
                    "role_id": "planning",
                    "account_id": first_account,
                    "thread_id": first_thread,
                    "agent_id": "openclawbot",
                    "attachments": [str(attachment_path)],
                }
                first = client.post("/v3/agent/turn", json=first_payload, headers=headers)
                first_body = first.json()
                task_id = str(first_body.get("task_id") or "")

                lookup = client.get(
                    f"/v3/agent/planning/task/{task_id}",
                    params={"account_id": first_account, "thread_id": first_thread},
                    headers=headers,
                )
                lookup_body = lookup.json()

                identity_continue = client.post(
                    "/v3/agent/turn",
                    json={
                        "message": scenario["continue_message"],
                        "goal_hint": scenario["goal_hint"],
                        "role_id": "planning",
                        "account_id": first_account,
                        "thread_id": first_thread,
                        "agent_id": "openclawbot",
                        "task_intake": {
                            "spec_version": "task-intake-v2",
                            "source": "openclaw",
                            "objective": scenario["continue_message"],
                            "context": {
                                "planning_task_action": "continue",
                            },
                        },
                    },
                    headers=headers,
                )
                identity_continue_body = identity_continue.json()

                explicit_continue = client.post(
                    "/v3/agent/turn",
                    json={
                        "message": f"显式继续完善 {scenario['scenario_id']}",
                        "goal_hint": scenario["goal_hint"],
                        "role_id": "planning",
                        "account_id": first_account,
                        "thread_id": first_thread,
                        "agent_id": "openclawbot",
                        "task_intake": {
                            "spec_version": "task-intake-v2",
                            "source": "openclaw",
                            "objective": f"显式继续完善 {scenario['scenario_id']}",
                            "task_id": task_id,
                            "context": {
                                "planning_task_type": scenario["task_type"],
                                "planning_task_action": "continue",
                            },
                        },
                    },
                    headers=headers,
                )
                explicit_continue_body = explicit_continue.json()

                cross_identity_continue = client.post(
                    "/v3/agent/turn",
                    json={
                        "message": f"跨端继续完善 {scenario['scenario_id']}",
                        "goal_hint": scenario["goal_hint"],
                        "role_id": "planning",
                        "account_id": f"{first_account}-alt",
                        "thread_id": f"{first_thread}-alt",
                        "agent_id": "openclawbot",
                        "task_intake": {
                            "spec_version": "task-intake-v2",
                            "source": "openclaw",
                            "objective": f"跨端继续完善 {scenario['scenario_id']}",
                            "task_id": task_id,
                            "context": {
                                "planning_task_type": scenario["task_type"],
                                "planning_task_action": "continue",
                            },
                        },
                    },
                    headers=headers,
                )
                cross_identity_continue_body = cross_identity_continue.json()

                listed = client.get(
                    "/v3/agent/planning/tasks",
                    params={"account_id": first_account, "thread_id": first_thread},
                    headers=headers,
                )
                listed_body = listed.json()

            writeback_output = _write_file(scenario_dir / "writeback_output.md", scenario["writeback_output"])
            writeback = subprocess.run(
                [
                    sys.executable,
                    str(COMPLETE_SCRIPT),
                    "--task-id",
                    task_id,
                    "--output-file",
                    str(writeback_output),
                    "--artifact-ref",
                    str(writeback_output),
                ],
                check=False,
                capture_output=True,
                text=True,
                env={**env, "TMUX_PANE": f"%{40 + index}"},
                cwd=str(REPO_ROOT),
            )
            writeback_body = json.loads(writeback.stdout or "{}")
            after_writeback = client.get(
                f"/v3/agent/planning/task/{task_id}",
                params={"account_id": first_account, "thread_id": first_thread},
                headers=headers,
            )
            after_writeback_body = after_writeback.json()

            writeback_content_ok = _writeback_content_ok(after_writeback_body, scenario["writeback_output"])
            scenario_payload = {
                "scenario_id": scenario["scenario_id"],
                "task_id": task_id,
                "task_type": scenario["task_type"],
                "evidence_dir": str(scenario_dir),
                "files": {
                    "attachment": str(attachment_path),
                    "writeback_output": str(writeback_output),
                },
                "checks": {
                    "first_response_ok": (
                        first.status_code == 200
                        and task_id.startswith(scenario["task_prefix"])
                        and first_body.get("planning_task", {}).get("task_type") == scenario["task_type"]
                    ),
                    "retrieve_ok": (
                        lookup.status_code == 200
                        and lookup_body.get("planning_task", {}).get("task_type") == scenario["task_type"]
                    ),
                    "identity_continue_ok": (
                        identity_continue.status_code == 200
                        and identity_continue_body.get("task_id") == task_id
                        and identity_continue_body.get("planning_task", {}).get("resolution") == "continue"
                    ),
                    "explicit_continue_ok": (
                        explicit_continue.status_code == 200
                        and explicit_continue_body.get("task_id") == task_id
                        and explicit_continue_body.get("planning_task", {}).get("resolution") == "continue_explicit"
                    ),
                    "cross_identity_continue_guard_ok": (
                        cross_identity_continue.status_code in {404, 409}
                        and (
                            cross_identity_continue_body.get("detail", {}).get("error")
                            in {"planning_task_not_found", "planning_task_visibility_mismatch"}
                        )
                    ),
                    "list_ok": (
                        listed.status_code == 200
                        and int(listed_body.get("count") or 0) >= 1
                        and any(item.get("task_id") == task_id for item in list(listed_body.get("planning_tasks") or []))
                    ),
                    "writeback_ok": writeback.returncode == 0 and after_writeback.status_code == 200,
                    "writeback_content_ok": writeback_content_ok,
                    "checkpoint_version_ok": (
                        lookup_body.get("planning_task", {}).get("checkpoint", {}).get("checkpoint_version")
                        == scenario["checkpoint_version"]
                    ),
                },
                "responses": {
                    "first": first_body,
                    "lookup": lookup_body,
                    "identity_continue": identity_continue_body,
                    "explicit_continue": explicit_continue_body,
                    "cross_identity_continue": cross_identity_continue_body,
                    "list": listed_body,
                    "writeback": writeback_body,
                    "after_writeback": after_writeback_body,
                },
            }
            (scenario_dir / "scenario_result.json").write_text(
                json.dumps(scenario_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            scenario_results.append(scenario_payload)

    overall_pass = all(all(bool(value) for value in item["checks"].values()) for item in scenario_results)
    manifest = {
        "ok": True,
        "overall_pass": overall_pass,
        "counts": {
            "scenarios": len(scenario_results),
            "passed": sum(1 for item in scenario_results if all(item["checks"].values())),
            "failed": sum(1 for item in scenario_results if not all(item["checks"].values())),
        },
        "scope": {
            "phase1_continuity_only": False,
            "planning_task_plane": True,
            "full_task_runtime": False,
            "live_claude_signoff": False,
            "rate_limit_override": "OPENMIND_RATE_LIMIT=1000",
        },
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "task_id": item["task_id"],
                "task_type": item["task_type"],
                "checks": dict(item["checks"]),
                "evidence_dir": item["evidence_dir"],
            }
            for item in scenario_results
        ],
        "files": {
            "report_md": str(out / "report_v1.md"),
        },
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    smoke_manifest_path = out / "smoke_manifest.json"
    smoke_manifest_path.write_text(
        json.dumps(
            {
                "overall_pass": overall_pass,
                "scenario_ids": [item["scenario_id"] for item in scenario_results],
                "task_ids": [item["task_id"] for item in scenario_results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# Planning Task Plane Acceptance Pack v1",
        "",
        f"- `overall_pass`: `{overall_pass}`",
        f"- `scenarios`: `{len(scenario_results)}`",
        "",
    ]
    for item in scenario_results:
        report_lines.extend(_scenario_report_lines(item))
    report_path = out / "report_v1.md"
    report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "ok": True,
        "overall_pass": overall_pass,
        "output_dir": str(out),
        "manifest_path": str(manifest_path),
        "smoke_manifest_path": str(smoke_manifest_path),
        "report_path": str(report_path),
        "scenario_results": scenario_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a deterministic acceptance pack for the planning task plane.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = export_pack(output_dir=args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
