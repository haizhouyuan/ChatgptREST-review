#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    DEFAULT_API_BASE_URL,
    DEFAULT_ENV_FILE,
    DEFAULT_PLUGIN_SOURCE,
    DEFAULT_TYPEBOX_PATH,
    _execute_openclaw_plugin_tool,
    _load_openmind_api_key,
)
from chatgptrest.eval.openclawbot_planning_task_plane_live_gate import _live_runtime_ctx


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "visit_cooperation_prep_live_gate"
DEFAULT_MESSAGE = (
    "杭州资本刚才联系到哲源这边，下周一或周二准备带钛虎机器人董事长一行来拜访，"
    "核心洽谈机器人关节模组业务合作的可行性。我也要提前做准备，详细了解一下这家公司并准备建议回复。"
)


@dataclass
class LiveCheck:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


def _check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any] = {},
    required_nonempty: tuple[str, ...] = (),
    allow_values: dict[str, set[str]] | None = None,
) -> LiveCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name in required_nonempty:
        if not details.get(field_name):
            mismatches[field_name] = {"expected": "non-empty", "actual": details.get(field_name)}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    for field_name, allowed in dict(allow_values or {}).items():
        actual = str(details.get(field_name) or "")
        if actual not in allowed:
            mismatches[field_name] = {"expected": sorted(allowed), "actual": actual}
    return LiveCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def run_live_gate(
    *,
    base_url: str,
    env_file: Path,
    plugin_source: Path,
    typebox_path: Path,
    output_root: Path,
    message: str,
) -> dict[str, Any]:
    api_key = _load_openmind_api_key(env_file)
    runtime_ctx = _live_runtime_ctx("visit-cooperation-live-gate")
    ask_result = _execute_openclaw_plugin_tool(
        base_url=str(base_url).rstrip("/"),
        api_key=api_key,
        plugin_source=plugin_source,
        typebox_path=typebox_path,
        question=message,
        goal_hint="planning",
        timeout_seconds=120,
        context={"planning_task_type": "planning_general"},
        runtime_ctx=runtime_ctx,
        request_timeout_ms=180000,
    )
    details = dict((ask_result.get("result") or {}).get("details") or {})
    scenario_pack = dict(details.get("scenario_pack") or {})
    control_plane = dict(details.get("control_plane") or {})
    execution_layer = dict(control_plane.get("execution_layer") or {})
    quality_gate = dict(details.get("quality_gate") or {})
    next_action = dict(details.get("next_action") or {})

    checks = [
        _check(
            name="live_visit_request_accepted",
            details={
                "status": str(details.get("status") or ""),
                "session_id": str(details.get("session_id") or ""),
                "task_id": str(details.get("task_id") or ""),
            },
            required_nonempty=("status", "session_id", "task_id"),
            allow_values={"status": {"running", "completed", "needs_followup"}},
        ),
        _check(
            name="live_visit_profile_selected",
            details={
                "profile": str(scenario_pack.get("profile") or ""),
                "route_hint": str(scenario_pack.get("route_hint") or ""),
            },
            expectations={"profile": "visit_cooperation_prep", "route_hint": "report"},
        ),
        _check(
            name="live_visit_coding_lane_selected",
            details={
                "execution_lane": str(execution_layer.get("execution_lane") or ""),
                "selected_executor": str(execution_layer.get("selected_executor") or ""),
                "automatic_default": bool(execution_layer.get("automatic_default")),
            },
            expectations={"execution_lane": "coding_agent", "selected_executor": "codex", "automatic_default": True},
        ),
        _check(
            name="live_visit_closure_contract_visible",
            details={
                "required_sections": list(quality_gate.get("required_sections") or []),
                "next_action_type": str(next_action.get("type") or ""),
            },
            expectations={
                "required_sections": [
                    "quick_judgment",
                    "visit_purpose",
                    "counterparty_focus",
                    "prep_checklist",
                    "confirmation_items",
                    "suggested_reply",
                    "next_steps",
                ]
            },
        ),
    ]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": all(item.passed for item in checks),
        "base_url": str(base_url).rstrip("/"),
        "message": message,
        "session_id": str(details.get("session_id") or ""),
        "task_id": str(details.get("task_id") or ""),
        "checks": [item.to_dict() for item in checks],
        "raw_result": ask_result,
    }
    (run_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Visit Cooperation Prep Live Gate",
        "",
        f"- `ok`: `{payload['ok']}`",
        f"- `session_id`: `{payload['session_id']}`",
        f"- `task_id`: `{payload['task_id']}`",
        "",
        "| Check | Pass | Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for item in checks:
        details_text = ", ".join(f"{k}={v}" for k, v in item.details.items()) or "-"
        mismatch_text = "; ".join(
            f"{k}: expected={v['expected']} actual={v['actual']}" for k, v in item.mismatches.items()
        ) or "-"
        escaped_details = details_text.replace("|", "\\|")
        escaped_mismatch = mismatch_text.replace("|", "\\|")
        lines.append(
            f"| {item.name} | {'yes' if item.passed else 'no'} | {escaped_details} | {escaped_mismatch} |"
        )
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["artifacts"] = {
        "report_json": str(run_dir / "report.json"),
        "report_md": str(run_dir / "report.md"),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live OpenClaw visit/cooperation-prep gate.")
    parser.add_argument("--base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--plugin-source", default=str(DEFAULT_PLUGIN_SOURCE))
    parser.add_argument("--typebox-path", default=str(DEFAULT_TYPEBOX_PATH))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    args = parser.parse_args()
    payload = run_live_gate(
        base_url=str(args.base_url),
        env_file=Path(args.env_file),
        plugin_source=Path(args.plugin_source),
        typebox_path=Path(args.typebox_path),
        output_root=Path(args.output_root),
        message=str(args.message),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
