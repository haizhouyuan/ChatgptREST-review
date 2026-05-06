from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_skill_module():
    path = Path("skills-src/chatgptrest-call/scripts/chatgptrest_call.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_call_skill", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool) -> None:  # noqa: ANN001
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))
    monkeypatch.setattr(
        mod,
        "_initialize_mcp_session",
        lambda *, mcp_url, timeout_seconds: {"session_id": "mcp-session-1", "protocol_version": "2025-03-26"},
    )
    monkeypatch.setattr(
        mod,
        "_enforce_min_interval",
        lambda **_kwargs: {
            "state_file": "/tmp/chatgptrest-call-test-interval.json",
            "min_interval_seconds": 0.0,
            "last_send_ts": 0.0,
            "waited_seconds": 0.0,
            "sent_at": 0.0,
        },
    )
    monkeypatch.setattr(mod, "_run_mcp_tool", fake_run_mcp_tool)


def test_is_pro_preset_includes_thinking_and_deep_research() -> None:
    mod = _load_skill_module()
    assert mod._is_pro_preset("pro_extended") is True
    assert mod._is_pro_preset("thinking_extended") is True
    assert mod._is_pro_preset("thinking_heavy") is True
    assert mod._is_pro_preset("deep_research") is True
    assert mod._is_pro_preset("deep-research") is True
    assert mod._is_pro_preset("research") is True
    assert mod._is_pro_preset("auto") is False


def test_skill_defaults_derive_repo_local_paths() -> None:
    mod = _load_skill_module()

    assert Path(mod.DEFAULT_CHATGPTREST_ROOT) == Path.cwd().resolve()
    assert Path(mod.DEFAULT_INTERVAL_STATE_FILE) == (
        Path.cwd().resolve() / "state" / "skill" / "chatgptrest_call_interval.json"
    )


