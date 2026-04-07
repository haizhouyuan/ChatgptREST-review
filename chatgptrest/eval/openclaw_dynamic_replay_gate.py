"""Dynamic OpenClaw plugin replay gate for public advisor ingress."""

from __future__ import annotations

import json
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
DEFAULT_PLUGIN_SOURCE = Path(__file__).resolve().parents[2] / "openclaw_extensions" / "openmind-advisor" / "index.ts"
DEFAULT_TYPEBOX_PATH = Path(
    "/vol1/1000/projects/openclaw/node_modules/.pnpm/@sinclair+typebox@0.34.48/node_modules/@sinclair/typebox"
)
DEFAULT_TSX_BIN = Path("/vol1/1000/projects/openclaw/node_modules/.bin/tsx")
DEFAULT_SAMPLE_MESSAGE = "请总结面试纪要"


@dataclass
class OpenClawDynamicReplayCheck:
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
class OpenClawDynamicReplayReport:
    base_url: str
    plugin_source: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[OpenClawDynamicReplayCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "plugin_source": self.plugin_source,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
        }


def run_openclaw_dynamic_replay_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    plugin_source: Path = DEFAULT_PLUGIN_SOURCE,
    typebox_path: Path = DEFAULT_TYPEBOX_PATH,
) -> OpenClawDynamicReplayReport:
    fake_capture = _run_contract_capture_replay(plugin_source=plugin_source, typebox_path=typebox_path)
    live_replay = _run_live_replay(
        base_url=base_url,
        env_file=env_file,
        plugin_source=plugin_source,
        typebox_path=typebox_path,
    )
    checks = [
        _build_registration_check(fake_capture),
        _build_contract_capture_check(fake_capture),
        _build_live_replay_check(live_replay),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return OpenClawDynamicReplayReport(
        base_url=str(base_url).rstrip("/"),
        plugin_source=str(plugin_source),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_openclaw_dynamic_replay_report_markdown(report: OpenClawDynamicReplayReport) -> str:
    lines = [
        "# OpenClaw Dynamic Replay Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- plugin_source: {report.plugin_source}",
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
            f"{key}: expected={value['expected']} actual={value['actual']}" for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_openclaw_dynamic_replay_report(
    report: OpenClawDynamicReplayReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_openclaw_dynamic_replay_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_registration_check(replay: dict[str, Any]) -> OpenClawDynamicReplayCheck:
    tool_names = [str(item) for item in replay.get("tool_names") or []]
    mismatches: dict[str, dict[str, Any]] = {}
    if "openmind_advisor_ask" not in tool_names:
        mismatches["tool_names"] = {"expected": "contains openmind_advisor_ask", "actual": tool_names}
    return OpenClawDynamicReplayCheck(
        name="dynamic_tool_registration",
        passed=not mismatches,
        details={"tool_names": tool_names},
        mismatches=mismatches,
    )


def _build_contract_capture_check(replay: dict[str, Any]) -> OpenClawDynamicReplayCheck:
    request = replay.get("captured_request") or {}
    headers = {str(key).lower(): str(value) for key, value in (request.get("headers") or {}).items()}
    body = request.get("body") or {}
    task_intake = body.get("task_intake") if isinstance(body, dict) else {}
    task_intake = task_intake if isinstance(task_intake, dict) else {}
    available_inputs = task_intake.get("available_inputs") if isinstance(task_intake, dict) else {}
    available_inputs = available_inputs if isinstance(available_inputs, dict) else {}
    details = {
        "request_path": str(request.get("path") or ""),
        "http_method": str(request.get("method") or ""),
        "x_client_name": headers.get("x-client-name", ""),
        "x_client_instance_prefix": headers.get("x-client-instance", "").startswith("openclaw-advisor:"),
        "x_request_id_prefix": headers.get("x-request-id", "").startswith("openclaw-advisor-"),
        "source": str(body.get("source") or ""),
        "body_session_id": str(body.get("session_id") or ""),
        "body_user_id": str(body.get("user_id") or ""),
        "task_spec_version": str(task_intake.get("spec_version") or ""),
        "task_source": str(task_intake.get("source") or ""),
        "task_ingress_lane": str(task_intake.get("ingress_lane") or ""),
        "task_scenario": str(task_intake.get("scenario") or ""),
        "task_output_shape": str(task_intake.get("output_shape") or ""),
        "task_session_id": str(task_intake.get("session_id") or ""),
        "task_account_id": str(task_intake.get("account_id") or ""),
        "task_thread_id": str(task_intake.get("thread_id") or ""),
        "task_agent_id": str(task_intake.get("agent_id") or ""),
        "attachments_count": len(list(task_intake.get("attachments") or [])),
        "available_input_files_count": len(list(available_inputs.get("files") or [])),
    }
    expectations = {
        "request_path": "/v3/agent/turn",
        "http_method": "POST",
        "x_client_name": "openclaw-advisor",
        "x_client_instance_prefix": True,
        "x_request_id_prefix": True,
        "source": "openclaw",
        "body_session_id": "oc-session-key",
        "body_user_id": "acct-1",
        "task_spec_version": "task-intake-v2",
        "task_source": "openclaw",
        "task_ingress_lane": "agent_v3",
        "task_scenario": "planning",
        "task_output_shape": "planning_memo",
        "task_session_id": "oc-session-key",
        "task_account_id": "acct-1",
        "task_thread_id": "oc-thread-id",
        "task_agent_id": "agent-1",
        "attachments_count": 1,
        "available_input_files_count": 1,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return OpenClawDynamicReplayCheck(
        name="dynamic_contract_capture",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_live_replay_check(replay: dict[str, Any]) -> OpenClawDynamicReplayCheck:
    result = replay.get("result") or {}
    result_details = result.get("details") if isinstance(result, dict) else {}
    result_details = result_details if isinstance(result_details, dict) else {}
    provenance = result_details.get("provenance") if isinstance(result_details, dict) else {}
    provenance = provenance if isinstance(provenance, dict) else {}
    next_action = result_details.get("next_action") if isinstance(result_details, dict) else {}
    next_action = next_action if isinstance(next_action, dict) else {}
    details = {
        "tool_error": str(replay.get("error") or ""),
        "status": str(result_details.get("status") or ""),
        "route": str(provenance.get("route") or result_details.get("route") or ""),
        "next_action_type": str(next_action.get("type") or ""),
        "session_id": str(result_details.get("session_id") or ""),
        "tool_names": [str(item) for item in replay.get("tool_names") or []],
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["tool_error"]:
        mismatches["tool_error"] = {"expected": "", "actual": details["tool_error"]}
    if "openmind_advisor_ask" not in details["tool_names"]:
        mismatches["tool_names"] = {"expected": "contains openmind_advisor_ask", "actual": details["tool_names"]}
    for field_name, expected in {
        "status": "needs_followup",
        "route": "clarify",
        "next_action_type": "await_user_clarification",
    }.items():
        if details[field_name] != expected:
            mismatches[field_name] = {"expected": expected, "actual": details[field_name]}
    if not details["session_id"]:
        mismatches["session_id"] = {"expected": "non-empty", "actual": details["session_id"]}
    return OpenClawDynamicReplayCheck(
        name="live_planning_clarify_replay",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _run_contract_capture_replay(*, plugin_source: Path, typebox_path: Path) -> dict[str, Any]:
    fake_response = {
        "status": "needs_followup",
        "session_id": "phase20-fake-session",
        "provenance": {"route": "clarify"},
        "next_action": {"type": "await_user_clarification"},
        "answer": "",
    }
    server = _ReplayCaptureServer(fake_response=fake_response)
    try:
        return _execute_openclaw_plugin_tool(
            base_url=server.base_url,
            api_key=None,
            plugin_source=plugin_source,
            typebox_path=typebox_path,
            question=DEFAULT_SAMPLE_MESSAGE,
            goal_hint="planning",
            timeout_seconds=30,
            context={"files": ["/tmp/openclaw-dynamic-replay-demo.txt"]},
            runtime_ctx={
                "sessionKey": "oc-session-key",
                "sessionId": "oc-thread-id",
                "agentAccountId": "acct-1",
                "agentId": "agent-1",
            },
            request_timeout_ms=30000,
            captured_request_target=server,
        )
    finally:
        server.close()


def _run_live_replay(
    *,
    base_url: str,
    env_file: Path,
    plugin_source: Path,
    typebox_path: Path,
) -> dict[str, Any]:
    api_key = _load_openmind_api_key(env_file)
    return _execute_openclaw_plugin_tool(
        base_url=base_url,
        api_key=api_key,
        plugin_source=plugin_source,
        typebox_path=typebox_path,
        question=DEFAULT_SAMPLE_MESSAGE,
        goal_hint="planning",
        timeout_seconds=60,
        context={},
        runtime_ctx={
            "sessionKey": "phase20-live-oc-session",
            "sessionId": "phase20-live-thread",
            "agentAccountId": "phase20-live-acct",
            "agentId": "phase20-live-agent",
        },
        request_timeout_ms=65000,
    )


def _execute_openclaw_plugin_tool(
    *,
    base_url: str,
    api_key: str | None,
    plugin_source: Path,
    typebox_path: Path,
    question: str = "",
    goal_hint: str = "",
    timeout_seconds: int = 60,
    context: dict[str, Any] | None = None,
    runtime_ctx: dict[str, Any],
    request_timeout_ms: int,
    tool_name: str = "openmind_advisor_ask",
    tool_params: dict[str, Any] | None = None,
    captured_request_target: _ReplayCaptureServer | None = None,
) -> dict[str, Any]:
    if not plugin_source.exists():
        raise FileNotFoundError(f"missing OpenClaw plugin source: {plugin_source}")
    if not typebox_path.exists():
        raise FileNotFoundError(f"missing TypeBox runtime path: {typebox_path}")
    with tempfile.TemporaryDirectory(prefix="phase20_openclaw_dynamic_replay_") as tempdir:
        temp_path = Path(tempdir)
        plugin_dir = temp_path / "plugin"
        plugin_dir.mkdir()
        shutil.copy2(plugin_source, plugin_dir / "index.ts")
        nm = temp_path / "node_modules" / "@sinclair"
        nm.mkdir(parents=True)
        os.symlink(typebox_path, nm / "typebox")
        harness_path = temp_path / "harness.ts"
        harness_path.write_text(_HARNESS_TS, encoding="utf-8")
        env = os.environ.copy()
        env["OPENCLAW_PLUGIN_CONFIG_JSON"] = json.dumps(
            {"endpoint": {"baseUrl": str(base_url).rstrip("/"), "timeoutMs": int(request_timeout_ms), "apiKey": api_key or ""}},
            ensure_ascii=False,
        )
        effective_params = (
            dict(tool_params)
            if tool_params is not None
            else {
                "question": question,
                "goalHint": goal_hint,
                "timeoutSeconds": int(timeout_seconds),
                "context": dict(context or {}),
            }
        )
        env["OPENCLAW_TOOL_NAME"] = str(tool_name)
        env["OPENCLAW_TOOL_PARAMS_JSON"] = json.dumps(effective_params, ensure_ascii=False)
        env["OPENCLAW_RUNTIME_CTX_JSON"] = json.dumps(runtime_ctx, ensure_ascii=False)
        npm_cache_dir = temp_path / ".npm-cache"
        npm_cache_dir.mkdir(parents=True, exist_ok=True)
        env["npm_config_cache"] = str(npm_cache_dir)
        env["npm_config_userconfig"] = os.devnull
        env["npm_config_update_notifier"] = "false"
        env["npm_config_audit"] = "false"
        env["npm_config_fund"] = "false"
        proc = subprocess.run(
            _tsx_command(harness_path),
            cwd=str(temp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_seconds) + 30),
        )
        stdout = str(proc.stdout or "").strip()
        stderr = str(proc.stderr or "").strip()
        if proc.returncode != 0:
            raise RuntimeError(f"OpenClaw dynamic replay harness failed: rc={proc.returncode} stderr={stderr or stdout}")
        payload = json.loads(stdout) if stdout else {}
        if captured_request_target is not None:
            captured_request = captured_request_target.wait_for_request()
            payload["captured_request"] = captured_request
        return payload


def _tsx_command(harness_path: Path) -> list[str]:
    if DEFAULT_TSX_BIN.exists():
        return [str(DEFAULT_TSX_BIN), str(harness_path)]
    return ["npx", "--yes", "tsx", str(harness_path)]


def _load_openmind_api_key(env_file: Path) -> str:
    value = str(os.environ.get("OPENMIND_API_KEY") or "").strip()
    if value:
        return value
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            if key.strip() != "OPENMIND_API_KEY":
                continue
            value = raw_value.strip().strip('"').strip("'")
            if value:
                return value
    raise RuntimeError("missing OPENMIND_API_KEY for OpenClaw dynamic replay gate")


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


class _CaptureRequestHandler(BaseHTTPRequestHandler):
    server: "_CaptureHttpServer"

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length)
        try:
            parsed_body = json.loads(raw_body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            parsed_body = {}
        self.server.captured_request = {
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers.items()),
            "body": parsed_body,
        }
        self.server.request_event.set()
        encoded = json.dumps(self.server.fake_response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class _CaptureHttpServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], fake_response: dict[str, Any]) -> None:
        super().__init__(server_address, _CaptureRequestHandler)
        self.fake_response = fake_response
        self.captured_request: dict[str, Any] | None = None
        self.request_event = threading.Event()


class _ReplayCaptureServer:
    def __init__(self, *, fake_response: dict[str, Any]) -> None:
        self._server = _CaptureHttpServer(("127.0.0.1", 0), fake_response)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def wait_for_request(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        if not self._server.request_event.wait(timeout_seconds):
            raise TimeoutError("timed out waiting for OpenClaw dynamic replay capture request")
        return dict(self._server.captured_request or {})

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


_HARNESS_TS = """
import plugin from "./plugin/index.ts";

type RegisteredTool = {
  spec: any;
  meta: any;
};

const pluginConfig = JSON.parse(process.env.OPENCLAW_PLUGIN_CONFIG_JSON || "{}");
const toolName = String(process.env.OPENCLAW_TOOL_NAME || "openmind_advisor_ask");
const toolParams = JSON.parse(process.env.OPENCLAW_TOOL_PARAMS_JSON || "{}");
const runtimeCtx = JSON.parse(process.env.OPENCLAW_RUNTIME_CTX_JSON || "{}");
const tools = new Map<string, RegisteredTool>();
const services: string[] = [];

const api = {
  pluginConfig,
  registerTool(spec: any, meta: any) {
    tools.set(spec.name, { spec, meta });
  },
  registerService(service: any) {
    services.push(String(service?.id || ""));
  },
  logger: {
    info(_msg: string) {},
    warn(_msg: string) {},
    error(_msg: string) {},
  },
};

(async () => {
  plugin.register(api as any);
  const tool = tools.get(toolName);
  if (!tool) {
    throw new Error(`tool missing: ${toolName}`);
  }
  const result = await tool.spec.execute("phase20-openclaw-dynamic-replay", toolParams, runtimeCtx);
  console.log(
    JSON.stringify(
      {
        tool_name: toolName,
        tool_names: [...tools.keys()],
        services,
        result,
      },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
""".strip()
