from __future__ import annotations

from pathlib import Path

import pytest

import chatgptrest.eval.public_agent_mcp_validation as mod
from chatgptrest.integrations.mcp_http_client import McpHttpError, McpHttpInitializeHandshake, McpHttpSession


def _public_agent_tools() -> list[dict]:
    return [
        {"name": "automation_ask"},
        {"name": "automation_result"},
        {"name": "automation_job_create"},
        {"name": "automation_job_status"},
        {"name": "automation_job_answer"},
        {
            "name": "automation_job_cancel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "reason": {"type": "string", "default": ""},
                },
                "required": ["job_id"],
            },
        },
        {"name": "automation_job_events"},
        {"name": "automation_conversation_fetch"},
        {"name": "automation_conversation_get"},
        {"name": "automation_conversation_find"},
        {"name": "automation_gemini_generate_image_submit"},
    ]


def test_public_agent_mcp_validation_report_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()
    tool_calls: list[tuple[str, dict, float]] = []

    monkeypatch.setattr(
        mod,
        "_mcp_initialize_handshake",
        lambda url: McpHttpInitializeHandshake(
            session=McpHttpSession(url=url, session_id="mcp-sess-1", protocol_version=mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION),
            result={
                "serverInfo": {"name": "chatgptrest-agent-mcp", "version": "1.26.0"},
                "protocolVersion": mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION,
            },
        ),
    )
    monkeypatch.setattr(mod, "_mcp_client", lambda url: client)
    monkeypatch.setattr(
        mod,
        "_mcp_list_tools",
        lambda actual_client: _public_agent_tools() if actual_client is client else [],
    )

    def _fake_call_tool(actual_client, *, tool_name: str, tool_args: dict, timeout_seconds: float = 30.0):
        assert actual_client is client
        tool_calls.append((tool_name, tool_args, timeout_seconds))
        if tool_name == "automation_ask":
            return {
                "ok": True,
                "accepted": True,
                "job_id": "job-auto-1",
                "status": "in_progress",
                "completion_mode": "push",
                "push_enabled": True,
                "front_action": "return_now",
                "background_wait_started": True,
                "expected_wait_bucket": "medium",
                "expected_wait_seconds": 420,
                "next_action": {
                    "kind": "await_push",
                    "channel": "controller",
                    "job_id": "job-auto-1",
                    "fallback_tools": ["automation_job_events", "automation_result"],
                },
            }
        if tool_name == "automation_job_status":
            return {
                "ok": True,
                "job_id": "job-auto-1",
                "status": "in_progress",
            }
        raise AssertionError(tool_name)

    monkeypatch.setattr(mod, "_mcp_call_tool", _fake_call_tool)

    report = mod.run_public_agent_mcp_validation()

    assert report.num_checks == 5
    assert report.num_failed == 0
    assert report.surface == "automation-kernel-v1"
    assert report.validation_class == "probe"
    assert [item.name for item in report.results] == [
        "initialize",
        "tools_list",
        "automation_job_cancel_schema",
        "automation_submit_receipt",
        "status_continuity",
    ]
    assert tool_calls == [
        (
            "automation_ask",
            {
                "idempotency_key": "public-agent-mcp-validation-automation-ask",
                "question": "请基于 docs/contract_v1.md 为维护者输出一段自动化提交变更摘要。",
                "provider": "chatgpt",
                "preset": "auto",
                "requested_execution_lane": "web_standard",
                "premium_allowed": False,
                "task_object_contract": {
                    "object_type": "document",
                    "object_ref": "docs/contract_v1.md",
                    "intended_reader": "maintainer",
                    "task_purpose": "probe_validation",
                    "evidence_boundary": "repository_docs_only",
                },
                "delivery_preference": "push_only",
                "preflight": {
                    "task_goal_clear": True,
                    "expected_output_defined": True,
                    "attachments_complete": True,
                    "question_not_trivial": True,
                },
                "provider_selection": {
                    "requested_provider": "chatgpt",
                    "requested_preset": "auto",
                    "selection_source": "probe_validation",
                    "reason": "验证 automation-kernel-v1 canonical receipt（probe-only, non-premium）",
                },
                "timeout_seconds": 30,
                "auto_wait": True,
                "notify_done": False,
            },
            90.0,
        ),
        ("automation_job_status", {"job_id": "job-auto-1"}, 30.0),
    ]