def test_autoload_runtime_env_reads_standard_env_file(monkeypatch, tmp_path: Path) -> None:
    mod = _load_skill_module()
    env_file = tmp_path / "chatgptrest.env"
    env_file.write_text(
        "\n".join(
            [
                "CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT=secret-value",
                "CHATGPTREST_API_TOKEN='token-value'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT", raising=False)
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.setenv("CHATGPTREST_CALL_ENV_FILES", str(env_file))

    loaded = mod._autoload_runtime_env()

    assert str(env_file.resolve()) in loaded["files"]
    assert os.environ["CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT"] == "secret-value"
    assert os.environ["CHATGPTREST_API_TOKEN"] == "token-value"


def test_python_bin_falls_back_to_current_interpreter(tmp_path: Path) -> None:
    mod = _load_skill_module()

    resolved = mod._python_bin(tmp_path)

    assert resolved == Path(sys.executable).resolve()


def test_skill_parser_accepts_job_timeout_aliases() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()
    args1 = parser.parse_args(["--provider", "chatgpt", "--question", "x", "--job-timeout-seconds", "9"])
    assert args1.timeout_seconds == 9

    args2 = parser.parse_args(["--provider", "chatgpt", "--question", "x", "--timeout-seconds", "10"])
    assert args2.timeout_seconds == 10


def test_skill_parser_defaults_to_push_only_automation_surface() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()

    args = parser.parse_args(["--question", "review this repo"])

    assert args.agent_surface == "automation-kernel-v1"
    assert args.delivery_preference == "push_only"


def test_initialize_mcp_session_uses_initialize_handshake(monkeypatch) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    requests: list[dict[str, Any]] = []

    @dataclass(frozen=True)
    class _FakeSession:
        url: str
        session_id: str
        protocol_version: str

    @dataclass(frozen=True)
    class _FakeHandshake:
        session: _FakeSession
        result: dict[str, Any]

    def fake_handshake(
        url: str,
        *,
        client_name: str,
        client_version: str,
        protocol_version: str = "2025-03-26",
        timeout_sec: float = 30.0,
    ):
        requests.append(
            {
                "url": url,
                "client_name": client_name,
                "client_version": client_version,
                "protocol_version": protocol_version,
                "timeout_sec": timeout_sec,
            }
        )
        return _FakeHandshake(
            session=_FakeSession(url=url, session_id="sess-header-1", protocol_version="2025-03-26"),
            result={"protocolVersion": "2025-03-26"},
        )

    monkeypatch.setattr(mod, "mcp_http_initialize_handshake", fake_handshake)

    session = mod._initialize_mcp_session(mcp_url=mod.DEFAULT_PUBLIC_MCP_URL, timeout_seconds=20.0)

    assert session["session_id"] == "sess-header-1"
    assert session["protocol_version"] == "2025-03-26"
    assert requests[0]["url"] == mod.DEFAULT_PUBLIC_MCP_URL
    assert requests[0]["client_name"] == mod.DEFAULT_MCP_CLIENT_NAME
    assert requests[0]["client_version"] == mod.DEFAULT_MCP_CLIENT_VERSION
    assert requests[0]["protocol_version"] == mod.DEFAULT_MCP_PROTOCOL_VERSION


def test_agent_mode_submits_automation_receipt_without_foreground_wait(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    calls: list[dict[str, Any]] = []

    def fake_run_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float, request_id: int, session: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append(
            {
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "timeout_seconds": timeout_seconds,
            }
        )
        if tool_name == "automation_ask":
            return {
                "ok": True,
                "accepted": True,
                "job_id": "job-1",
                "status": "in_progress",
                "provider": "chatgpt",
                "kind": "chatgpt_web.ask",
                "background_wait_started": True,
                "watch_id": "wait-1",
                "completion_mode": "push",
                "push_enabled": True,
                "notify_channel": "controller",
                "expected_wait_bucket": "medium",
                "expected_wait_seconds": 420,
                "expected_sla_seconds": 1200,
                "front_action": "return_now",
                "action_hint": "await_push",
                "next_action": {
                    "kind": "await_push",
                    "channel": "controller",
                    "job_id": "job-1",
                    "fallback_tools": ["automation_job_events", "automation_result"],
                },
                "user_message": "已提交，预计 5-8 分钟，完成后会推送，不需要前台轮询。",
            }
        raise AssertionError(tool_name)

    _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool)

    rc = mod.main(
        [
            "--question",
            "请基于当前仓代码做评审，并给出简短结论",
            "--goal-hint",
            "code_review",
            "--provider",
            "chatgpt",
            "--preset",
            "pro_extended",
            "--file-path",
            "/tmp/review.md",
        ]
    )

    assert rc == 0
    assert [call["tool_name"] for call in calls] == ["automation_ask"]
    call = calls[0]
    assert call["arguments"]["provider"] == "chatgpt"
    assert call["arguments"]["preset"] == "pro_extended"
    assert call["arguments"]["file_paths"] == ["/tmp/review.md"]
    assert call["arguments"]["delivery_preference"] == "push_only"
    assert call["arguments"]["timeout_seconds"] == mod.DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS
    assert call["arguments"]["max_wait_seconds"] == mod.DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS
    assert call["arguments"]["auto_wait"] is True
    assert call["arguments"]["notify_done"] is True
    assert call["arguments"]["preflight"]["question_not_trivial"] is True
    assert call["arguments"]["provider_selection"]["requested_provider"] == "chatgpt"
    payload = json.loads(capsys.readouterr().out)
    assert payload["job_id"] == "job-1"
    assert payload["completion_mode"] == "push"
    assert payload["front_action"] == "return_now"
    assert payload["next_action"]["kind"] == "await_push"
    assert payload["next_action"]["channel"] == "controller"


def test_agent_mode_normalizes_relative_file_paths_from_caller_cwd(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    packet = tmp_path / "review_packet.md"
    packet.write_text("review context", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_run_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float, request_id: int, session: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append({"tool_name": tool_name, "arguments": dict(arguments)})
        return {
            "ok": True,
            "accepted": True,
            "job_id": "job-relative-path",
            "status": "queued",
            "completion_mode": "push",
            "front_action": "return_now",
            "next_action": {
                "kind": "await_push",
                "channel": "controller",
                "job_id": "job-relative-path",
            },
        }

    _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool)

    rc = mod.main(
        [
            "--question",
            "请基于附件做审阅",
            "--provider",
            "chatgpt",
            "--preset",
            "pro_extended",
            "--file-path",
            "review_packet.md",
        ]
    )

    assert rc == 0
    assert calls[0]["arguments"]["file_paths"] == [packet.resolve().as_posix()]
    payload = json.loads(capsys.readouterr().out)
    assert payload["job_id"] == "job-relative-path"


def test_agent_mode_forwards_explicit_preflight_and_provider_selection(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    calls: list[dict[str, Any]] = []

    def fake_run_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float, request_id: int, session: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append({"tool_name": tool_name, "arguments": dict(arguments)})
        return {
            "ok": True,
            "accepted": True,
            "job_id": "job-2",
            "status": "queued",
            "completion_mode": "push",
            "background_wait_started": True,
            "watch_id": "wait-2",
            "front_action": "return_now",
            "next_action": {
                "kind": "await_push",
                "channel": "controller",
                "job_id": "job-2",
                "fallback_tools": ["automation_job_events", "automation_result"],
            },
        }

    _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool)

    rc = mod.main(
        [
            "--question",
            "请基于附件写一份 memo",
            "--provider",
            "chatgpt",
            "--preset",
            "pro_extended",
            "--preflight-json",
            '{"task_goal_clear":true,"attachments_complete":true,"question_not_trivial":true,"question_not_over_closed":true,"premium_justified":true}',
            "--provider-selection-json",
            '{"requested_provider":"chatgpt","requested_preset":"pro_extended","reason":"需要 Pro 长文判断"}',
            "--client-context-json",
            '{"origin":"hermes-workbench","task_id":"tsk-skill-001"}',
        ]
    )

    assert rc == 0
    call = calls[0]
    assert call["tool_name"] == "automation_ask"
    assert call["arguments"]["preflight"]["premium_justified"] is True
    assert call["arguments"]["provider_selection"]["reason"] == "需要 Pro 长文判断"
    assert call["arguments"]["client_context"]["task_id"] == "tsk-skill-001"
    payload = json.loads(capsys.readouterr().out)
    assert payload["job_id"] == "job-2"


def test_decode_tool_result_exposes_non_json_rate_limit_detail() -> None:
    mod = _load_skill_module()
    payload = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "HTTP 429 {\"detail\":{\"error\":\"chatgpt_frontend_rate_limit_active\","
                        "\"reason\":\"frontend_rate_limit\",\"retry_after_seconds\":4294}}"
                    ),
                }
            ]
        }
    }

    try:
        mod._decode_tool_result(payload)
    except RuntimeError as exc:
        message = exc.args[0]
        detail = exc.args[1]
    else:
        raise AssertionError("expected non-JSON tool text to fail")

    assert message == "MCP tool returned non-JSON text response"
    assert detail["http_status"] == 429
    assert detail["error"] == "chatgpt_frontend_rate_limit_active"
    assert detail["reason"] == "frontend_rate_limit"
    assert detail["retry_after_seconds"] == 4294


