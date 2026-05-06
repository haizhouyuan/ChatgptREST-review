from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import chatgptrest.controller.coding_agent_executor as executor_mod


def test_resolve_coding_agent_executor_defaults_to_ready_codex(monkeypatch) -> None:
    monkeypatch.setattr(
        executor_mod.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command == "codex" else "",
    )

    resolved = executor_mod.resolve_coding_agent_executor(
        requested_executor="",
        requested_family="",
        request_source="task_intake.context.requested_execution_lane",
    )

    assert resolved is not None
    assert resolved.executor_id == "codex"
    assert resolved.family == "codex"
    assert resolved.defaulted is True
    assert resolved.ready is True


def test_resolve_coding_agent_executor_prefers_ready_codex_for_codex_family(monkeypatch) -> None:
    monkeypatch.setattr(
        executor_mod.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command == "codex" else "",
    )

    resolved = executor_mod.resolve_coding_agent_executor(
        requested_family="codex",
        request_source="task_intake.context.requested_executor_family",
    )

    assert resolved is not None
    assert resolved.executor_id == "codex"
    assert resolved.family == "codex"


def test_resolve_coding_agent_executor_finds_home_local_bin_when_path_missing(monkeypatch, tmp_path) -> None:
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    (local_bin / "codex2").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(executor_mod.shutil, "which", lambda command: "")

    resolved = executor_mod.resolve_coding_agent_executor(
        requested_executor="codex2",
        request_source="task_intake.context.requested_executor",
    )

    assert resolved is not None
    assert resolved.executor_id == "codex2"
    assert resolved.ready is True
    assert resolved.command.endswith("/.local/bin/codex2")


def test_resolve_coding_agent_executor_uses_cc_cli_override(monkeypatch) -> None:
    monkeypatch.setenv("CC_CLI", "/opt/tools/claudeminmax")
    monkeypatch.setattr(executor_mod.shutil, "which", lambda command: "")
    monkeypatch.setattr(executor_mod.Path, "exists", lambda self: str(self) == "/opt/tools/claudeminmax")

    resolved = executor_mod.resolve_coding_agent_executor(
        requested_executor="claudeminmax",
        request_source="task_intake.context.requested_executor",
    )

    assert resolved is not None
    assert resolved.executor_id == "claudeminmax"
    assert resolved.ready is True
    assert resolved.command == "/opt/tools/claudeminmax"


def test_response_schema_is_closed_for_codex_output_contract() -> None:
    schema = executor_mod._response_schema()

    assert schema["type"] == "object"
    assert schema["required"] == ["answer", "summary"]
    assert schema["additionalProperties"] is False


def test_build_prompt_includes_local_material_preflight_summary() -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="codex",
        family="codex",
        mode="codex_exec",
        command="/usr/bin/codex",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )

    prompt = executor_mod._build_prompt(
        question="请梳理 Q1 绩效总结",
        resolved=resolved,
        stable_context={
            "files": ["/vol1/1000/projects/planning/个人绩效/2026Q1/素材/2025年度绩效考核表-袁海州1.xlsx"],
            "scenario_pack": {"profile": "performance_summary", "acceptance": {"required_sections": ["objective", "work_modules"]}},
            "task_intake": {
                "objective": "请梳理 Q1 绩效总结",
                "available_inputs": {
                    "files": ["2025年度绩效考核表-袁海州1 [local artifact]"],
                },
                "context": {
                    "local_material_preflight_summary": "已检查 1 个本地材料路径。\n- /tmp/demo.xlsx: file; sheets=绩效考核表",
                },
            },
        },
    )

    assert "Host local material preflight:" in prompt
    assert "已检查 1 个本地材料路径" in prompt


def test_run_coding_agent_executor_claude_mode_parses_json(monkeypatch, tmp_path) -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="claudeminmax",
        family="claude",
        mode="claude_print",
        command="/usr/bin/claudeminmax",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )

    monkeypatch.setattr(
        executor_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"answer":"- 第一条\\n- 第二条","summary":"ok"}',
            stderr="",
        ),
    )

    result = executor_mod.run_coding_agent_executor(
        resolved=resolved,
        question="给我两条计划",
        stable_context={"cwd": str(tmp_path), "scenario_pack": {"profile": "implementation_plan"}},
        trace_id="trace-claude-exec",
        timeout_seconds=30,
    )

    assert result.ok is True
    assert result.answer == "- 第一条\n- 第二条"
    assert result.summary == "ok"


