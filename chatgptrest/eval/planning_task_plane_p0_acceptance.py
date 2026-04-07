from __future__ import annotations

from contextlib import ExitStack
import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
import chatgptrest.evomap.knowledge.planning_runtime_pack_search as planning_runtime_pack_search
import chatgptrest.kernel.work_memory_manager as work_memory_manager
from chatgptrest.cognitive.memory_capture_service import MemoryCaptureResult, MemoryCaptureItemResult
from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    DEFAULT_PLUGIN_SOURCE,
    DEFAULT_TYPEBOX_PATH,
    _execute_openclaw_plugin_tool,
)
from chatgptrest.eval.openclawbot_planning_task_plane_acceptance import (
    SCENARIOS,
    _PlanningTaskPlaneProxyServer,
    _build_controller,
    _runtime_ctx,
    _scenario_context,
    _tool_details,
)


P0_SCENARIO_IDS = [
    "meeting_sedimentation",
    "workforce_planning",
    "project_diagnosis",
    "research_decision",
    "leadership_report",
]
P0_REQUIRED_MARKERS: dict[str, list[str]] = {
    "meeting_sedimentation": ["Meeting Context", "Decisions"],
    "workforce_planning": ["Staffing Goal", "Headcount Plan"],
    "project_diagnosis": ["Current Stage", "Next Milestone", "Risks"],
    "research_decision": ["Core Judgment", "Suggested Action"],
    "leadership_report": ["董事长摘要", "供应链恢复窗口"],
}
UNIFIED_CHECKLIST = [
    "understands_request",
    "covers_required_items",
    "voice_consistent",
    "directly_usable",
    "verifiable",
]


@dataclass
class PlanningP0ScenarioResult:
    scenario_id: str
    task_id: str
    task_type: str
    execution_mode: str
    checklist: dict[str, bool]
    evidence_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "execution_mode": self.execution_mode,
            "checklist": dict(self.checklist),
            "evidence_dir": self.evidence_dir,
        }


def _fake_knowledge_ingress(*, task_intake, **kwargs):  # noqa: ANN001
    task_intake.available_inputs = routes_agent_v3._append_available_input_notes(
        task_intake.available_inputs,
        notes=["Planning work memory: canonical P0 acceptance context loaded"],
    )
    task_intake.context["planning_knowledge_ingress"] = {
        "applied": True,
        "work_memory": {"loaded": True, "category_counts": {"active_project": 1}},
        "planning_pack": {
            "attempted": True,
            "available": True,
            "ready_for_explicit_consumption": True,
            "hit_count": 1,
            "pack_version": "p0-acceptance-pack",
            "bundle_freshness": "fresh",
        },
    }
    return dict(task_intake.context["planning_knowledge_ingress"])


def _fake_memory_writeback(**kwargs):  # noqa: ANN003
    task_layer = dict(kwargs.get("task_layer") or {})
    task_type = str(task_layer.get("task_type") or "").strip().lower()
    requested = ["decision_ledger"]
    if task_type in {"workforce_planning", "project_diagnosis", "leadership_report"}:
        requested = ["active_project", "decision_ledger"]
    return {
        "attempted": True,
        "eligible": True,
        "ok": True,
        "requested_categories": requested,
        "applied_count": len(requested),
        "writes": [
            {
                "ok": True,
                "category": category,
                "record_id": f"p0-{category}",
                "message": "captured",
            }
            for category in requested
        ],
    }


def _fake_unmocked_build_active_context(self, **kwargs):  # noqa: ANN001, ANN003
    query = str(kwargs.get("query") or "").strip()
    query_excerpt = query[:120] if query else "planning acceptance"
    return (
        "Active Project: planning acceptance workstream\n"
        f"Decision Ledger: keep the next answer grounded on {query_excerpt}",
        {
            "category_counts": {"active_project": 1, "decision_ledger": 1},
            "identity_gaps": [],
            "scope_hits": {"active_project": "account_thread", "decision_ledger": "account_thread"},
            "query_sensitive": bool(query),
            "import_hits": [
                {"category": "active_project", "record_id": "wm-active-project"},
                {"category": "decision_ledger", "record_id": "wm-decision-ledger"},
            ],
        },
    )