def test_public_agent_mcp_validation_reuses_existing_job_on_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()

    monkeypatch.setattr(
        mod,
        "_mcp_initialize_handshake",
        lambda url: McpHttpInitializeHandshake(
            session=McpHttpSession(url=url, session_id="mcp-sess-2", protocol_version=mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION),
            result={
                "serverInfo": {"name": "chatgptrest-agent-mcp", "version": "1.26.0"},
                "protocolVersion": mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION,
            },
        ),
    )
    monkeypatch.setattr(mod, "_mcp_client", lambda url: client)
    monkeypatch.setattr(
        mod,
        "_mcp_list_tools",
        lambda actual_client: _public_agent_tools() if actual_client is client else [],
    )

    def _fake_call_tool(actual_client, *, tool_name: str, tool_args: dict, timeout_seconds: float = 30.0):
        assert actual_client is client
        if tool_name == "automation_ask":
            return {
                "ok": False,
                "status_code": 409,
                "error": "duplicate_public_agent_session_in_progress",
                "job_id": "job-auto-new",
                "existing_job_id": "job-auto-existing",
                "recommended_client_action": "reuse_existing_job",
            }
        if tool_name == "automation_job_status":
            assert tool_args == {"job_id": "job-auto-existing"}
            return {
                "ok": True,
                "job_id": "job-auto-existing",
                "status": "running",
                "completion_mode": "push",
                "push_enabled": True,
                "front_action": "return_now",
                "background_wait_started": True,
                "expected_wait_bucket": "medium",
                "expected_wait_seconds": 420,
                "next_action": {
                    "kind": "await_push",
                    "channel": "controller",
                    "job_id": "job-auto-existing",
                    "fallback_tools": ["automation_job_events", "automation_result"],
                },
            }
        raise AssertionError(tool_name)

    monkeypatch.setattr(mod, "_mcp_call_tool", _fake_call_tool)

    report = mod.run_public_agent_mcp_validation()

    assert report.num_failed == 0
    receipt_check = next(item for item in report.results if item.name == "automation_submit_receipt")
    assert receipt_check.details["duplicate_handoff"] is True
    assert receipt_check.details["turn_source"] == "status_after_duplicate_handoff"
    assert receipt_check.details["receipt_contract_checked"] is False


def test_public_agent_mcp_validation_reuses_completed_recent_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()

    monkeypatch.setattr(
        mod,
        "_mcp_initialize_handshake",
        lambda url: McpHttpInitializeHandshake(
            session=McpHttpSession(url=url, session_id="mcp-sess-duplicate", protocol_version=mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION),
            result={
                "serverInfo": {"name": "chatgptrest-agent-mcp", "version": "1.26.0"},
                "protocolVersion": mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION,
            },
        ),
    )
    monkeypatch.setattr(mod, "_mcp_client", lambda url: client)
    monkeypatch.setattr(
        mod,
        "_mcp_list_tools",
        lambda actual_client: _public_agent_tools() if actual_client is client else [],
    )

    def _fake_call_tool(actual_client, *, tool_name: str, tool_args: dict, timeout_seconds: float = 30.0):
        assert actual_client is client
        if tool_name == "automation_ask":
            return {
                "ok": False,
                "mcp_tool_error": True,
                "error": "low_level_ask_duplicate_recently_submitted",
                "reason": "duplicate_recent_low_level_ask",
                "existing_job_id": "job-auto-completed",
                "existing_status": "completed",
            }
        if tool_name == "automation_job_status":
            assert tool_args == {"job_id": "job-auto-completed"}
            return {
                "ok": True,
                "job_id": "job-auto-completed",
                "status": "completed",
            }
        raise AssertionError(tool_name)

    monkeypatch.setattr(mod, "_mcp_call_tool", _fake_call_tool)

    report = mod.run_public_agent_mcp_validation()

    assert report.num_failed == 0
    receipt_check = next(item for item in report.results if item.name == "automation_submit_receipt")
    assert receipt_check.details["duplicate_handoff"] is True
    assert receipt_check.details["receipt_contract_checked"] is False


def test_public_agent_mcp_validation_reuses_recent_low_level_duplicate() -> None:
    assert mod._looks_like_duplicate_in_progress(
        {
            "ok": False,
            "mcp_tool_error": True,
            "error": "low_level_ask_duplicate_recently_submitted",
            "reason": "duplicate_recent_low_level_ask",
            "existing_job_id": "job-auto-existing",
            "existing_status": "in_progress",
        }
    )


def test_public_agent_mcp_validation_does_not_reuse_duplicate_without_job_id() -> None:
    assert not mod._looks_like_duplicate_in_progress(
        {
            "ok": False,
            "error": "low_level_ask_duplicate_recently_submitted",
            "reason": "duplicate_recent_low_level_ask",
        }
    )