def test_run_coding_agent_executor_claude_mode_accepts_structured_output_envelope(monkeypatch, tmp_path) -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="claudegac",
        family="claude",
        mode="claude_print",
        command="/usr/bin/claudegac",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )

    monkeypatch.setattr(
        executor_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"type":"result","structured_output":{"answer":"## Goal\\n- Alpha","summary":"ok"}}',
            stderr="",
        ),
    )

    result = executor_mod.run_coding_agent_executor(
        resolved=resolved,
        question="给我一份实施计划",
        stable_context={"cwd": str(tmp_path), "scenario_pack": {"profile": "implementation_plan"}},
        trace_id="trace-claude-structured",
        timeout_seconds=30,
    )

    assert result.ok is True
    assert result.answer == "## Goal\n- Alpha"
    assert result.summary == "ok"


def test_run_coding_agent_executor_claude_mode_uses_family_timeout_floor(monkeypatch, tmp_path) -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="claudegac",
        family="claude",
        mode="claude_print",
        command="/usr/bin/claudegac",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )
    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(
            returncode=0,
            stdout='{"answer":"## Goal\\n- Alpha","summary":"ok"}',
            stderr="",
        )

    monkeypatch.setattr(executor_mod.subprocess, "run", _fake_run)

    result = executor_mod.run_coding_agent_executor(
        resolved=resolved,
        question="给我一份实施计划",
        stable_context={"cwd": str(tmp_path), "scenario_pack": {"profile": "implementation_plan"}},
        trace_id="trace-claude-timeout-floor",
        timeout_seconds=30,
    )

    assert result.ok is True
    assert captured["timeout"] == 900
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    assert payload["requested_timeout_seconds"] == 30
    assert payload["effective_timeout_seconds"] == 900


def test_run_coding_agent_executor_claude_mode_timeout_writes_result(monkeypatch, tmp_path) -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="claudegac",
        family="claude",
        mode="claude_print",
        command="/usr/bin/claudegac",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )

    def _fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["/usr/bin/claudegac"],
            timeout=kwargs["timeout"],
            output='{"structured_output":{"answer":"## Goal\\n- Partial","summary":"partial"}}',
            stderr="slow executor",
        )

    monkeypatch.setattr(executor_mod.subprocess, "run", _fake_run)

    result = executor_mod.run_coding_agent_executor(
        resolved=resolved,
        question="给我一份实施计划",
        stable_context={"cwd": str(tmp_path), "scenario_pack": {"profile": "implementation_plan"}},
        trace_id="trace-claude-timeout",
        timeout_seconds=60,
    )

    assert result.ok is False
    assert result.error == "executor_timeout_after_900s"
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["error"] == "executor_timeout_after_900s"
    assert payload["effective_timeout_seconds"] == 900
    stderr_text = Path(result.stderr_path).read_text(encoding="utf-8")
    assert "timed out after 900 seconds" in stderr_text


def test_run_coding_agent_executor_codex_mode_uses_override(monkeypatch, tmp_path) -> None:
    resolved = executor_mod.CodingAgentResolvedExecutor(
        executor_id="codex2",
        family="codex",
        mode="codex_exec",
        command="/usr/bin/codex2",
        ready=True,
        request_source="task_intake.context",
        resolution_reason="explicit_executor",
    )

    def _fake_codex_exec_with_schema(**kwargs):
        assert kwargs["env"]["CHATGPTREST_CODEX_BIN"] == "/usr/bin/codex2"
        return SimpleNamespace(
            ok=True,
            output={"answer": "- Alpha\n- Beta", "summary": "ok"},
            raw_output="",
            stderr="",
            error="",
            error_type="",
        )

    monkeypatch.setattr(executor_mod, "codex_exec_with_schema", _fake_codex_exec_with_schema)

    result = executor_mod.run_coding_agent_executor(
        resolved=resolved,
        question="给我两条动作",
        stable_context={"cwd": str(tmp_path), "scenario_pack": {"profile": "implementation_plan"}},
        trace_id="trace-codex-exec",
        timeout_seconds=30,
    )

    assert result.ok is True
    assert result.answer == "- Alpha\n- Beta"
