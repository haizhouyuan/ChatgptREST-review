from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from chatgptrest import cli as cli_mod


def _completed(args: list[str], rc: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=out, stderr=err)


def test_jobs_submit_builds_payload_and_headers(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True, "job_id": "j_submit"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--idempotency-key",
            "idem-1",
            "--question",
            "hello",
            "--preset",
            "pro_extended",
            "--purpose",
            "smoke",
            "--deep-research",
            "--allow-queue",
            "--client-name",
            "agent",
            "--client-project",
            "proj",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    c = calls[0]
    assert c["method"] == "POST"
    assert c["path"] == "/v1/jobs"
    assert c["headers"]["Idempotency-Key"] == "idem-1"
    body = c["json_body"]
    assert body["kind"] == "chatgpt_web.ask"
    assert body["input"]["question"] == "hello"
    assert body["params"]["preset"] == "pro_extended"
    assert body["params"]["purpose"] == "smoke"
    assert body["params"]["deep_research"] is True
    assert body["params"]["allow_queue"] is True
    assert body["client"]["name"] == "agent"
    assert body["client"]["project"] == "proj"
    out = json.loads(capsys.readouterr().out)
    assert out["job_id"] == "j_submit"


def test_api_client_auto_trace_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_http_json_request(*, method: str, url: str, headers: dict[str, str], json_body: Any, timeout_seconds: float):  # noqa: ANN001
        seen["method"] = method
        seen["url"] = url
        seen["headers"] = dict(headers)
        seen["json_body"] = json_body
        seen["timeout_seconds"] = timeout_seconds
        return 200, {"ok": True}, '{"ok":true}'

    monkeypatch.setattr(cli_mod, "_http_json_request", fake_http_json_request)
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "cli-tests")
    monkeypatch.setenv("CHATGPTREST_CLIENT_INSTANCE", "ci-1")
    monkeypatch.setenv("CHATGPTREST_REQUEST_ID_PREFIX", "rid")

    api = cli_mod.ApiClient(base_url="http://127.0.0.1:18711", api_token=None, ops_token=None, timeout_seconds=3.0)
    out = api.request("GET", "/healthz")

    assert out["ok"] is True
    assert seen["headers"]["X-Client-Name"] == "cli-tests"
    assert seen["headers"]["X-Client-Instance"] == "ci-1"
    assert seen["headers"]["X-Request-ID"].startswith("rid-")

    seen.clear()
    api.request("GET", "/healthz", headers={"X-Request-ID": "custom-rid"})
    assert seen["headers"]["X-Request-ID"] == "custom-rid"


def test_jobs_run_emits_single_json_object(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seq: list[dict[str, Any]] = [
        {"ok": True, "job_id": "j_run", "status": "queued"},
        {"ok": True, "job_id": "j_run", "status": "completed"},
        {"chunk": "abc", "next_offset": 3, "done": False},
        {"chunk": "def", "next_offset": None, "done": True},
    ]
    calls: list[tuple[str, str]] = []

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        calls.append((method, path))
        return seq.pop(0)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "run",
            "--kind",
            "chatgpt_web.ask",
            "--idempotency-key",
            "idem-run-1",
            "--question",
            "hello",
            "--preset",
            "auto",
        ]
    )
    assert rc == 0
    assert calls[0] == ("POST", "/v1/jobs")
    assert calls[1] == ("GET", "/v1/jobs/j_run/wait")
    assert calls[2] == ("GET", "/v1/jobs/j_run/answer")
    out = json.loads(capsys.readouterr().out)
    assert out["submit"]["job_id"] == "j_run"
    assert out["job"]["status"] == "completed"
    assert out["answer"]["chunk"] == "abcdef"
    assert out["answer"]["fetched_all"] is True


def test_jobs_run_expect_job_id_skips_submit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seq: list[dict[str, Any]] = [
        {"ok": True, "job_id": "j_existing", "status": "completed"},
        {"chunk": "xyz", "next_offset": None, "done": True},
    ]
    calls: list[tuple[str, str]] = []

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        calls.append((method, path))
        return seq.pop(0)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "run",
            "--expect-job-id",
            "j_existing",
        ]
    )
    assert rc == 0
    assert calls[0] == ("GET", "/v1/jobs/j_existing/wait")
    assert calls[1] == ("GET", "/v1/jobs/j_existing/answer")
    out = json.loads(capsys.readouterr().out)
    assert out["submit"]["status"] == "submit_skipped"
    assert out["submit"]["reason"] == "expect_job_id"
    assert out["job"]["job_id"] == "j_existing"
    assert out["answer"]["chunk"] == "xyz"