def test_public_agent_mcp_validation_fails_when_conversation_tools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()

    monkeypatch.setattr(
        mod,
        "_mcp_initialize_handshake",
        lambda url: McpHttpInitializeHandshake(
            session=McpHttpSession(url=url, session_id="mcp-sess-3", protocol_version=mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION),
            result={
                "serverInfo": {"name": "chatgptrest-agent-mcp", "version": "1.26.0"},
                "protocolVersion": mod.EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION,
            },
        ),
    )
    monkeypatch.setattr(mod, "_mcp_client", lambda url: client)
    monkeypatch.setattr(
        mod,
        "_mcp_list_tools",
        lambda actual_client: [
            tool
            for tool in _public_agent_tools()
            if not str(tool.get("name") or "").startswith("automation_conversation_")
        ]
        if actual_client is client
        else [],
    )

    def _fake_call_tool(actual_client, *, tool_name: str, tool_args: dict, timeout_seconds: float = 30.0):
        assert actual_client is client
        if tool_name == "automation_ask":
            return {
                "ok": True,
                "accepted": True,
                "job_id": "job-auto-1",
                "status": "in_progress",
                "completion_mode": "push",
                "push_enabled": True,
                "front_action": "return_now",
                "background_wait_started": True,
                "expected_wait_bucket": "medium",
                "expected_wait_seconds": 420,
                "next_action": {"kind": "await_push", "channel": "controller"},
            }
        if tool_name == "automation_job_status":
            return {"ok": True, "job_id": "job-auto-1", "status": "in_progress"}
        raise AssertionError(tool_name)

    monkeypatch.setattr(mod, "_mcp_call_tool", _fake_call_tool)

    report = mod.run_public_agent_mcp_validation()

    tools_check = next(item for item in report.results if item.name == "tools_list")
    assert report.num_failed == 1
    assert tools_check.passed is False
    assert tools_check.mismatches["missing_tools"]["actual"] == [
        "automation_conversation_fetch",
        "automation_conversation_get",
        "automation_conversation_find",
    ]


def test_public_agent_mcp_validation_client_uses_keyword_constructor(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    class FakeMcpHttpClient:
        def __init__(self, *, url: str, client_name: str, client_version: str) -> None:
            seen["url"] = url
            seen["client_name"] = client_name
            seen["client_version"] = client_version

    monkeypatch.setattr(mod, "McpHttpClient", FakeMcpHttpClient)

    client = mod._mcp_client("http://127.0.0.1:18712/mcp")

    assert isinstance(client, FakeMcpHttpClient)
    assert seen == {
        "url": "http://127.0.0.1:18712/mcp",
        "client_name": mod.DEFAULT_VALIDATION_CLIENT_NAME,
        "client_version": mod.DEFAULT_VALIDATION_CLIENT_VERSION,
    }


def test_public_agent_mcp_validation_call_tool_uses_keyword_api() -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:
            seen["tool_name"] = tool_name
            seen["tool_args"] = tool_args
            seen["timeout_sec"] = timeout_sec
            return {"ok": True, "job_id": "job-1"}

    result = mod._mcp_call_tool(
        FakeClient(),  # type: ignore[arg-type]
        tool_name="automation_job_status",
        tool_args={"job_id": "job-1"},
        timeout_seconds=12.5,
    )

    assert result == {"ok": True, "job_id": "job-1"}
    assert seen == {
        "tool_name": "automation_job_status",
        "tool_args": {"job_id": "job-1"},
        "timeout_sec": 12.5,
    }


def test_public_agent_mcp_validation_call_tool_extracts_structured_tool_error() -> None:
    class FakeClient:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
            raise McpHttpError(
                'tools/call tool error: Error executing tool automation_ask: HTTP 409 Conflict: '
                '{"detail":{"error":"low_level_ask_duplicate_recently_submitted",'
                '"reason":"duplicate_recent_low_level_ask",'
                '"existing_job_id":"job-auto-existing","existing_status":"in_progress"}}'
            )

    result = mod._mcp_call_tool(
        FakeClient(),  # type: ignore[arg-type]
        tool_name="automation_ask",
        tool_args={"idempotency_key": "same"},
    )

    assert result == {
        "ok": False,
        "mcp_tool_error": True,
        "error": "low_level_ask_duplicate_recently_submitted",
        "reason": "duplicate_recent_low_level_ask",
        "existing_job_id": "job-auto-existing",
        "existing_status": "in_progress",
    }


def test_public_agent_mcp_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAgentMcpValidationReport(
        base_url="http://127.0.0.1:18712",
        surface="automation-kernel-v1",
        validation_class="probe",
        sample_message="请基于 docs/contract_v1.md 为维护者输出一段自动化提交变更摘要。",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        results=[
            mod.PublicAgentMcpCheckResult(
                name="initialize",
                passed=True,
                details={"server_name": "chatgptrest-agent-mcp"},
            )
        ],
    )

    json_path, md_path = mod.write_public_agent_mcp_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_agent_mcp_report_markdown(report)
    assert "Public Agent MCP Validation Report" in markdown
    assert "- validation_class: probe" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
