"""Live completion and answer-quality gate for OpenClawBot planning task plane."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    DEFAULT_PLUGIN_SOURCE,
    DEFAULT_TYPEBOX_PATH,
    _execute_openclaw_plugin_tool,
    _load_openmind_api_key,
)
from chatgptrest.eval.planning_live_prompt_cases import select_planning_live_prompt_case


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
DEFAULT_REQUESTED_PROVIDER = "gemini"
DEFAULT_REQUESTED_PRESET = "auto"
DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS = 90
DEFAULT_TIMEOUT_SECONDS = 2700
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_SAME_SESSION_REPAIR_MAX_ATTEMPTS = 1
DEFAULT_MESSAGE = (
    "请严格依据附件整理三条下一步计划。"
    "要求：1）直接输出三条无序列表；2）每条一句；3）至少有一条直接处理附件中的当前项目卡点；"
    "4）不要写附件里没有出现的项目名、系统名、代码文件名。"
)
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "needs_followup", "needs_input"}
_LOCAL_TERMINAL_JOB_STATUSES = {"completed", "error", "cancelled", "failed", "needs_followup", "blocked", "cooldown"}


@dataclass
class OpenClawPlanningCompletionCheck:
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


@dataclass
class OpenClawPlanningLiveCompletionReport:
    base_url: str
    requested_provider: str
    session_id: str
    task_id: str
    terminal_status: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[OpenClawPlanningCompletionCheck]
    scope_boundary: list[str]
    prompt_case_id: str = ""
    requested_preset: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "requested_provider": self.requested_provider,
            "requested_preset": self.requested_preset,
            "prompt_case_id": self.prompt_case_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "terminal_status": self.terminal_status,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def _build_openclaw_planning_ask_tool_params(
    *,
    question: str,
    attachment_path: str,
    requested_provider: str,
    requested_preset: str = "",
    timeout_seconds: int,
    session_id: str = "",
    task_id: str = "",
    task_action: str = "",
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "planning_task_type": "planning_general",
        "files": [attachment_path],
        "requested_provider": requested_provider,
    }
    if str(requested_preset or "").strip():
        context["requested_preset"] = str(requested_preset).strip()
    if task_id:
        context["task_id"] = task_id
        context["planning_task_id"] = task_id
        context["logical_task_id"] = task_id
    if task_action:
        context["planning_task_action"] = task_action
    payload: dict[str, Any] = {
        "question": question,
        "goalHint": "planning",
        "timeoutSeconds": int(timeout_seconds),
        "context": context,
    }
    if session_id:
        payload["sessionId"] = session_id
    if task_id:
        payload["taskId"] = task_id
    if task_action:
        payload["taskAction"] = task_action
    return payload


def _same_session_repair_requested(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status") or "").strip()
    if status not in {"needs_followup", "needs_input"}:
        return False
    next_action = dict(payload.get("next_action") or {})
    return str(next_action.get("type") or "").strip() == "same_session_repair"


def _same_session_repair_retry_after_seconds(payload: dict[str, Any]) -> float:
    next_action = dict(payload.get("next_action") or {})
    raw = next_action.get("retry_after_seconds")
    try:
        value = float(raw)
    except Exception:
        return 0.0
    if not value > 0:
        return 0.0
    return max(0.0, min(value, 10.0))


def _execute_same_session_repair_turn(
    *,
    base_url: str,
    api_key: str,
    question: str,
    runtime_ctx: dict[str, Any],
    attachment_path: str,
    requested_provider: str,
    requested_preset: str,
    timeout_seconds: int,
    session_id: str,
    task_id: str,
) -> dict[str, Any]:
    return _execute_openclaw_plugin_tool(
        base_url=base_url,
        api_key=api_key,
        plugin_source=DEFAULT_PLUGIN_SOURCE,
        typebox_path=DEFAULT_TYPEBOX_PATH,
        runtime_ctx=runtime_ctx,
        timeout_seconds=max(30, int(timeout_seconds)),
        request_timeout_ms=(max(30, int(timeout_seconds)) * 1000) + 10000,
        tool_name="openmind_advisor_ask",
        tool_params=_build_openclaw_planning_ask_tool_params(
            question=question,
            attachment_path=attachment_path,
            requested_provider=requested_provider,
            requested_preset=requested_preset,
            timeout_seconds=max(30, int(timeout_seconds)),
            session_id=session_id,
            task_id=task_id,
            task_action="continue",
        ),
    )


def _local_jobdb_path() -> Path:
    raw = str(os.environ.get("CHATGPTREST_DB_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "state" / "jobdb.sqlite3").resolve()


def _local_agent_session_dir() -> Path:
    raw = str(os.environ.get("CHATGPTREST_AGENT_SESSION_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _local_jobdb_path().parent / "agent_sessions"


def _local_artifacts_dir() -> Path:
    raw = str(os.environ.get("CHATGPTREST_ARTIFACTS_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "artifacts").resolve()


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}


def _local_timeout_diagnostics(*, session_id: str) -> dict[str, Any]:
    if not session_id:
        return {}
    session_path = _local_agent_session_dir() / f"{session_id}.json"
    session_payload = _read_json_file(session_path) if session_path.exists() else {}
    job_id = str(session_payload.get("job_id") or "").strip()
    job_payload: dict[str, Any] = {}
    db_path = _local_jobdb_path()
    if job_id and db_path.exists():
        conn = None
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT job_id, status, phase, conversation_url, conversation_id, last_error, last_error_type, updated_at, not_before FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is not None:
                job_payload = dict(row)
        except Exception:
            job_payload = {}
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
    queue_wait_seconds = None
    if job_id:
        events_path = _local_artifacts_dir() / "jobs" / job_id / "events.jsonl"
        if events_path.exists():
            created_ts = None
            claimed_ts = None
            try:
                with events_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        event_type = str(event.get("type") or "").strip()
                        if event_type == "job_created" and created_ts is None:
                            created_ts = event.get("ts")
                        elif event_type == "claimed" and claimed_ts is None:
                            claimed_ts = event.get("ts")
                        if created_ts is not None and claimed_ts is not None:
                            break
                if created_ts is not None and claimed_ts is not None:
                    queue_wait_seconds = max(0.0, float(claimed_ts) - float(created_ts))
            except Exception:
                queue_wait_seconds = None
    details: dict[str, Any] = {}
    if session_payload:
        details["local_session_status"] = str(session_payload.get("status") or "").strip()
        details["local_session_job_id"] = job_id
        details["local_session_route"] = str(session_payload.get("route") or "").strip()
    if job_payload:
        details["local_job_status"] = str(job_payload.get("status") or "").strip()
        details["local_job_phase"] = str(job_payload.get("phase") or "").strip()
        details["local_job_error_type"] = str(job_payload.get("last_error_type") or "").strip()
    if queue_wait_seconds is not None:
        details["local_queue_wait_seconds"] = round(float(queue_wait_seconds), 3)
    return {key: value for key, value in details.items() if value not in (None, "", [])}


def run_openclawbot_planning_task_plane_live_completion_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    message: str = "",
    requested_provider: str = DEFAULT_REQUESTED_PROVIDER,
    requested_preset: str = DEFAULT_REQUESTED_PRESET,
    bootstrap_timeout_seconds: int = DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> OpenClawPlanningLiveCompletionReport:
    api_key = _load_openmind_api_key(env_file)
    runtime_ctx = _live_runtime_ctx("openclaw-live-planning-completion")
    if str(message or "").strip():
        prompt_case_id = "custom"
        selected_message = str(message or "").strip()
    else:
        prompt_case = select_planning_live_prompt_case("compact_next_steps")
        prompt_case_id = prompt_case.case_id
        selected_message = prompt_case.message
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(
            "# 材料\n"
            "- 当前项目卡点：供应链恢复窗口待确认。\n"
            "- 当前风险：在恢复窗口确认前，不能对客户承诺导入日期。\n"
            "- 本周必须推进的对象：供应商、销售、交付三方。\n"
            "- 输出约束：三条计划里至少有一条直接处理当前项目卡点，不要写附件里没有出现的项目名、系统名、代码文件名。\n"
        )
        attachment_path = handle.name

    try:
        ask_result = _execute_plugin_with_retry(
            base_url=str(base_url).rstrip("/"),
            api_key=api_key,
            question=selected_message,
            runtime_ctx=runtime_ctx,
            attachment_path=attachment_path,
            requested_provider=requested_provider,
            requested_preset=requested_preset,
            bootstrap_timeout_seconds=bootstrap_timeout_seconds,
        )
    except Exception as exc:
        return _error_report(
            base_url=str(base_url).rstrip("/"),
            requested_provider=str(requested_provider or "").strip(),
            requested_preset=str(requested_preset or "").strip(),
            prompt_case_id=prompt_case_id,
            error_text=str(exc),
        )
    ask_details = dict((ask_result.get("result") or {}).get("details") or {})
    session_id = str(ask_details.get("session_id") or "").strip()

    task_id = str(ask_details.get("task_id") or "").strip()
    same_session_repair_attempts = 0
    try:
        terminal_session = _wait_for_terminal_session(
            base_url=str(base_url).rstrip("/"),
            api_key=api_key,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        ) if session_id else {}
        while (
            session_id
            and same_session_repair_attempts < DEFAULT_SAME_SESSION_REPAIR_MAX_ATTEMPTS
            and _same_session_repair_requested(terminal_session)
        ):
            retry_after_seconds = _same_session_repair_retry_after_seconds(terminal_session)
            if retry_after_seconds > 0:
                time.sleep(retry_after_seconds)
            same_session_repair_attempts += 1
            repair_result = _execute_same_session_repair_turn(
                base_url=str(base_url).rstrip("/"),
                api_key=api_key,
                question=selected_message,
                runtime_ctx=runtime_ctx,
                attachment_path=attachment_path,
                requested_provider=requested_provider,
                requested_preset=requested_preset,
                timeout_seconds=max(30, min(int(bootstrap_timeout_seconds), 180)),
                session_id=session_id,
                task_id=task_id,
            )
            repair_details = dict((repair_result.get("result") or {}).get("details") or {})
            session_id = str(repair_details.get("session_id") or session_id).strip() or session_id
            task_id = str(repair_details.get("task_id") or task_id).strip() or task_id
            terminal_session = _wait_for_terminal_session(
                base_url=str(base_url).rstrip("/"),
                api_key=api_key,
                session_id=session_id,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            ) if session_id else {}
        terminal_status = str(terminal_session.get("status") or "")
        terminal_next_action = dict(terminal_session.get("next_action") or {})
        terminal_provenance = dict(terminal_session.get("provenance") or {})
        last_answer = str(terminal_session.get("last_answer") or "")

        task_list_result = _execute_openclaw_plugin_tool(
            base_url=str(base_url).rstrip("/"),
            api_key=api_key,
            plugin_source=DEFAULT_PLUGIN_SOURCE,
            typebox_path=DEFAULT_TYPEBOX_PATH,
            runtime_ctx=runtime_ctx,
            request_timeout_ms=60000,
            tool_name="openmind_advisor_task_list",
            tool_params={"taskType": "planning_general", "limit": 10},
        )
        task_list_details = dict((task_list_result.get("result") or {}).get("details") or {})
        task_items = [dict(item) for item in list(task_list_details.get("planning_tasks") or []) if isinstance(item, dict)]
        if not task_id and task_items:
            task_id = str(task_items[0].get("task_id") or "").strip()

        task_get_result = {}
        task_get_details: dict[str, Any] = {}
        planning_task: dict[str, Any] = {}
        checkpoint: dict[str, Any] = {}
        if task_id:
            task_get_result = _execute_openclaw_plugin_tool(
                base_url=str(base_url).rstrip("/"),
                api_key=api_key,
                plugin_source=DEFAULT_PLUGIN_SOURCE,
                typebox_path=DEFAULT_TYPEBOX_PATH,
                runtime_ctx=runtime_ctx,
                request_timeout_ms=60000,
                tool_name="openmind_advisor_task_get",
                tool_params={"taskId": task_id},
            )
            task_get_details = dict((task_get_result.get("result") or {}).get("details") or {})
            planning_task = dict(task_get_details.get("planning_task") or {})
            checkpoint = dict(planning_task.get("checkpoint") or {})
    except Exception as exc:
        local_timeout_details = _local_timeout_diagnostics(session_id=session_id)
        error_text = str(exc)
        if local_timeout_details:
            error_text = (
                f"{error_text} | local_session_status={local_timeout_details.get('local_session_status') or ''} "
                f"local_job_status={local_timeout_details.get('local_job_status') or ''} "
                f"local_job_phase={local_timeout_details.get('local_job_phase') or ''} "
                f"local_job_error_type={local_timeout_details.get('local_job_error_type') or ''} "
                f"local_queue_wait_seconds={local_timeout_details.get('local_queue_wait_seconds') or ''}"
            ).strip()
        return _probe_error_report(
            base_url=str(base_url).rstrip("/"),
            requested_provider=str(requested_provider or "").strip(),
            requested_preset=str(requested_preset or "").strip(),
            prompt_case_id=prompt_case_id,
            session_id=session_id,
            task_id=task_id,
            error_text=error_text,
        )

    bullet_count = _count_bullet_lines(last_answer)
    completed = terminal_status == "completed"
    actionable_repair = (
        terminal_status in {"needs_followup", "needs_input"}
        and str(terminal_next_action.get("type") or "").strip() in {"same_session_repair", "await_user_clarification", "await_workspace_patch"}
    )
    provider_selection = dict(terminal_provenance.get("provider_selection") or {})
    expected_task_status = _public_task_status(terminal_status)

    checks = [
        _build_check(
            name="openclaw_live_terminal_observable",
            details={
                "session_id": session_id,
                "terminal_status": terminal_status,
                "route": str(terminal_provenance.get("route") or ""),
                "final_provider": str(terminal_provenance.get("final_provider") or ""),
                "provider_request_honored": bool(provider_selection.get("request_honored")),
                "requested_preset": str(provider_selection.get("requested_preset") or ""),
                "same_session_repair_attempts": same_session_repair_attempts,
            },
            expectations=(
                {
                    "provider_request_honored": True,
                    **({"requested_preset": str(requested_preset or "").strip()} if str(requested_preset or "").strip() else {}),
                }
                if requested_provider
                else {}
            ),
            required_nonempty=("session_id", "terminal_status"),
            allow_values={"terminal_status": _TERMINAL_STATUSES},
        ),
        _build_check(
            name="planning_task_visible_after_terminal",
            details={
                "listed_count": int(task_list_details.get("count") or 0),
                "task_id": task_id,
                "task_type": str(planning_task.get("task_type") or (task_items[0].get("task_type") if task_items else "")),
                "latest_session_id": str(planning_task.get("latest_session_id") or ""),
            },
            expectations={
                "task_type": "planning_general",
                "latest_session_id": session_id,
            },
            required_nonempty=("task_id",),
            minimums={"listed_count": 1},
        ),
        _build_check(
            name="planning_checkpoint_terminal_alignment",
            details={
                "task_status": str(planning_task.get("status") or ""),
                "checkpoint_state": str(checkpoint.get("current_state") or ""),
                "checkpoint_status": str(checkpoint.get("current_status") or ""),
                "attachment_captured": attachment_path in list(checkpoint.get("source_materials") or []),
            },
            expectations={
                "task_status": expected_task_status,
                "checkpoint_state": terminal_status,
                "checkpoint_status": terminal_status,
                "attachment_captured": True,
            },
            required_nonempty=("task_status", "checkpoint_state", "checkpoint_status"),
        ),
        _build_check(
            name="final_completion_ok",
            details={
                "terminal_status": terminal_status,
                "answer_chars": len(last_answer),
                "checkpoint_latest_output_chars": len(str(checkpoint.get("latest_output") or "")),
            },
            expectations={"terminal_status": "completed"},
            minimums={"answer_chars": 30, "checkpoint_latest_output_chars": 30},
        ),
        _build_check(
            name="answer_quality_ok",
            details={
                "terminal_status": terminal_status,
                "bullet_count": bullet_count,
                "answer_contains_attachment_fact": _contains_attachment_fact(last_answer),
                "answer_has_three_steps_shape": bullet_count >= 3,
            },
            expectations={
                "terminal_status": "completed",
                "answer_contains_attachment_fact": True,
                "answer_has_three_steps_shape": True,
            },
        ),
        _build_check(
            name="actionable_fail_closed_if_not_completed",
            details={
                "terminal_status": terminal_status,
                "next_action_type": str(terminal_next_action.get("type") or ""),
                "actionable_repair": actionable_repair,
                "same_session_repair_attempts": same_session_repair_attempts,
            },
            expectations={"actionable_repair": True} if not completed else {},
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return OpenClawPlanningLiveCompletionReport(
        base_url=str(base_url).rstrip("/"),
        requested_provider=str(requested_provider or "").strip(),
        requested_preset=str(requested_preset or "").strip(),
        prompt_case_id=prompt_case_id,
        session_id=session_id,
        task_id=task_id,
        terminal_status=terminal_status,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "live OpenClaw plugin entry against the integrated 18711 host",
            "proves a terminal planning session state after real provider execution",
            "requires completed status for final-completion and answer-quality pass",
            "still records actionable fail-closed repair when the provider does not complete",
            "runner defaults to requested_provider=gemini unless explicitly overridden",
            "runner defaults to requested_preset=auto so live validation does not rely on pro-only Gemini presets",
            f"live prompt case rotates via {prompt_case_id or 'custom'} to avoid reusing one canonical question",
            f"bootstrap ask is hard-capped to {int(bootstrap_timeout_seconds)}s before fail-closed",
        ],
    )


def render_openclawbot_planning_task_plane_live_completion_markdown(
    report: OpenClawPlanningLiveCompletionReport,
) -> str:
    lines = [
        "# OpenClawBot Planning Task Plane Live Completion Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- requested_provider: {report.requested_provider}",
        f"- requested_preset: {report.requested_preset}",
        f"- prompt_case_id: {report.prompt_case_id}",
        f"- session_id: {report.session_id}",
        f"- task_id: {report.task_id}",
        f"- terminal_status: {report.terminal_status}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{key}={value}" for key, value in check.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    lines.append("")
    lines.append("## Scope Boundary")
    lines.append("")
    for item in report.scope_boundary:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_openclawbot_planning_task_plane_live_completion_report(
    report: OpenClawPlanningLiveCompletionReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_openclawbot_planning_task_plane_live_completion_markdown(report), encoding="utf-8")
    return json_path, md_path


def _is_retryable_terminal_probe_error(error: Exception) -> bool:
    text = str(error or "").strip().lower()
    return any(
        marker in text
        for marker in (
            "connection refused",
            "connection reset by peer",
            "remote end closed connection",
            "timed out",
            "temporarily unavailable",
            "socket hang up",
        )
    )


def _wait_for_terminal_session(
    *,
    base_url: str,
    api_key: str,
    session_id: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + max(30.0, float(timeout_seconds))
    while True:
        try:
            snapshot = _request_json(f"{base_url}/v3/agent/session/{session_id}", api_key=api_key)
        except Exception as exc:
            now = time.time()
            if (not _is_retryable_terminal_probe_error(exc)) or now >= deadline:
                raise RuntimeError(
                    f"terminal_probe_transport_failed session_id={session_id} error={str(exc or '').strip()}"
                ) from exc
            time.sleep(max(0.5, min(float(poll_seconds), max(0.5, deadline - now))))
            continue
        status = str(snapshot.get("status") or "").strip().lower()
        if status in _TERMINAL_STATUSES:
            return snapshot
        now = time.time()
        if now >= deadline:
            raise RuntimeError(
                f"terminal_wait_timeout status={status or '(empty)'} session_id={session_id}"
            )
        time.sleep(max(0.5, min(float(poll_seconds), max(0.5, deadline - now))))


def _request_json(url: str, *, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "X-Api-Key": api_key,
            "X-Client-Name": "openclaw-advisor",
            "X-Client-Instance": "openclaw-live-completion-gate",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _count_bullet_lines(answer: str) -> int:
    markers = ("- ", "* ", "1.", "2.", "3.", "1、", "2、", "3、", "①", "②", "③")
    count = 0
    for raw in str(answer or "").splitlines():
        line = raw.strip()
        if any(line.startswith(marker) for marker in markers):
            count += 1
    return count


def _public_task_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "completed":
        return "completed"
    if normalized in {"needs_followup", "needs_input"}:
        return "awaiting_input"
    if normalized == "failed":
        return "needs_attention"
    if normalized == "cancelled":
        return "cancelled"
    return "active"


def _build_check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any],
    required_nonempty: tuple[str, ...] = (),
    allow_values: dict[str, set[str]] | None = None,
    minimums: dict[str, int] | None = None,
) -> OpenClawPlanningCompletionCheck:
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
    for field_name, minimum in dict(minimums or {}).items():
        actual = int(details.get(field_name) or 0)
        if actual < minimum:
            mismatches[field_name] = {"expected": f">={minimum}", "actual": actual}
    return OpenClawPlanningCompletionCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _escape_pipe(value: str) -> str:
    return str(value).replace("|", "\\|")


def _contains_attachment_fact(answer: str) -> bool:
    text = str(answer or "").strip()
    if not text:
        return False
    return bool(re.search(r"供应链(?:的)?恢复(?:时间)?(?:的具体)?窗口", text))


def _execute_plugin_with_retry(
    *,
    base_url: str,
    api_key: str,
    question: str,
    runtime_ctx: dict[str, Any],
    attachment_path: str,
    requested_provider: str,
    requested_preset: str,
    bootstrap_timeout_seconds: int,
) -> dict[str, Any]:
    effective_timeout_seconds = max(30, min(int(bootstrap_timeout_seconds), 180))
    attempts: list[str] = []
    for attempt in range(2):
        try:
            return _execute_openclaw_plugin_tool(
                base_url=base_url,
                api_key=api_key,
                plugin_source=DEFAULT_PLUGIN_SOURCE,
                typebox_path=DEFAULT_TYPEBOX_PATH,
                runtime_ctx=runtime_ctx,
                timeout_seconds=effective_timeout_seconds,
                request_timeout_ms=(effective_timeout_seconds * 1000) + 10000,
                tool_name="openmind_advisor_ask",
                tool_params=_build_openclaw_planning_ask_tool_params(
                    question=question,
                    attachment_path=attachment_path,
                    requested_provider=requested_provider,
                    requested_preset=requested_preset,
                    timeout_seconds=effective_timeout_seconds,
                ),
            )
        except Exception as exc:  # pragma: no cover - exercised through _error_report path
            attempts.append(str(exc))
            if attempt >= 1:
                raise RuntimeError(" | ".join(attempts)) from exc
            time.sleep(2.0)
    raise RuntimeError("unexpected_retry_exhausted")


def _error_report(
    *,
    base_url: str,
    requested_provider: str,
    requested_preset: str,
    prompt_case_id: str,
    error_text: str,
) -> OpenClawPlanningLiveCompletionReport:
    check = _build_check(
        name="openclaw_live_completion_gate_bootstrap",
        details={"error": str(error_text or "").strip()},
        expectations={},
        required_nonempty=(),
    )
    check.passed = False
    check.mismatches = {"error": {"expected": "successful live ask bootstrap", "actual": str(error_text or "").strip()}}
    return OpenClawPlanningLiveCompletionReport(
        base_url=base_url,
        requested_provider=requested_provider,
        session_id="",
        task_id="",
        terminal_status="ask_failed",
        num_checks=1,
        num_passed=0,
        num_failed=1,
        checks=[check],
        scope_boundary=[
            "live OpenClaw plugin entry against the integrated 18711 host",
            "fail-closed report emitted even when the initial live ask bootstrap fails",
            "this report means completion evidence was not obtained",
        ],
        prompt_case_id=prompt_case_id,
        requested_preset=requested_preset,
    )


def _probe_error_report(
    *,
    base_url: str,
    requested_provider: str,
    requested_preset: str,
    prompt_case_id: str,
    session_id: str,
    task_id: str,
    error_text: str,
) -> OpenClawPlanningLiveCompletionReport:
    check = _build_check(
        name="openclaw_live_completion_gate_probe",
        details={
            "session_id": str(session_id or "").strip(),
            "task_id": str(task_id or "").strip(),
            "error": str(error_text or "").strip(),
        },
        expectations={},
    )
    check.passed = False
    check.mismatches = {"error": {"expected": "successful terminal probe and planning visibility checks", "actual": str(error_text or "").strip()}}
    return OpenClawPlanningLiveCompletionReport(
        base_url=base_url,
        requested_provider=requested_provider,
        session_id=str(session_id or "").strip(),
        task_id=str(task_id or "").strip(),
        terminal_status="probe_failed",
        num_checks=1,
        num_passed=0,
        num_failed=1,
        checks=[check],
        scope_boundary=[
            "live OpenClaw plugin entry against the integrated 18711 host",
            "fail-closed report emitted when terminal polling or planning visibility probes fail after bootstrap",
            "this report means the live completion chain did not produce reliable terminal evidence",
        ],
        prompt_case_id=prompt_case_id,
        requested_preset=requested_preset,
    )


def _live_runtime_ctx(prefix: str) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return {
        "sessionKey": f"{prefix}-session-{suffix}",
        "sessionId": f"{prefix}-thread-{suffix}",
        "agentAccountId": f"acct-{prefix}-{suffix}",
        "agentId": "openclawbot",
    }
