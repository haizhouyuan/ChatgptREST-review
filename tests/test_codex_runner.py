from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from chatgptrest.core.codex_runner import codex_exec_with_schema, codex_resume_last_message_json


def test_codex_exec_with_schema_builds_cmd_and_parses_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    out_json = tmp_path / "out.json"

    captured: dict[str, object] = {}

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        captured["cmd"] = list(cmd)
        out_json.write_text(json.dumps({"summary": "ok"}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.delenv("CHATGPTREST_CODEX_BIN", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)

    res = codex_exec_with_schema(
        prompt="hello",
        schema_path=schema_path,
        out_json=out_json,
        model="m1",
        profile="cold-client-executor",
        timeout_seconds=5,
        cd=tmp_path,
        sandbox="read-only",
    )
    assert res.ok is True
    assert res.output == {"summary": "ok"}

    cmd = captured.get("cmd")
    assert isinstance(cmd, list)
    assert "--sandbox" in cmd
    assert "read-only" in cmd
    assert "--output-schema" in cmd
    assert str(schema_path) in cmd
    assert "-o" in cmd
    assert str(out_json) in cmd
    assert "--model" in cmd
    assert "m1" in cmd
    assert "--profile" in cmd
    assert "cold-client-executor" in cmd
    assert "--cd" in cmd
    assert str(tmp_path) in cmd


def test_codex_exec_with_schema_reports_nonzero_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    out_json = tmp_path / "out.json"

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        return subprocess.CompletedProcess(cmd, 7, stdout="oops", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = codex_exec_with_schema(prompt="hello", schema_path=schema_path, out_json=out_json, timeout_seconds=5)
    assert res.ok is False
    assert res.returncode == 7
    assert res.error is not None
    assert "boom" in res.error or "oops" in res.error


def test_codex_exec_with_schema_reports_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    out_json = tmp_path / "out.json"

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        out_json.write_text("{not json", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = codex_exec_with_schema(prompt="hello", schema_path=schema_path, out_json=out_json, timeout_seconds=5)
    assert res.ok is False
    assert res.error_type == "ValueError"


def test_codex_exec_with_schema_surfaces_error_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    out_json = tmp_path / "out.json"
    noisy_stderr = (
        "prompt header\n"
        "lots of echoed context\n"
        "ERROR: {\"type\":\"error\",\"error\":{\"code\":\"invalid_json_schema\",\"message\":\"Missing allow_actions\"}}\n"
    )

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=noisy_stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = codex_exec_with_schema(prompt="hello", schema_path=schema_path, out_json=out_json, timeout_seconds=5)
    assert res.ok is False
    assert res.error is not None
    assert "invalid_json_schema" in res.error
    assert "prompt header" not in res.error


def test_codex_resume_last_message_json_builds_cmd_and_parses_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_text = tmp_path / "resume.txt"
    captured: dict[str, object] = {}

    def fake_run(cmd, *, input, text, check, capture_output, timeout, cwd):  # noqa: ANN001,A002,ARG001
        captured["cmd"] = list(cmd)
        captured["cwd"] = cwd
        captured["input"] = input
        out_text.write_text('{"summary":"ok","route":"repair.open_pr"}', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.delenv("CHATGPTREST_CODEX_BIN", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)

    res = codex_resume_last_message_json(
        prompt="continue",
        out_text=out_text,
        model="gpt-5-codex",
        profile="maint-judge",
        timeout_seconds=9,
        cwd=tmp_path,
    )
    assert res.ok is True
    assert res.output == {"summary": "ok", "route": "repair.open_pr"}
    assert res.raw_output is not None

    cmd = captured.get("cmd")
    assert isinstance(cmd, list)
    assert cmd[1:4] == ["exec", "resume", "--last"]
    assert "-o" in cmd
    assert str(out_text) in cmd
    assert "--model" in cmd
    assert "gpt-5-codex" in cmd
    assert "--profile" in cmd
    assert "maint-judge" in cmd
    assert cmd[-1] == "-"
    assert captured.get("cwd") == str(tmp_path)
    assert captured.get("input") == "continue"


def test_codex_resume_last_message_json_parses_fenced_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_text = tmp_path / "resume.txt"

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        out_text.write_text("resume result\n```json\n{\"summary\":\"ok\",\"route\":\"manual\"}\n```", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = codex_resume_last_message_json(prompt="continue", out_text=out_text, timeout_seconds=5)
    assert res.ok is True
    assert res.output == {"summary": "ok", "route": "manual"}


def test_codex_resume_last_message_json_reports_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_text = tmp_path / "resume.txt"

    def fake_run(cmd, *, input, text, check, capture_output, timeout):  # noqa: ANN001,A002,ARG001
        out_text.write_text("not json", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = codex_resume_last_message_json(prompt="continue", out_text=out_text, timeout_seconds=5)
    assert res.ok is False
    assert res.error_type == "ValueError"
