"""Dynamic admin-MCP compatibility gate for low-level provider tools."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from chatgptrest.integrations.mcp_http_client import (
    McpHttpClient,
    McpHttpInitializeHandshake,
    mcp_http_initialize_handshake,
)

DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
DEFAULT_SAMPLE_MESSAGE = (
    "请输出三条不重复的要点，说明 ChatgptREST 当前 scoped stack readiness 的含义、边界以及"
    "为什么这不等于 full-stack deployment proof。每条至少二十个字。"
)
EXPECTED_ADMIN_TOOLS = (
    "chatgptrest_gemini_ask_submit",
    "chatgptrest_job_wait",
    "chatgptrest_answer_get",
)


@dataclass
class AdminMcpProviderCompatibilityCheck:
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
class AdminMcpProviderCompatibilityGateReport:
    base_url: str
    mcp_url: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[AdminMcpProviderCompatibilityCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "mcp_url": self.mcp_url,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_admin_mcp_provider_compatibility_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    sample_message: str = DEFAULT_SAMPLE_MESSAGE,
) -> AdminMcpProviderCompatibilityGateReport:
    with _launch_admin_mcp_server(base_url=base_url, env_file=env_file) as mcp_url:
        initialize = _mcp_initialize_handshake(mcp_url)
        initialize_result = _mapping(initialize.result)
        server_info = _mapping(initialize_result.get("serverInfo"))
        client = _mcp_client(mcp_url)
        tool_names = [str(_mapping(item).get("name") or "") for item in _mcp_list_tools(client)]

        submit_result = _mcp_call_tool(
            client,
            tool_name="chatgptrest_gemini_ask_submit",
            tool_args={
                "idempotency_key": f"phase25-gemini-{uuid.uuid4().hex[:12]}",
                "question": sample_message,
                "preset": "auto",
                "min_chars": 80,
                "max_wait_seconds": 240,
                "notify_controller": False,
                "notify_done": False,
            },
            timeout_seconds=60.0,
        )
        job_id = str(submit_result.get("job_id") or "")

        wait_result = _mcp_call_tool(
            client,
            tool_name="chatgptrest_job_wait",
            tool_args={"job_id": job_id, "timeout_seconds": 240, "poll_seconds": 1},
            timeout_seconds=300.0,
        )

        answer_result = _mcp_call_tool(
            client,
            tool_name="chatgptrest_answer_get",
            tool_args={"job_id": job_id, "offset": 0, "max_chars": 4000},
            timeout_seconds=60.0,
        )

    checks = [
        _build_initialize_check(
            server_info=server_info,
            protocol_version=str(initialize_result.get("protocolVersion") or ""),
            mcp_session_id=str(initialize.session.session_id or ""),
        ),
        _build_tools_check(tool_names),
        _build_submit_check(submit_result),
        _build_wait_check(wait_result),
        _build_answer_check(answer_result),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return AdminMcpProviderCompatibilityGateReport(
        base_url=str(base_url).rstrip("/"),
        mcp_url=mcp_url,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "dynamic admin MCP streamable-http replay against the live 18711 API",
            "legacy low-level gemini submit + wait + answer compatibility",
            "replayed under an allowlisted MCP identity rather than proving a dedicated admin client name is allowlisted",
            "not a proof that admin MCP must be always-on as a systemd service",
            "not a direct chatgpt_web.ask execution proof",
            "not a public agent MCP proof",
        ],
    )


def render_admin_mcp_provider_compatibility_gate_markdown(report: AdminMcpProviderCompatibilityGateReport) -> str:
    lines = [
        "# Admin MCP Provider Compatibility Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- mcp_url: {report.mcp_url}",
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


def write_admin_mcp_provider_compatibility_gate_report(
    report: AdminMcpProviderCompatibilityGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_admin_mcp_provider_compatibility_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


@contextlib.contextmanager
def _launch_admin_mcp_server(*, base_url: str, env_file: Path) -> Iterator[str]:
    port = _free_port()
    env = os.environ.copy()
    env.update(_load_env_file(env_file))
    env.update(
        {
            "FASTMCP_HOST": "127.0.0.1",
            "FASTMCP_PORT": str(port),
            "CHATGPTREST_BASE_URL": str(base_url).rstrip("/"),
            "CHATGPTREST_CLIENT_NAME": "chatgptrest-mcp",
            "CHATGPTREST_CLIENT_INSTANCE": "phase25-admin-mcp",
            "CHATGPTREST_REQUEST_ID_PREFIX": "phase25-admin-mcp",
            "PYTHONPATH": ".",
        }
    )
    proc = subprocess.Popen(
        ["./.venv/bin/python", "chatgptrest_admin_mcp_server.py", "--transport", "streamable-http"],
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(port)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _build_initialize_check(
    *,
    server_info: dict[str, Any],
    protocol_version: str,
    mcp_session_id: str,
) -> AdminMcpProviderCompatibilityCheck:
    details = {
        "server_name": str(server_info.get("name") or ""),
        "protocol_version": protocol_version,
        "mcp_session_id": str(mcp_session_id or ""),
        "sessionful_http": bool(str(mcp_session_id or "").strip()),
    }
    expectations = {
        "server_name": "chatgptrest",
        "protocol_version": "2025-03-26",
        "sessionful_http": True,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return AdminMcpProviderCompatibilityCheck(
        name="dynamic_admin_mcp_initialize",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_tools_check(tool_names: list[str]) -> AdminMcpProviderCompatibilityCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for tool_name in EXPECTED_ADMIN_TOOLS:
        if tool_name not in tool_names:
            mismatches[tool_name] = {"expected": "present", "actual": "missing"}
    return AdminMcpProviderCompatibilityCheck(
        name="dynamic_admin_mcp_tools_list",
        passed=not mismatches,
        details={"tool_names": tool_names},
        mismatches=mismatches,
    )


def _build_submit_check(result: dict[str, Any]) -> AdminMcpProviderCompatibilityCheck:
    details = {
        "job_id": str(result.get("job_id") or ""),
        "kind": str(result.get("kind") or ""),
        "status": str(result.get("status") or ""),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["kind"] != "gemini_web.ask":
        mismatches["kind"] = {"expected": "gemini_web.ask", "actual": details["kind"]}
    if details["status"] not in {"queued", "in_progress", "completed"}:
        mismatches["status"] = {"expected": "queued|in_progress|completed", "actual": details["status"]}
    if not details["job_id"]:
        mismatches["job_id"] = {"expected": "non-empty", "actual": details["job_id"]}
    return AdminMcpProviderCompatibilityCheck(
        name="dynamic_admin_mcp_gemini_submit",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_wait_check(result: dict[str, Any]) -> AdminMcpProviderCompatibilityCheck:
    details = {"status": str(result.get("status") or ""), "kind": str(result.get("kind") or "")}
    expectations = {"status": "completed", "kind": "gemini_web.ask"}
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return AdminMcpProviderCompatibilityCheck(
        name="dynamic_admin_mcp_gemini_wait_completed",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_answer_check(result: dict[str, Any]) -> AdminMcpProviderCompatibilityCheck:
    details = {
        "chunk_nonempty": bool(str(result.get("chunk") or "").strip()),
        "done": bool(result.get("done") is True),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if not details["chunk_nonempty"]:
        mismatches["chunk_nonempty"] = {"expected": True, "actual": details["chunk_nonempty"]}
    return AdminMcpProviderCompatibilityCheck(
        name="dynamic_admin_mcp_gemini_answer_readable",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _parse_streamable_http_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    candidates: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except Exception:
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
    if not candidates:
        raise RuntimeError(f"unable to decode streamable-http json: {text[:400]}")
    return candidates[-1]


def _mcp_initialize_handshake(url: str) -> McpHttpInitializeHandshake:
    return mcp_http_initialize_handshake(
        url,
        client_name="phase25-admin-mcp-gate",
        client_version="1.0",
        protocol_version="2025-03-26",
        timeout_sec=30.0,
    )


def _mcp_client(url: str) -> McpHttpClient:
    return McpHttpClient(url=url, client_name="phase25-admin-mcp-gate", client_version="1.0")


def _mcp_list_tools(client: McpHttpClient) -> list[dict[str, Any]]:
    return client.list_tools(timeout_sec=30.0)


def _mcp_call_tool(
    client: McpHttpClient,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    return client.call_tool(tool_name=tool_name, tool_args=tool_args, timeout_sec=timeout_seconds)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, *, timeout_seconds: float = 25.0) -> None:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"admin MCP port did not open: {port}")


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