def test_agent_mode_surfaces_structured_mcp_text_error(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()

    def fake_run_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float, request_id: int, session: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError(
            "MCP tool returned non-JSON text response",
            {
                "http_status": 429,
                "error": "chatgpt_frontend_rate_limit_active",
                "reason": "frontend_rate_limit",
                "retry_after_seconds": 4294,
            },
        )

    _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool)

    rc = mod.main(
        [
            "--question",
            "请做架构顾问评审",
            "--provider",
            "chatgpt",
            "--preset",
            "pro_extended",
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["message"] == "MCP tool returned non-JSON text response"
    assert err["detail"]["http_status"] == 429
    assert err["detail"]["error"] == "chatgpt_frontend_rate_limit_active"
    assert err["detail"]["reason"] == "frontend_rate_limit"
    assert err["detail"]["retry_after_seconds"] == 4294


def test_removed_agent_surface_is_rejected(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--agent-surface",
            "advisor-agent",
            "--question",
            "continue",
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["detail"]["requested_surface"] == "advisor-agent"
    assert err["detail"]["supported_surface"] == "automation-kernel-v1"


def test_task_intake_is_rejected_on_automation_only_surface(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--question",
            "继续执行",
            "--task-intake-json",
            '{"spec_version":"task-intake-v2","objective":"Write memo"}',
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["message"] == "automation-kernel-v1 does not accept task_intake"


def test_execution_profile_is_rejected_on_automation_only_surface(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--question",
            "继续执行",
            "--execution-profile",
            "report_grade",
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["message"] == "automation-kernel-v1 does not accept --execution-profile"


def test_agent_mode_rejects_transport_timeout_shorter_than_run_budget(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--question",
            "请总结当前状态",
            "--job-timeout-seconds",
            "300",
            "--request-timeout-seconds",
            "60",
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["message"] == "agent transport timeout is shorter than the requested run budget"


def test_agent_mode_uses_long_default_budget_for_chatgpt_deep_research() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()
    args = parser.parse_args(
        [
            "--question",
            "请做深度研究",
            "--provider",
            "chatgpt",
            "--preset",
            "pro_extended",
            "--deep-research",
        ]
    )

    assert mod._resolve_agent_timeout_seconds(args) == mod.DEFAULT_CHATGPT_DEEP_RESEARCH_AGENT_TIMEOUT_SECONDS


def test_agent_mode_keeps_short_default_budget_for_non_pro() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()
    args = parser.parse_args(
        [
            "--question",
            "请总结",
            "--provider",
            "gemini",
            "--preset",
            "pro",
        ]
    )

    assert mod._resolve_agent_timeout_seconds(args) == mod.DEFAULT_AGENT_TIMEOUT_SECONDS


def test_skill_parser_accepts_maintenance_legacy_jobs_flag() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()
    args = parser.parse_args(["--no-agent", "--maintenance-legacy-jobs", "--question", "x"])
    assert args.agent is False
    assert args.maintenance_legacy_jobs is True
