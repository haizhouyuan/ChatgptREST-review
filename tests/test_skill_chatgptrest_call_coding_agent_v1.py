from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _load_skill_module():
    path = Path("skills-src/chatgptrest-call/scripts/chatgptrest_call.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_call_skill_v1", path)
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


def test_parser_defaults_to_automation_surface() -> None:
    mod = _load_skill_module()
    parser = mod.build_parser()

    args = parser.parse_args(["--question", "review this repo"])

    assert args.agent_surface == "automation-kernel-v1"


def test_agent_mode_submits_automation_job_without_foreground_wait(monkeypatch, capsys) -> None:  # noqa: ANN001
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
                "job_id": "job-1",
                "status": "in_progress",
                "provider": "chatgpt",
                "kind": "chatgpt_web.ask",
                "background_wait_started": True,
                "watch_id": "wait-1",
                "completion_mode": "push",
                "push_enabled": True,
                "expected_wait_bucket": "medium",
                "expected_wait_seconds": 420,
                "expected_sla_seconds": 1200,
                "action_hint": "await_push",
                "next_action": {
                    "kind": "await_push",
                    "channel": "controller",
                    "job_id": "job-1",
                    "fallback_tools": ["automation_job_events", "automation_result"],
                },
                "front_action": "return_now",
                "user_message": "已提交，预计 5-8 分钟，完成后会推送，不需要前台轮询。",
            }
        raise AssertionError(tool_name)

    _patch_agent_transport(monkeypatch, mod, fake_run_mcp_tool)

    rc = mod.main(
        [
            "--question",
            "review this repo",
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
    assert calls[0]["arguments"]["provider"] == "chatgpt"
    assert calls[0]["arguments"]["preset"] == "pro_extended"
    assert calls[0]["arguments"]["file_paths"] == ["/tmp/review.md"]
    assert calls[0]["arguments"]["timeout_seconds"] == mod.DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS
    assert calls[0]["arguments"]["max_wait_seconds"] == mod.DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS
    assert calls[0]["arguments"]["auto_wait"] is True
    assert calls[0]["arguments"]["notify_done"] is True
    assert calls[0]["arguments"]["delivery_preference"] == "push_only"
    assert calls[0]["arguments"]["preflight"]["question_not_trivial"] is True
    assert calls[0]["arguments"]["provider_selection"]["requested_provider"] == "chatgpt"
    payload = json.loads(capsys.readouterr().out)
    assert payload["job_id"] == "job-1"
    assert payload["background_wait_started"] is True
    assert payload["watch_id"] == "wait-1"
    assert payload["completion_mode"] == "push"
    assert payload["front_action"] == "return_now"


def test_removed_coding_agent_surface_is_rejected(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--agent-surface",
            "coding-agent-v1",
            "--question",
            "continue",
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["detail"]["requested_surface"] == "coding-agent-v1"
    assert err["detail"]["supported_surface"] == "automation-kernel-v1"


def test_removed_advisor_agent_surface_is_rejected(monkeypatch, capsys) -> None:  # noqa: ANN001
    mod = _load_skill_module()
    monkeypatch.setattr(mod, "_python_bin", lambda _root: Path(sys.executable))

    rc = mod.main(
        [
            "--agent-surface",
            "advisor-agent",
            "--question",
            "continue",
            "--task-intake-json",
            '{"spec_version":"task-intake-v2","objective":"Write memo"}',
        ]
    )

    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["detail"]["requested_surface"] == "advisor-agent"
    assert err["detail"]["supported_surface"] == "automation-kernel-v1"