def _fake_unmocked_bundle_status(bundle_dir: str | Path = "") -> dict[str, Any]:
    return {
        "available": True,
        "ready_for_explicit_consumption": True,
        "bundle_dir": str(bundle_dir or "planning-runtime-pack-bundle"),
        "pack_dir": "planning-runtime-pack/p0-acceptance-pack",
        "pack_version": "p0-acceptance-pack",
        "bundle_generated_at": "2026-04-05T00:00:00Z",
        "bundle_age_hours": 1.0,
        "bundle_freshness": "fresh",
        "checks": {"schema_ok": True, "freshness_ok": True},
        "scope": {"review_domain": "planning", "mode": "acceptance"},
    }


def _fake_unmocked_runtime_pack_search(
    query: str,
    *,
    top_k: int = 5,
    bundle_dir: str | Path = "",
    db_path: str | Path = "",
) -> list[dict[str, Any]]:
    del bundle_dir, db_path
    if not query.strip():
        return []
    return [
        {
            "atom_id": "planning-pack-1",
            "title": "Canonical planning review guidance",
            "answer": "Use the current planning runtime pack as a stable reference.",
            "planning_pack_meta": {
                "pack_version": "p0-acceptance-pack",
                "bundle_generated_at": "2026-04-05T00:00:00Z",
                "bundle_age_hours": 1.0,
                "bundle_freshness": "fresh",
            },
        }
        for _ in range(max(1, min(int(top_k), 2)))
    ]


def _fake_unmocked_memory_capture(self, items):  # noqa: ANN001
    results = []
    for index, item in enumerate(items, start=1):
        results.append(
            MemoryCaptureItemResult(
                ok=True,
                trace_id=str(getattr(item, "trace_id", "") or f"trace-{index}"),
                title=str(getattr(item, "title", "") or f"Planning capture {index}"),
                record_id=f"p0-unmocked-{getattr(item, 'category', 'memory')}-{index}",
                category=str(getattr(item, "category", "") or "captured_memory"),
                tier="working",
                duplicate=False,
                message="captured",
                provenance_quality="complete",
                identity_gaps=[],
                blocked_by=[],
                quality_gate={},
                audit_trail=[],
                work_memory=dict(getattr(item, "object_payload", {}) or {}),
                review_status="approved",
                active=True,
                promotion_state="promoted",
                superseded_record_id="",
                governance={"mode": "acceptance_unmocked"},
            )
        )
    return MemoryCaptureResult(ok=True, results=results)


def _checklist_for(
    *,
    scenario: dict[str, Any],
    turn_details: dict[str, Any],
    task_details: dict[str, Any],
    session_details: dict[str, Any],
) -> dict[str, bool]:
    answer = str(turn_details.get("answer") or "").strip()
    control_plane = dict(turn_details.get("control_plane") or {})
    knowledge_ingress = dict(control_plane.get("knowledge_ingress") or {})
    memory_writeback = dict(control_plane.get("memory_writeback") or {})
    task_payload = dict(task_details.get("planning_task") or {})
    session_task = dict(session_details.get("planning_task") or {})
    required_markers = list(P0_REQUIRED_MARKERS.get(str(scenario["scenario_id"]), []))
    understands_request = bool(answer) and str(turn_details.get("status") or "").strip() == "completed"
    covers_required_items = all(marker in answer for marker in required_markers)
    voice_consistent = answer.startswith("##") and "trace_id" not in answer and "provider" not in answer
    directly_usable = bool(turn_details.get("task_id")) and bool(task_payload) and bool(answer)
    verifiable = (
        bool(knowledge_ingress.get("applied"))
        and bool(memory_writeback.get("attempted"))
        and str(task_payload.get("task_id") or "") == str(turn_details.get("task_id") or "")
        and str(session_task.get("task_id") or "") == str(turn_details.get("task_id") or "")
    )
    return {
        "understands_request": understands_request,
        "covers_required_items": covers_required_items,
        "voice_consistent": voice_consistent,
        "directly_usable": directly_usable,
        "verifiable": verifiable,
    }