def test_jobs_run_requires_submit_inputs_without_expect_job_id(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_mod.main(
        [
            "jobs",
            "run",
        ]
    )
    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["error_type"] == "CliError"
    assert "--kind is required" in err["message"]


def test_jobs_cancel_sends_cancel_reason_header(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["headers"] = dict(kwargs.get("headers") or {})
        return {"ok": True, "status": "canceled"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["jobs", "cancel", "job-123", "--reason", "operator stop"])
    assert rc == 0
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/jobs/job-123/cancel"
    assert seen["headers"]["X-Cancel-Reason"] == "operator stop"
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "canceled"


def test_issues_status_calls_expected_endpoint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["body"] = kwargs.get("json_body")
        return {"ok": True, "issue_id": "iss_1", "status": "mitigated"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["issues", "status", "iss_1", "--status", "mitigated", "--note", "fixed"])
    assert rc == 0
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/issues/iss_1/status"
    assert seen["body"]["status"] == "mitigated"
    assert seen["body"]["note"] == "fixed"
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "mitigated"


def test_service_status_uses_systemctl(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool) -> subprocess.CompletedProcess[str]:  # noqa: FBT001
        calls.append(cmd)
        return _completed(cmd, 0, out="active\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = cli_mod.main(["service", "status"])
    assert rc == 0
    assert calls
    assert calls[0][:5] == ["systemctl", "--user", "--no-pager", "--full", "status"]
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True


def test_viewer_status_uses_probe(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        cli_mod,
        "_viewer_status",
        lambda *args, **kwargs: {
            "ok": True,
            "bind_host": "100.124.54.52",
            "novnc_port": 6082,
            "novnc_url": "http://100.124.54.52:6082/vnc.html",
        },
    )
    rc = cli_mod.main(["viewer", "status"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["novnc_port"] == 6082


def test_doctor_fails_when_required_viewer_unhealthy(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if path == "/healthz":
            return {"ok": True}
        if path == "/v1/ops/status":
            return {"ok": True, "build": {"git_sha": "abc"}}
        raise AssertionError(path)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: _completed(cmd, 0, out="active\n"))
    monkeypatch.setattr(cli_mod, "_port_open", lambda *args, **kwargs: True)
    monkeypatch.setattr(cli_mod, "_viewer_status", lambda *args, **kwargs: {"ok": False, "novnc_url": "http://x:6082/vnc.html"})
    rc = cli_mod.main(["doctor", "--require-viewer"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["viewer"]["ok"] is False


def test_doctor_accepts_alternate_cdp_port_when_default_is_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if path == "/healthz":
            return {"ok": True}
        if path == "/v1/ops/status":
            return {"ok": True, "build": {"git_sha": "abc"}}
        raise AssertionError(path)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: _completed(cmd, 0, out="active\n"))
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.delenv("CHROME_DEBUG_PORT", raising=False)
    monkeypatch.setattr(
        cli_mod,
        "_port_open",
        lambda host, port, timeout=0.2: int(port) in {18711, 18701, 18712, 9226},  # noqa: ARG005
    )
    monkeypatch.setattr(cli_mod, "_viewer_status", lambda *args, **kwargs: {"ok": True, "novnc_url": "http://x:6082/vnc.html"})
    rc = cli_mod.main(["doctor"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["cdp_ok"] is True
    assert out["ports"]["9222"] is False
    assert out["ports"]["9226"] is True


def test_doctor_fails_when_no_cdp_port_is_open(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if path == "/healthz":
            return {"ok": True}
        if path == "/v1/ops/status":
            return {"ok": True, "build": {"git_sha": "abc"}}
        raise AssertionError(path)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: _completed(cmd, 0, out="active\n"))
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.delenv("CHROME_DEBUG_PORT", raising=False)
    monkeypatch.setattr(
        cli_mod,
        "_port_open",
        lambda host, port, timeout=0.2: int(port) in {18711, 18701, 18712},  # noqa: ARG005
    )
    monkeypatch.setattr(cli_mod, "_viewer_status", lambda *args, **kwargs: {"ok": True, "novnc_url": "http://x:6082/vnc.html"})
    rc = cli_mod.main(["doctor"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["cdp_ok"] is False


def test_doctor_fails_when_required_port_is_missing_even_if_cdp_ok(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if path == "/healthz":
            return {"ok": True}
        if path == "/v1/ops/status":
            return {"ok": True, "build": {"git_sha": "abc"}}
        raise AssertionError(path)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: _completed(cmd, 0, out="active\n"))
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9226")
    monkeypatch.setattr(
        cli_mod,
        "_port_open",
        lambda host, port, timeout=0.2: int(port) in {18711, 18701, 9226},  # noqa: ARG005
    )
    monkeypatch.setattr(cli_mod, "_viewer_status", lambda *args, **kwargs: {"ok": True, "novnc_url": "http://x:6082/vnc.html"})
    rc = cli_mod.main(["doctor"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["required_ports_ok"] is False
    assert out["cdp_ok"] is True
    assert out["ok"] is False


def test_cdp_port_from_url_parses_and_rejects_invalid_values() -> None:
    assert cli_mod._cdp_port_from_url("http://127.0.0.1:9222") == 9222  # noqa: SLF001
    assert cli_mod._cdp_port_from_url("127.0.0.1:9226") == 9226  # noqa: SLF001
    assert cli_mod._cdp_port_from_url("http://127.0.0.1") is None  # noqa: SLF001
    assert cli_mod._cdp_port_from_url("http://127.0.0.1:not-a-port") is None  # noqa: SLF001
    assert cli_mod._cdp_port_from_url("") is None  # noqa: SLF001


def test_doctor_cdp_ports_dedup_and_fallback_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1:9226")
    monkeypatch.setenv("CHROME_DEBUG_PORT", "9226")
    assert cli_mod._doctor_cdp_ports() == [9226, 9222]  # noqa: SLF001

    monkeypatch.setenv("CHATGPT_CDP_URL", "http://127.0.0.1")
    monkeypatch.setenv("CHROME_DEBUG_PORT", "0")
    assert cli_mod._doctor_cdp_ports() == [9222, 9226]  # noqa: SLF001

def test_api_error_returns_exit_code_3(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        raise cli_mod.ApiError(status=503, message="service unavailable", body_obj={"detail": "down"})

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["ops", "status"])
    assert rc == 3
    err = json.loads(capsys.readouterr().err)
    assert err["error_type"] == "ApiError"
    assert err["status"] == 503


def test_advisor_advise_calls_expected_endpoint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["body"] = kwargs.get("json_body")
        return {"ok": True, "status": "planned", "route": "chatgpt_pro"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "advisor",
            "advise",
            "--raw-question",
            "请给出执行方案",
            "--context-json",
            '{"project":"openclaw"}',
            "--agent-options-json",
            '{"preset":"thinking_heavy"}',
            "--execute",
        ]
    )
    assert rc == 0
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/advisor/advise"
    assert seen["body"]["raw_question"] == "请给出执行方案"
    assert seen["body"]["context"]["project"] == "openclaw"
    assert seen["body"]["execute"] is True
    assert seen["body"]["agent_options"]["preset"] == "thinking_heavy"
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "planned"


def test_agent_status_uses_public_mcp_by_default(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, Any] = {}

    def fake_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        seen["mcp_url"] = mcp_url
        seen["tool_name"] = tool_name
        seen["arguments"] = dict(arguments)
        seen["timeout_seconds"] = timeout_seconds
        return {"ok": True, "session_id": "sess-1", "status": "completed"}

    monkeypatch.setattr(cli_mod, "_call_public_mcp_tool", fake_mcp_tool)
    rc = cli_mod.main(["agent", "status", "sess-1"])
    assert rc == 0
    assert seen["mcp_url"] == cli_mod.DEFAULT_PUBLIC_MCP_URL
    assert seen["tool_name"] == "advisor_agent_status"
    assert seen["arguments"] == {"session_id": "sess-1"}
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "completed"


def test_agent_cancel_uses_public_mcp_by_default(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, Any] = {}

    def fake_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        seen["mcp_url"] = mcp_url
        seen["tool_name"] = tool_name
        seen["arguments"] = dict(arguments)
        seen["timeout_seconds"] = timeout_seconds
        return {"ok": True, "session_id": "sess-1", "status": "cancelled"}

    monkeypatch.setattr(cli_mod, "_call_public_mcp_tool", fake_mcp_tool)
    rc = cli_mod.main(["agent", "cancel", "sess-1"])
    assert rc == 0
    assert seen["mcp_url"] == cli_mod.DEFAULT_PUBLIC_MCP_URL
    assert seen["tool_name"] == "advisor_agent_cancel"
    assert seen["arguments"] == {"session_id": "sess-1"}
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "cancelled"


def test_agent_status_direct_rest_override_uses_maintenance_client_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["headers"] = dict(kwargs.get("headers") or {})
        return {"ok": True, "session_id": "sess-1", "status": "completed"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["agent", "status", "sess-1", "--agent-direct-rest"])
    assert rc == 0
    assert seen["path"] == "/v3/agent/session/sess-1"
    assert seen["headers"]["X-Client-Name"] == "chatgptrestctl-maint"
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "completed"


def test_agent_cancel_direct_rest_override_uses_maintenance_client_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["headers"] = dict(kwargs.get("headers") or {})
        seen["body"] = kwargs.get("json_body")
        return {"ok": True, "session_id": "sess-1", "status": "cancelled"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["agent", "cancel", "sess-1", "--agent-direct-rest"])
    assert rc == 0
    assert seen["path"] == "/v3/agent/cancel"
    assert seen["headers"]["X-Client-Name"] == "chatgptrestctl-maint"
    assert seen["body"] == {"session_id": "sess-1"}
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "cancelled"


def test_parser_accepts_request_timeout_seconds_alias() -> None:
    parser = cli_mod.build_parser()
    args = parser.parse_args(["--request-timeout-seconds", "123", "ops", "status"])
    assert args.request_timeout_seconds == 123.0


def test_jobs_wait_timeout_fallback_uses_job_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if method == "GET" and path.endswith("/wait"):
            raise cli_mod.CliError("request timed out: simulated")
        if method == "GET" and path == "/v1/jobs/job-timeout-1":
            return {"ok": True, "job_id": "job-timeout-1", "status": "in_progress", "phase": "wait"}
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["jobs", "wait", "job-timeout-1", "--timeout-seconds", "90"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["job_id"] == "job-timeout-1"
    assert out["status"] == "in_progress"
    assert out["client_wait_timed_out"] is True


def test_jobs_run_timeout_fallback_uses_job_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        if method == "POST" and path == "/v1/jobs":
            return {"ok": True, "job_id": "job-timeout-2", "status": "queued"}
        if method == "GET" and path.endswith("/wait"):
            raise cli_mod.CliError("request timed out: simulated")
        if method == "GET" and path == "/v1/jobs/job-timeout-2":
            return {"ok": True, "job_id": "job-timeout-2", "status": "in_progress", "phase": "wait"}
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "run",
            "--kind",
            "chatgpt_web.ask",
            "--question",
            "hello",
            "--preset",
            "auto",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["submit"]["job_id"] == "job-timeout-2"
    assert out["job"]["job_id"] == "job-timeout-2"
    assert out["job"]["status"] == "in_progress"
    assert out["job"]["client_wait_timed_out"] is True


def test_jobs_run_cancel_on_client_timeout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        calls.append((method, path, dict(kwargs)))
        if method == "POST" and path == "/v1/jobs":
            return {"ok": True, "job_id": "job-timeout-3", "status": "queued"}
        if method == "GET" and path.endswith("/wait"):
            raise cli_mod.CliError("request timed out: simulated")
        if method == "GET" and path == "/v1/jobs/job-timeout-3":
            return {"ok": True, "job_id": "job-timeout-3", "status": "in_progress", "phase": "wait"}
        if method == "POST" and path == "/v1/jobs/job-timeout-3/cancel":
            return {"ok": True, "job_id": "job-timeout-3", "status": "canceled"}
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "run",
            "--kind",
            "chatgpt_web.ask",
            "--question",
            "hello",
            "--preset",
            "auto",
            "--cancel-on-client-timeout",
            "--cancel-on-client-timeout-reason",
            "auto timeout cleanup",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["job"]["client_wait_timed_out"] is True
    assert out["cancel"]["status"] == "canceled"

    cancel_calls = [c for c in calls if c[0] == "POST" and c[1] == "/v1/jobs/job-timeout-3/cancel"]
    assert len(cancel_calls) == 1
    headers = cancel_calls[0][2]["headers"]
    assert headers["X-Cancel-Reason"] == "auto timeout cleanup"


def test_jobs_submit_auto_generates_idempotency_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["headers"] = kwargs.get("headers")
        return {"ok": True, "job_id": "j_auto_idem"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--question",
            "hello",
            "--preset",
            "auto",
        ]
    )
    assert rc == 0
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/jobs"
    assert isinstance(seen["headers"], dict)
    assert str(seen["headers"]["Idempotency-Key"]).startswith("chatgptrestctl-")
    assert "auto-generated idempotency-key" in capsys.readouterr().err


def test_jobs_submit_preset_alias_deep_research_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["body"] = kwargs.get("json_body")
        return {"ok": True, "job_id": "j_dr_alias"}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--question",
            "hello",
            "--preset",
            "deep_research",
        ]
    )
    assert rc == 0
    params = seen["body"]["params"]
    assert params["preset"] == "thinking_heavy"
    assert params["deep_research"] is True


def test_jobs_submit_preset_validation_fails_early(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_mod.main(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--question",
            "hello",
            "--preset",
            "not_a_real_preset",
        ]
    )
    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["error_type"] == "CliError"
    assert "unsupported params.preset" in err["message"]


def test_jobs_events_follow_advances_after_id(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[dict[str, str]] = []
    seq: list[Any] = [
        {"ok": True, "events": [{"id": 1}], "next_after_id": 2},
        "done",
    ]

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        assert method == "GET"
        assert path == "/v1/jobs/job-follow/events"
        queries.append(dict(kwargs.get("query") or {}))
        return seq.pop(0)

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["jobs", "events", "job-follow", "--after-id", "0", "--follow"])
    assert rc == 0
    assert queries == [{"after_id": "0", "limit": "200"}, {"after_id": "2", "limit": "200"}]


def test_jobs_list_alias_calls_ops_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["query"] = dict(kwargs.get("query") or {})
        return {"ok": True, "jobs": []}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(["jobs", "list", "--status", "queued", "--limit", "7"])
    assert rc == 0
    assert seen["method"] == "GET"
    assert seen["path"] == "/v1/ops/jobs"
    assert seen["query"]["status"] == "queued"
    assert seen["query"]["limit"] == "7"


def test_ops_pause_set_serializes_numeric_types(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN001
        seen["method"] = method
        seen["path"] = path
        seen["body"] = kwargs.get("json_body")
        return {"ok": True}

    monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
    rc = cli_mod.main(
        [
            "ops",
            "pause",
            "set",
            "--mode",
            "send",
            "--duration-seconds",
            "60",
            "--until-ts",
            "1700000000.5",
            "--reason",
            "maintenance",
        ]
    )
    assert rc == 0
    body = seen["body"]
    assert isinstance(body["duration_seconds"], int)
    assert body["duration_seconds"] == 60
    assert isinstance(body["until_ts"], float)
    assert body["until_ts"] == 1700000000.5
    assert body["reason"] == "maintenance"


def test_parser_accepts_job_timeout_seconds_aliases() -> None:
    parser = cli_mod.build_parser()
    args1 = parser.parse_args(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--preset",
            "auto",
            "--job-timeout-seconds",
            "30",
        ]
    )
    assert args1.timeout_seconds == 30

    args2 = parser.parse_args(
        [
            "jobs",
            "submit",
            "--kind",
            "chatgpt_web.ask",
            "--preset",
            "auto",
            "--timeout-seconds",
            "31",
        ]
    )
    assert args2.timeout_seconds == 31
