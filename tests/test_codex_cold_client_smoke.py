from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    path = Path("ops/codex_cold_client_smoke.py").resolve()
    spec = importlib.util.spec_from_file_location("codex_cold_client_smoke_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_prompt_mentions_repo_discovery_and_wrapper(tmp_path: Path) -> None:
    mod = _load_module()
    prompt = mod._build_prompt(
        provider="gemini",
        preset="pro",
        question="请解释自动化测试的价值。",
        out_dir=tmp_path,
        request_timeout_seconds=180.0,
    )
    assert "AGENTS.md" in prompt
    assert "docs/codex_fresh_client_quickstart.md" in prompt
    assert "docs/runbook.md" in prompt
    assert "docs/client_projects_registry.md" in prompt
    assert "skills-src/chatgptrest-call/SKILL.md" in prompt
    assert "chatgptrest_call.py" in prompt
    assert "./.venv/bin/python -m chatgptrest.cli" in prompt
    assert "/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py" in prompt
    assert "mcp" in prompt.lower()
    assert "provider and preset are mandatory" in prompt.lower()
    assert "keep exploration lean" in prompt.lower()
    assert "do not assume bare `python` exists" in prompt.lower()
    assert "artifact" in prompt.lower()


def test_chatgpt_default_preset_is_auto() -> None:
    mod = _load_module()
    assert mod._default_preset("chatgpt") == "auto"


def test_policy_blocks_live_chatgpt_smoke_by_default() -> None:
    mod = _load_module()
    err = mod._policy_error_for_request(provider="chatgpt", preset="auto", allow_live_chatgpt_smoke=False)
    assert err is not None
    assert "blocked by default" in err


def test_policy_blocks_high_cost_chatgpt_smoke_even_with_live_override() -> None:
    mod = _load_module()
    err = mod._policy_error_for_request(
        provider="chatgpt",
        preset="pro_extended",
        allow_live_chatgpt_smoke=True,
    )
    assert err is not None
    assert "high-cost" in err


def test_cold_codex_env_isolates_codex_home(tmp_path: Path) -> None:
    mod = _load_module()
    env = mod._cold_codex_env(tmp_path, isolate_codex_home=True)
    assert env["CODEX_HOME"] == str(tmp_path / "cold_codex_home")
    assert (tmp_path / "cold_codex_home").is_dir()


def test_main_writes_meta_and_uses_workspace_write(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()
    calls: dict[str, object] = {}

    class _FakeResult:
        ok = True
        output = {
            "ok": True,
            "provider": "gemini",
            "preset": "pro",
            "question": "q",
            "docs_read": ["docs/runbook.md"],
            "commands": ["python -m chatgptrest.cli ..."],
            "job_succeeded": True,
            "gaps": [],
            "recommendations": []
        }

    def _fake_exec_with_schema(**kwargs):
        calls.update(kwargs)
        Path(kwargs["out_json"]).write_text(json.dumps(_FakeResult.output), encoding="utf-8")
        return _FakeResult()

    monkeypatch.setattr(mod, "codex_exec_with_schema", _fake_exec_with_schema)

    rc = mod.main(
        [
            "--provider",
            "gemini",
            "--preset",
            "pro",
            "--profile",
            "cold-client-executor",
            "--question",
            "q",
            "--out-dir",
            str(tmp_path / "run"),
        ]
    )
    assert rc == 0
    assert calls["sandbox"] == "workspace-write"
    assert Path(calls["out_json"]).exists()
    meta = json.loads((tmp_path / "run" / "meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "gemini"
    assert meta["profile"] == "cold-client-executor"
    assert meta["isolate_codex_home"] is False
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["runner"] == "codex_exec_with_schema"
    assert out["profile"] == "cold-client-executor"
    assert out["used_isolated_codex_home"] is False
    assert out["result"]["job_succeeded"] is True


def test_main_falls_back_to_codex_json_mode(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()

    class _FailResult:
        ok = False
        error_type = "RuntimeError"
        error = "schema mode failed"
        returncode = 1
        stderr = "schema stderr"

    def _fake_exec_with_schema(**_kwargs):
        return _FailResult()

    json_payload = {
        "ok": True,
        "provider": "gemini",
        "preset": "pro",
        "question": "q",
        "docs_read": ["docs/runbook.md"],
        "commands": ["python ..."],
        "job_succeeded": True,
        "gaps": [],
        "recommendations": [],
    }
    stdout = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(json_payload, ensure_ascii=False),
            },
        },
        ensure_ascii=False,
    )

    class _FakeStdin:
        def write(self, _text: str) -> None:
            return None

        def close(self) -> None:
            return None

    class _FakePopen:
        def __init__(self, *_args, **kwargs) -> None:
            self.stdin = _FakeStdin()
            self.returncode = 0
            stdout_fh = kwargs.get("stdout")
            if stdout_fh is not None:
                stdout_fh.write(stdout + "\n")
                stdout_fh.flush()

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return self.returncode

    monkeypatch.setattr(mod, "codex_exec_with_schema", _fake_exec_with_schema)
    monkeypatch.setattr(mod.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(mod, "_codex_bin", lambda: "/usr/bin/codex")

    rc = mod.main(
        [
            "--provider",
            "gemini",
            "--preset",
            "pro",
            "--question",
            "q",
            "--out-dir",
            str(tmp_path / "run"),
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["runner"] == "codex_exec_json_fallback"
    assert out["used_isolated_codex_home"] is False
    assert out["result"]["job_succeeded"] is True


def test_main_salvages_client_summary_when_fallback_process_lingers(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()

    class _FailResult:
        ok = False
        error_type = "RuntimeError"
        error = "schema mode failed"
        returncode = 1
        stderr = "schema stderr"

    class _FakeStdin:
        def write(self, _text: str) -> None:
            return None

        def close(self) -> None:
            return None

    class _FakePopen:
        def __init__(self, *_args, **_kwargs) -> None:
            self.stdin = _FakeStdin()
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return self.returncode

    def _fake_exec_with_schema(**_kwargs):
        return _FailResult()

    monkeypatch.setattr(mod, "codex_exec_with_schema", _fake_exec_with_schema)
    monkeypatch.setattr(mod.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(mod, "_codex_bin", lambda: "/usr/bin/codex")
    monkeypatch.setattr(mod.time, "sleep", lambda _secs: None)

    out_dir = tmp_path / "run"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "answer.md").write_text("answer body", encoding="utf-8")
    (out_dir / "client_summary.json").write_text(
        json.dumps(
            {
                "documented_path_discovered": True,
                "request_executed": True,
                "docs_and_files_read": ["docs/runbook.md"],
                "commands_ran": ["python wrapper.py ..."],
                "job": {
                    "job_id": "job-1",
                    "final_status": "completed",
                },
                "concrete_confusion_points_or_missing_guidance": ["loopback blocked"],
                "recommendations": ["document mcp fallback"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = mod.main(
        [
            "--provider",
            "gemini",
            "--preset",
            "pro",
            "--question",
            "q",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["runner"] == "codex_exec_json_fallback"
    assert out["used_isolated_codex_home"] is False
    assert out["result"]["ok"] is True
    assert out["result"]["job_id"] == "job-1"
    assert out["result"]["answer_preview"] == "answer body"


def test_main_auto_retries_with_isolated_codex_home_on_config_error(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()
    calls: list[dict[str, object]] = []
    monkeypatch.delenv("CODEX_HOME", raising=False)

    class _FailResult:
        ok = False
        error_type = "RuntimeError"
        error = "Error loading config.toml: duplicate key"
        returncode = 1
        stderr = "Error loading config.toml: duplicate key"

    class _OkResult:
        ok = True
        returncode = 0
        stderr = ""
        output = {
            "ok": True,
            "provider": "gemini",
            "preset": "pro",
            "question": "q",
            "docs_read": ["docs/runbook.md"],
            "commands": ["python ..."],
            "job_succeeded": True,
            "gaps": [],
            "recommendations": [],
        }

    def _fake_exec_with_schema(**kwargs):
        calls.append(kwargs)
        env = kwargs.get("env") or {}
        if env.get("CODEX_HOME"):
            return _OkResult()
        return _FailResult()

    monkeypatch.setattr(mod, "codex_exec_with_schema", _fake_exec_with_schema)
    monkeypatch.setattr(mod, "_codex_json_fallback", lambda **_kwargs: (None, "config error"))

    rc = mod.main(
        [
            "--provider",
            "gemini",
            "--preset",
            "pro",
            "--question",
            "q",
            "--out-dir",
            str(tmp_path / "run"),
        ]
    )
    assert rc == 0
    assert len(calls) == 2
    assert "CODEX_HOME" not in (calls[0]["env"] or {})
    assert str((calls[1]["env"] or {}).get("CODEX_HOME", "")).endswith("cold_codex_home")
    out = json.loads(capsys.readouterr().out)
    assert out["used_isolated_codex_home"] is True


def test_build_system_observed_payload_falls_back_to_synthetic_docs_and_commands(tmp_path: Path) -> None:
    mod = _load_module()
    answer_path = tmp_path / "answer.md"
    answer_path.write_text("answer body", encoding="utf-8")
    payload, err = mod._build_system_observed_payload(
        jsonl_path=tmp_path / "missing.jsonl",
        provider="gemini",
        preset="pro",
        question="q",
        job_info={
            "job_id": "job-1",
            "status": "completed",
            "answer_path": answer_path,
            "conversation_path": tmp_path / "conversation.json",
        },
        schema_path=Path("ops/schemas/codex_cold_client_smoke.schema.json"),
    )
    assert err is None
    assert payload is not None
    assert payload["docs_read"]
    assert payload["commands"]
    assert payload["job_succeeded"] is True


def test_build_system_observed_payload_marks_completed_not_final_research(tmp_path: Path) -> None:
    mod = _load_module()
    answer_path = tmp_path / "answer.txt"
    answer_path.write_text("partial answer", encoding="utf-8")
    payload, err = mod._build_system_observed_payload(
        jsonl_path=tmp_path / "missing.jsonl",
        provider="chatgpt",
        preset="auto",
        question="q",
        job_info={
            "job_id": "job-2",
            "status": "completed",
            "completion_contract": {
                "answer_state": "provisional",
                "authoritative_answer_path": "jobs/job-2/answer.txt",
                "answer_provenance": {"contract_class": "research"},
            },
            "answer_path": answer_path,
            "authoritative_answer_path": "jobs/job-2/answer.txt",
            "conversation_path": tmp_path / "conversation.json",
        },
        schema_path=Path("ops/schemas/codex_cold_client_smoke.schema.json"),
    )
    assert err is None
    assert payload is not None
    assert payload["job_succeeded"] is False
    assert payload["final_status"] == "completed_not_final"
    assert payload["answer_state"] == "provisional"
    assert payload["authoritative_answer_path"] == "jobs/job-2/answer.txt"