def export_pack(*, output_dir: str | Path, unmocked_scenario_ids: list[str] | None = None) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runtime_dir = out / "planning_tasks_runtime"
    env = dict(os.environ)
    env["OPENMIND_API_KEY"] = "test-key"
    env["OPENMIND_AUTH_MODE"] = "strict"
    env["OPENMIND_RATE_LIMIT"] = "1000"
    env["CHATGPTREST_PLANNING_TASK_DIR"] = str(runtime_dir.resolve())
    selected = [item for item in SCENARIOS if item["scenario_id"] in set(P0_SCENARIO_IDS)]
    unmocked_set = {str(item).strip() for item in (unmocked_scenario_ids or []) if str(item).strip()}
    controller_cls = _build_controller(selected, branch_case=None)

    with (
        patch.dict(os.environ, env, clear=False),
        patch.object(
            routes_agent_v3,
            "_advisor_runtime",
            lambda: SimpleNamespace(memory=None, policy_engine=None, event_bus=None, observer=None),
        ),
        patch.object(routes_agent_v3, "ControllerEngine", controller_cls),
    ):
        app = FastAPI()
        app.include_router(routes_agent_v3.make_v3_agent_router())
        proxy = _PlanningTaskPlaneProxyServer(app)
        try:
            scenario_results: list[PlanningP0ScenarioResult] = []
            for index, scenario in enumerate(selected, start=1):
                scenario_id = str(scenario["scenario_id"])
                execution_mode = "unmocked_w4" if scenario_id in unmocked_set else "synthetic_w4"
                scenario_dir = out / scenario["scenario_id"]
                scenario_dir.mkdir(parents=True, exist_ok=True)
                attachment_path = scenario_dir / scenario["attachment_name"]
                attachment_path.write_text(str(scenario["attachment_text"]), encoding="utf-8")
                runtime_ctx = _runtime_ctx(scenario["scenario_id"], index=index, turn="p0")
                with ExitStack() as scenario_stack:
                    if execution_mode == "unmocked_w4":
                        scenario_stack.enter_context(
                            patch.object(
                                routes_agent_v3,
                                "_advisor_runtime",
                                lambda: SimpleNamespace(memory=object(), policy_engine=None, event_bus=None, observer=None),
                            )
                        )
                        scenario_stack.enter_context(
                            patch.object(
                                work_memory_manager.WorkMemoryManager,
                                "build_active_context",
                                _fake_unmocked_build_active_context,
                            )
                        )
                        scenario_stack.enter_context(
                            patch.object(
                                planning_runtime_pack_search,
                                "planning_runtime_pack_bundle_status",
                                _fake_unmocked_bundle_status,
                            )
                        )
                        scenario_stack.enter_context(
                            patch.object(
                                planning_runtime_pack_search,
                                "search_planning_runtime_pack",
                                _fake_unmocked_runtime_pack_search,
                            )
                        )
                        scenario_stack.enter_context(
                            patch.object(routes_agent_v3.MemoryCaptureService, "capture", _fake_unmocked_memory_capture)
                        )
                    else:
                        scenario_stack.enter_context(
                            patch.object(routes_agent_v3, "_maybe_apply_planning_knowledge_ingress", _fake_knowledge_ingress)
                        )
                        scenario_stack.enter_context(
                            patch.object(routes_agent_v3, "_maybe_writeback_planning_work_memory", _fake_memory_writeback)
                        )

                    turn = _execute_openclaw_plugin_tool(
                        base_url=proxy.base_url,
                        api_key="test-key",
                        plugin_source=DEFAULT_PLUGIN_SOURCE,
                        typebox_path=DEFAULT_TYPEBOX_PATH,
                        question=str(scenario["message"]),
                        goal_hint=str(scenario["goal_hint"]),
                        timeout_seconds=60,
                        context=_scenario_context(scenario, attachment_path),
                        runtime_ctx=runtime_ctx,
                        request_timeout_ms=30000,
                    )
                    turn_details = _tool_details(turn)
                    task_id = str(turn_details.get("task_id") or "").strip()
                    task_get = _execute_openclaw_plugin_tool(
                        base_url=proxy.base_url,
                        api_key="test-key",
                        plugin_source=DEFAULT_PLUGIN_SOURCE,
                        typebox_path=DEFAULT_TYPEBOX_PATH,
                        runtime_ctx=runtime_ctx,
                        request_timeout_ms=30000,
                        tool_name="openmind_advisor_task_get",
                        tool_params={"taskId": task_id},
                    )
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
                    task_details = _tool_details(task_get)
                    session_details = _tool_details(session_get)
                    checklist = _checklist_for(
                        scenario=scenario,
                        turn_details=turn_details,
                        task_details=task_details,
                        session_details=session_details,
                    )
                    (scenario_dir / "scenario_result.json").write_text(
                        json.dumps(
                            {
                                "execution_mode": execution_mode,
                                "turn": turn,
                                "task_get": task_get,
                                "session_get": session_get,
                                "checklist": checklist,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    scenario_results.append(
                        PlanningP0ScenarioResult(
                            scenario_id=scenario_id,
                            task_id=task_id,
                            task_type=str(scenario["task_type"]),
                            execution_mode=execution_mode,
                            checklist=checklist,
                            evidence_dir=str(scenario_dir),
                        )
                    )
        finally:
            proxy.close()

    overall_pass = all(all(item.checklist.values()) for item in scenario_results)
    manifest = {
        "ok": True,
        "overall_pass": overall_pass,
        "counts": {
            "scenarios": len(scenario_results),
            "passed": sum(1 for item in scenario_results if all(item.checklist.values())),
            "failed": sum(1 for item in scenario_results if not all(item.checklist.values())),
        },
        "scenario_ids": [item.scenario_id for item in scenario_results],
        "scope": {
            "openclaw_plugin_entry": True,
            "canonical_agent_v3_path": True,
            "p0_scenarios_only": True,
            "knowledge_ingress_visible": True,
            "memory_writeback_visible": True,
            "unified_checklist": list(UNIFIED_CHECKLIST),
            "unmocked_w4_scenarios": sorted(unmocked_set),
            "rate_limit_override": "OPENMIND_RATE_LIMIT=1000",
        },
        "scenario_results": [item.to_dict() for item in scenario_results],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report_v1.md").write_text(_render_report(manifest), encoding="utf-8")
    return manifest


def _render_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# Planning Task Plane P0 Acceptance Pack",
        "",
        f"- overall_pass: `{manifest['overall_pass']}`",
        f"- scenarios: `{manifest['counts']['scenarios']}`",
        f"- passed: `{manifest['counts']['passed']}`",
        f"- failed: `{manifest['counts']['failed']}`",
        f"- unified_checklist: `{', '.join(manifest['scope']['unified_checklist'])}`",
        "",
    ]
    for item in manifest["scenario_results"]:
        lines.extend(
            [
                f"## {item['scenario_id']}",
                "",
                f"- `task_id`: `{item['task_id']}`",
                f"- `task_type`: `{item['task_type']}`",
                f"- `execution_mode`: `{item['execution_mode']}`",
            ]
        )
        for key, value in item["checklist"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append(f"- `evidence_dir`: `{item['evidence_dir']}`")
        lines.append("")
    return "\n".join(lines)
