"""Tests for CLI improvements (feat/cli-client-improvements branch).

Covers:
 - _format_pretty: human-readable output for various data shapes
 - _validate_kind_preset: CLI-side preset validation
 - idempotency-key auto-generation (no longer raises)
 - --expect-job-id removal
 - ops pause set sends int/float (not str)
 - --job-timeout-seconds renamed flag
 - advisor subcommand registration
 - jobs list subcommand registration
 - jobs events --follow flag registration
 - _is_pro_preset fix in skill wrapper
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pytest

from chatgptrest import cli as cli_mod


# ---------------------------------------------------------------------------
# _format_pretty
# ---------------------------------------------------------------------------

class TestFormatPretty:
    def test_string_passthrough(self) -> None:
        assert cli_mod._format_pretty("hello") == "hello"

    def test_job_view(self) -> None:
        obj = {"job_id": "abc123", "status": "completed", "kind": "chatgpt_web.ask", "phase": "wait"}
        out = cli_mod._format_pretty(obj)
        assert "job_id=abc123" in out
        assert "status=completed" in out
        assert "kind=chatgpt_web.ask" in out

    def test_jobs_list(self) -> None:
        obj = {
            "ok": True,
            "jobs": [
                {"job_id": "j1", "status": "queued", "kind": "chatgpt_web.ask", "phase": "send", "reason": None},
                {"job_id": "j2", "status": "error", "kind": "gemini_web.ask", "phase": None, "reason": "timeout"},
            ],
        }
        out = cli_mod._format_pretty(obj)
        assert "JOB_ID" in out  # header
        assert "j1" in out
        assert "j2" in out
        assert "chatgpt_web.ask" in out

    def test_ops_status(self) -> None:
        obj = {
            "ok": True,
            "pause": {"mode": "none", "active": False},
            "jobs_by_status": {"queued": 0, "in_progress": 1, "completed": 10},
            "active_incidents": 2,
        }
        out = cli_mod._format_pretty(obj)
        assert "pause=False" in out
        assert "completed=10" in out
        assert "incidents=2" in out

    def test_incidents_list(self) -> None:
        obj = {
            "ok": True,
            "incidents": [
                {"incident_id": "inc1", "severity": "P0", "status": "active", "count": 3, "signature": "driver crash"},
            ],
        }
        out = cli_mod._format_pretty(obj)
        assert "INCIDENT_ID" in out
        assert "inc1" in out
        assert "driver crash" in out

    def test_fallback_json(self) -> None:
        obj = {"unknown_structure": True}
        out = cli_mod._format_pretty(obj)
        assert '"unknown_structure"' in out  # JSON fallback


# ---------------------------------------------------------------------------
# _validate_kind_preset
# ---------------------------------------------------------------------------

class TestValidateKindPreset:
    def test_valid_chatgpt(self) -> None:
        cli_mod._validate_kind_preset(kind="chatgpt_web.ask", params_obj={"preset": "auto"})  # no raise

    def test_valid_gemini(self) -> None:
        cli_mod._validate_kind_preset(kind="gemini_web.ask", params_obj={"preset": "pro"})  # no raise

    def test_valid_qwen(self) -> None:
        cli_mod._validate_kind_preset(kind="qwen_web.ask", params_obj={"preset": "deep_research"})  # no raise

    def test_invalid_chatgpt_preset(self) -> None:
        with pytest.raises(cli_mod.CliError, match="unsupported params.preset"):
            cli_mod._validate_kind_preset(kind="chatgpt_web.ask", params_obj={"preset": "nonexistent"})

    def test_invalid_gemini_preset(self) -> None:
        with pytest.raises(cli_mod.CliError, match="unsupported params.preset"):
            cli_mod._validate_kind_preset(kind="gemini_web.ask", params_obj={"preset": "deep_research"})

    def test_noop_when_no_kind(self) -> None:
        cli_mod._validate_kind_preset(kind="", params_obj={"preset": "auto"})  # no raise

    def test_noop_when_unknown_kind(self) -> None:
        cli_mod._validate_kind_preset(kind="repair.check", params_obj={"preset": "whatever"})  # no raise


# ---------------------------------------------------------------------------
# idempotency-key auto-generation
# ---------------------------------------------------------------------------

class TestIdempotencyKeyAutoGen:
    def test_auto_generates_when_missing(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """When --idempotency-key is omitted, _build_submit_request should auto-generate one."""
        ns = argparse.Namespace(
            kind="chatgpt_web.ask",
            input_json="{}",
            input_file=None,
            params_json="{}",
            params_file=None,
            client_json="{}",
            client_file=None,
            question="test",
            prompt=None,
            conversation_url=None,
            parent_job_id=None,
            file_path=None,
            github_repo=None,
            client_name=None,
            client_project=None,
            preset="auto",
            timeout_seconds=None,
            send_timeout_seconds=None,
            wait_timeout_seconds=None,
            max_wait_seconds=None,
            min_chars=None,
            answer_format=None,
            purpose=None,
            allow_queue=None,
            deep_research=None,
            web_search=None,
            agent_mode=None,
            enable_import_code=None,
            drive_name_fallback=None,
            idempotency_key=None,
        )
        payload, headers = cli_mod._build_submit_request(ns)
        assert "Idempotency-Key" in headers
        assert headers["Idempotency-Key"].startswith("chatgptrestctl-")
        # Check stderr has the auto-gen notice
        cap = capsys.readouterr()
        assert "auto-generated idempotency-key" in cap.err


# ---------------------------------------------------------------------------
# --expect-job-id removed
# ---------------------------------------------------------------------------

class TestExpectJobIdCompatibility:
    def test_parser_accepts_expect_job_id(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "jobs", "run",
            "--kind", "chatgpt_web.ask",
            "--question", "test",
            "--preset", "auto",
            "--expect-job-id", "abc",
        ])
        assert args.expect_job_id == "abc"


# ---------------------------------------------------------------------------
# ops pause set sends int/float
# ---------------------------------------------------------------------------

class TestOpsPauseSetTypes:
    def test_pause_set_sends_correct_types(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        captured_body: list[Any] = []

        def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:
            captured_body.append(kwargs.get("json_body"))
            return {"ok": True, "mode": "send"}

        monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
        rc = cli_mod.main([
            "--base-url", "http://localhost:1",
            "ops", "pause", "set",
            "--mode", "send",
            "--duration-seconds", "300",
            "--until-ts", "1700000000.5",
            "--reason", "test reason",
        ])
        assert rc == 0
        body = captured_body[0]
        assert isinstance(body["duration_seconds"], int)
        assert body["duration_seconds"] == 300
        assert isinstance(body["until_ts"], float)
        assert body["until_ts"] == 1700000000.5
        assert body["reason"] == "test reason"


# ---------------------------------------------------------------------------
# --job-timeout-seconds renamed flag
# ---------------------------------------------------------------------------

class TestTimeoutSecondsRenamed:
    def test_job_timeout_seconds_flag_exists(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "jobs", "submit",
            "--kind", "chatgpt_web.ask",
            "--job-timeout-seconds", "600",
        ])
        assert args.timeout_seconds == 600


# ---------------------------------------------------------------------------
# advisor subcommand registration
# ---------------------------------------------------------------------------

class TestAdvisorSubcommand:
    def test_advisor_advise_parses(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "advisor", "advise",
            "--raw-question", "What is AI?",
            "--execute",
            "--force",
        ])
        assert args.raw_question == "What is AI?"
        assert args.execute is True
        assert args.force is True

    def test_advisor_advise_calls_api(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        captured: list[tuple[str, str, Any]] = []

        def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:
            captured.append((method, path, kwargs.get("json_body")))
            return {"ok": True, "status": "planned", "route": "chatgpt_web.ask"}

        monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
        rc = cli_mod.main([
            "--base-url", "http://localhost:1",
            "advisor", "advise",
            "--raw-question", "What is machine learning?",
        ])
        assert rc == 0
        assert len(captured) == 1
        method, path, body = captured[0]
        assert method == "POST"
        assert path == "/v1/advisor/advise"
        assert body["raw_question"] == "What is machine learning?"
        assert body["execute"] is False


class TestAgentTurnExecutionProfile:
    def test_agent_turn_parser_accepts_execution_profile(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "agent",
                "turn",
                "--message",
                "快速分析这个问题",
                "--depth",
                "heavy",
                "--execution-profile",
                "thinking_heavy",
            ]
        )
        assert args.depth == "heavy"
        assert args.execution_profile == "thinking_heavy"

    def test_agent_turn_calls_public_mcp_with_execution_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[tuple[str, dict[str, Any], float]] = []

        def fake_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
            captured.append((tool_name, arguments, timeout_seconds))
            assert mcp_url == cli_mod.DEFAULT_PUBLIC_MCP_URL
            return {"ok": True, "status": "completed", "session_id": "sess-1"}

        monkeypatch.setattr(cli_mod, "_call_public_mcp_tool", fake_mcp_tool)
        rc = cli_mod.main(
            [
                "agent",
                "turn",
                "--message",
                "快速分析这个问题",
                "--depth",
                "heavy",
                "--execution-profile",
                "thinking_heavy",
            ]
        )
        assert rc == 0
        tool_name, body, timeout_seconds = captured[0]
        assert tool_name == "advisor_agent_turn"
        assert body["depth"] == "heavy"
        assert body["execution_profile"] == "thinking_heavy"
        assert timeout_seconds >= 330.0

    def test_agent_turn_calls_public_mcp_with_task_intake_and_contract_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[tuple[str, dict[str, Any]]] = []

        def fake_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
            captured.append((tool_name, arguments))
            assert mcp_url == cli_mod.DEFAULT_PUBLIC_MCP_URL
            return {"ok": True, "status": "completed", "session_id": "sess-1"}

        monkeypatch.setattr(cli_mod, "_call_public_mcp_tool", fake_mcp_tool)
        rc = cli_mod.main(
            [
                "agent",
                "turn",
                "--message",
                "继续执行",
                "--task-intake-json",
                '{"spec_version":"task-intake-v2","objective":"Write a decision memo","trace_id":"trace-1"}',
                "--contract-patch-json",
                '{"decision_to_support":"Approve budget","audience":"Leadership"}',
            ]
        )
        assert rc == 0
        tool_name, body = captured[0]
        assert tool_name == "advisor_agent_turn"
        assert body["task_intake"]["spec_version"] == "task-intake-v2"
        assert body["contract_patch"]["decision_to_support"] == "Approve budget"

    def test_agent_turn_calls_public_mcp_with_workspace_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[tuple[str, dict[str, Any]]] = []

        def fake_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
            captured.append((tool_name, arguments))
            assert mcp_url == cli_mod.DEFAULT_PUBLIC_MCP_URL
            return {"ok": True, "status": "completed", "session_id": "sess-ws-1"}

        monkeypatch.setattr(cli_mod, "_call_public_mcp_tool", fake_mcp_tool)
        rc = cli_mod.main(
            [
                "agent",
                "turn",
                "--workspace-request-json",
                '{"spec_version":"workspace-request-v1","action":"deliver_report_to_docs","payload":{"title":"日报","body_markdown":"# content"}}',
            ]
        )
        assert rc == 0
        tool_name, body = captured[0]
        assert tool_name == "advisor_agent_turn"
        assert body["message"] == ""
        assert body["workspace_request"]["action"] == "deliver_report_to_docs"

    def test_agent_turn_direct_rest_override_still_calls_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[tuple[str, str, Any]] = []

        def fake_request(self, method: str, path: str, **kwargs: Any) -> Any:
            captured.append((method, path, kwargs))
            return {"ok": True, "status": "completed", "session_id": "sess-1"}

        monkeypatch.setattr(cli_mod.ApiClient, "request", fake_request)
        rc = cli_mod.main(
            [
                "--base-url",
                "http://localhost:1",
                "agent",
                "turn",
                "--message",
                "maintenance direct path",
                "--agent-direct-rest",
            ]
        )
        assert rc == 0
        method, path, kwargs = captured[0]
        assert method == "POST"
        assert path == "/v3/agent/turn"
        assert kwargs["headers"]["X-Client-Name"] == "chatgptrestctl-maint"
        body = kwargs["json_body"]
        assert body["message"] == "maintenance direct path"


# ---------------------------------------------------------------------------
# jobs list subcommand registration
# ---------------------------------------------------------------------------

class TestJobsListSubcommand:
    def test_jobs_list_parses(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "jobs", "list",
            "--status", "queued",
            "--limit", "10",
        ])
        assert args.status == "queued"
        assert args.limit == 10


# ---------------------------------------------------------------------------
# jobs events --follow registration
# ---------------------------------------------------------------------------

class TestJobsEventsFollow:
    def test_follow_flag_exists(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "jobs", "events", "job123",
            "--follow",
        ])
        assert args.follow is True


# ---------------------------------------------------------------------------
# skill wrapper: _is_pro_preset fix
# ---------------------------------------------------------------------------

class TestSkillWrapperProPreset:
    def test_pro_extended_is_pro(self) -> None:
        # Import from skills-src
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills-src" / "chatgptrest-call" / "scripts"))
        try:
            import chatgptrest_call
            assert chatgptrest_call._is_pro_preset("pro_extended") is True
            assert chatgptrest_call._is_pro_preset("thinking_extended") is True
            assert chatgptrest_call._is_pro_preset("thinking_heavy") is True
            assert chatgptrest_call._is_pro_preset("pro") is True
            assert chatgptrest_call._is_pro_preset("auto") is False
            assert chatgptrest_call._is_pro_preset("deep_think") is False
            assert chatgptrest_call._is_pro_preset("deep_research") is True
        finally:
            sys.path.pop(0)
            if "chatgptrest_call" in sys.modules:
                del sys.modules["chatgptrest_call"]
