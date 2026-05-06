"""Scoped direct-provider execution gate for low-level /v1/jobs paths."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.public_auth_trace_gate import _load_tokens


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
DEFAULT_GEMINI_PROMPT = (
    "请输出三条不重复的要点，说明 ChatgptREST 当前 scoped stack readiness 的含义、边界以及"
    "为什么这不等于 full-stack deployment proof。每条至少二十个字。"
)
DEFAULT_CHATGPT_PROMPT = "请用两点概括 ChatgptREST 当前 scoped stack readiness 的结论与边界。"
DEFAULT_BLOCKED_CLIENT_NAME = "chatgptrestctl"
DEFAULT_MAINT_CLIENT_NAME = "chatgptrestctl-maint"


@dataclass
class DirectProviderExecutionCheck:
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
class DirectProviderExecutionGateReport:
    base_url: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[DirectProviderExecutionCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_direct_provider_execution_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
) -> DirectProviderExecutionGateReport:
    auth_header = _build_v1_jobs_auth_header(_load_tokens(env_file))

    blocked = _post_job(
        base_url=base_url,
        auth_header=auth_header,
        kind="chatgpt_web.ask",
        question=DEFAULT_CHATGPT_PROMPT,
        params={"preset": "auto", "timeout_seconds": 180, "max_wait_seconds": 240, "min_chars": 80, "answer_format": "markdown"},
        trace_suffix="chatgpt-blocked",
        client_name=DEFAULT_BLOCKED_CLIENT_NAME,
    )
    gemini_submit = _post_job(
        base_url=base_url,
        auth_header=auth_header,
        kind="gemini_web.ask",
        question=DEFAULT_GEMINI_PROMPT,
        params={"preset": "auto", "timeout_seconds": 180, "max_wait_seconds": 240, "min_chars": 80, "answer_format": "markdown"},
        trace_suffix="gemini-submit",
        client_name=DEFAULT_MAINT_CLIENT_NAME,
    )
    gemini_job_id = str(((gemini_submit.get("body") or {}) if isinstance(gemini_submit.get("body"), dict) else {}).get("job_id") or "")
    gemini_final = _wait_for_job(base_url=base_url, auth_header=auth_header, job_id=gemini_job_id) if gemini_job_id else {}
    gemini_answer = _get_answer_chunk(base_url=base_url, auth_header=auth_header, job_id=gemini_job_id) if gemini_job_id else {}

    checks = [
        _build_chatgpt_block_check(blocked),
        _build_gemini_submit_check(gemini_submit),
        _build_gemini_delivery_check(gemini_final, gemini_answer),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return DirectProviderExecutionGateReport(
        base_url=str(base_url).rstrip("/"),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "live low-level /v1/jobs policy block for coding-agent direct chatgpt_web.ask",
            "live low-level /v1/jobs delivery proof for maintenance-only gemini_web.ask",
            "not a proof that coding agents should use low-level /v1/jobs ask paths",
            "not a qwen or full generic-provider matrix",
            "not a full-stack deployment proof",
        ],
    )


def render_direct_provider_execution_gate_markdown(report: DirectProviderExecutionGateReport) -> str:
    lines = [
        "# Direct Provider Execution Gate Report",
        "",
        f"- base_url: {report.base_url}",
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


def write_direct_provider_execution_gate_report(
    report: DirectProviderExecutionGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_direct_provider_execution_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_chatgpt_block_check(response: dict[str, Any]) -> DirectProviderExecutionCheck:
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
    details = {
        "http_status": int(response.get("status_code") or 0),
        "error": str(detail.get("error") or body.get("error") or ""),
        "x_client_name": str(detail.get("x_client_name") or ""),
    }
    expectations = {
        "http_status": 403,
        "error": "direct_live_chatgpt_ask_blocked",
        "x_client_name": DEFAULT_BLOCKED_CLIENT_NAME,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return DirectProviderExecutionCheck(
        name="direct_chatgpt_low_level_blocked",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_gemini_submit_check(response: dict[str, Any]) -> DirectProviderExecutionCheck:
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    details = {
        "http_status": int(response.get("status_code") or 0),
        "job_id": str(body.get("job_id") or ""),
        "kind": str(body.get("kind") or ""),
        "status": str(body.get("status") or ""),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["http_status"] != 200:
        mismatches["http_status"] = {"expected": 200, "actual": details["http_status"]}
    if details["kind"] != "gemini_web.ask":
        mismatches["kind"] = {"expected": "gemini_web.ask", "actual": details["kind"]}
    if details["status"] not in {"queued", "in_progress", "completed"}:
        mismatches["status"] = {"expected": "queued|in_progress|completed", "actual": details["status"]}
    if not details["job_id"]:
        mismatches["job_id"] = {"expected": "non-empty", "actual": details["job_id"]}
    return DirectProviderExecutionCheck(
        name="direct_gemini_submission_accepted",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_gemini_delivery_check(job: dict[str, Any], answer: dict[str, Any]) -> DirectProviderExecutionCheck:
    details = {
        "final_status": str(job.get("status") or ""),
        "kind": str(job.get("kind") or ""),
        "answer_nonempty": bool(str(answer.get("chunk") or "").strip()),
        "answer_done": bool(answer.get("done") is True),
    }
    expectations = {
        "final_status": "completed",
        "kind": "gemini_web.ask",
        "answer_nonempty": True,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return DirectProviderExecutionCheck(
        name="direct_gemini_delivery_completed",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _post_job(
    *,
    base_url: str,
    auth_header: dict[str, str],
    kind: str,
    question: str,
    params: dict[str, Any],
    trace_suffix: str,
    client_name: str,
) -> dict[str, Any]:
    request_id = f"phase24-{trace_suffix}-{uuid.uuid4().hex[:10]}"
    idem_key = f"phase24-{trace_suffix}-{uuid.uuid4().hex[:12]}"
    payload = {
        "kind": str(kind),
        "input": {"question": str(question)},
        "params": dict(params),
        "client": {"name": str(client_name)},
    }
    request = urllib.request.Request(
        str(base_url).rstrip("/") + "/v1/jobs",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": idem_key,
            "X-Client-Name": str(client_name),
            "X-Client-Instance": f"phase24-{trace_suffix}",
            "X-Request-ID": request_id,
            **auth_header,
        },
        method="POST",
    )
    return _request_json(request)


def _wait_for_job(*, base_url: str, auth_header: dict[str, str], job_id: str, timeout_seconds: int = 300) -> dict[str, Any]:
    if not str(job_id or "").strip():
        return {}
    request = urllib.request.Request(
        str(base_url).rstrip("/") + f"/v1/jobs/{urllib.parse.quote(str(job_id))}/wait?timeout_seconds={int(timeout_seconds)}&poll_seconds=1&auto_wait_cooldown=1",
        headers=dict(auth_header),
        method="GET",
    )
    response = _request_json(request, timeout_seconds=float(timeout_seconds) + 30.0)
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    return body if isinstance(body, dict) else {}


def _get_answer_chunk(*, base_url: str, auth_header: dict[str, str], job_id: str) -> dict[str, Any]:
    if not str(job_id or "").strip():
        return {}
    request = urllib.request.Request(
        str(base_url).rstrip("/") + f"/v1/jobs/{urllib.parse.quote(str(job_id))}/answer?offset=0&max_chars=4000",
        headers=dict(auth_header),
        method="GET",
    )
    response = _request_json(request)
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    return body if isinstance(body, dict) else {}


def _request_json(request: urllib.request.Request, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:
            status_code = int(getattr(resp, "status", resp.getcode()) or 200)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
    body = json.loads(raw) if raw.strip() else {}
    return {
        "status_code": status_code,
        "body": body if isinstance(body, dict) else {"_raw": raw},
    }


def _build_v1_jobs_auth_header(tokens: dict[str, str]) -> dict[str, str]:
    bearer = str(tokens.get("CHATGPTREST_API_TOKEN") or os.environ.get("CHATGPTREST_API_TOKEN") or "").strip()
    if bearer:
        return {"Authorization": f"Bearer {bearer}"}
    raise RuntimeError("no CHATGPTREST_API_TOKEN available for /v1/jobs direct provider gate")


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
