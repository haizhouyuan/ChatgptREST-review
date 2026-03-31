from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ops import run_convergence_live_matrix as module


def test_run_live_matrix_skips_without_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)
    monkeypatch.setattr(module, "DEFAULT_CHATGPTREST_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.delenv("CHATGPTREST_ENV_FILE", raising=False)

    result = module.run_live_matrix(output_dir=tmp_path / "bundle", python_bin="/tmp/python")

    assert result["skipped"] is True
    assert result["reason"] == "missing_api_token"
    assert result["discovery"]["api_token_source"] == ""
    summary = json.loads((tmp_path / "bundle" / "summary.json").read_text(encoding="utf-8"))
    assert summary["skipped"] is True


def test_run_live_matrix_uses_shared_env_file_when_process_env_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)
    env_file = tmp_path / "chatgptrest.env"
    env_file.write_text(
        "CHATGPTREST_API_TOKEN=file-token\nCHATGPTREST_OPS_TOKEN=file-ops\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_ENV_FILE", str(env_file))
    monkeypatch.setattr(module, "DEFAULT_CHATGPTREST_ENV_FILE", tmp_path / "unused.env")

    seen_tokens: list[str] = []

    def fake_run_command(cmd: list[str], *, env=None, cwd=module.REPO_ROOT):
        seen_tokens.append(str((env or {}).get("CHATGPTREST_API_TOKEN") or ""))
        return subprocess.CompletedProcess(
            cmd,
            3,
            stdout="",
            stderr=json.dumps(
                {
                    "body": {
                        "detail": {
                            "error": "provider_disabled",
                            "detail": "provider disabled for this host",
                        }
                    }
                }
            ),
        )

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_live_matrix(output_dir=tmp_path / "bundle", python_bin="/tmp/python")

    assert result["skipped"] is False
    assert result["discovery"]["api_token_source"] == f"env_file:{env_file}"
    assert result["discovery"]["ops_token_source"] == f"env_file:{env_file}"
    assert all(token == "file-token" for token in seen_tokens)
    assert result["providers"]


def test_classify_outcome_accepts_wait_handoff_pending() -> None:
    outcome, acceptable, completed = module._classify_outcome(
        submit_obj={"job_id": "job-chat"},
        get_obj={
            "job_id": "job-chat",
            "status": "in_progress",
            "phase": "wait",
            "prompt_sent_at": 123.0,
            "conversation_url": "https://chatgpt.com/c/test",
        },
        events_obj={"events": []},
        answer_obj=None,
    )

    assert outcome == "wait_handoff_pending"
    assert acceptable is True
    assert completed is False


def test_classify_outcome_rejects_completed_without_research_finality() -> None:
    outcome, acceptable, completed = module._classify_outcome(
        submit_obj={"job_id": "job-chat"},
        get_obj={
            "job_id": "job-chat",
            "status": "completed",
            "completion_contract": {
                "answer_state": "provisional",
                "authoritative_answer_path": "jobs/job-chat/answer.md",
                "answer_provenance": {"contract_class": "research"},
            },
        },
        events_obj={"events": []},
        answer_obj=None,
    )

    assert outcome == "completed_not_final"
    assert acceptable is False
    assert completed is False


def test_run_live_matrix_accepts_wait_handoff_only_outcomes(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "test-token")

    def fake_run_command(cmd: list[str], *, env=None, cwd=module.REPO_ROOT):
        joined = " ".join(cmd)
        if "jobs submit" in joined and "--kind gemini_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-gem", "status": "queued"}),
                stderr="",
            )
        if "jobs get job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "job_id": "job-gem",
                        "status": "in_progress",
                        "phase": "wait",
                        "prompt_sent_at": 123.0,
                        "conversation_url": "https://gemini.google.com/app/test",
                    }
                ),
                stderr="",
            )
        if "jobs events job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": []}),
                stderr="",
            )
        if "jobs submit" in joined and "--kind chatgpt_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-chat", "status": "queued"}),
                stderr="",
            )
        if "jobs get job-chat" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "job_id": "job-chat",
                        "status": "in_progress",
                        "phase": "wait",
                        "prompt_sent_at": 456.0,
                        "conversation_url": "https://chatgpt.com/c/test",
                    }
                ),
                stderr="",
            )
        if "jobs events job-chat" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": []}),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_live_matrix(output_dir=tmp_path / "bundle", python_bin="/tmp/python")

    assert result["ok"] is True
    assert result["any_completed"] is False
    assert result["any_handoff"] is True
    providers = {item["provider"]: item for item in result["providers"]}
    assert providers["gemini"]["outcome"] == "wait_handoff_pending"
    assert providers["chatgpt"]["outcome"] == "wait_handoff_pending"


def test_run_live_matrix_classifies_realistic_provider_outcomes(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "test-token")

    def fake_run_command(cmd: list[str], *, env=None, cwd=module.REPO_ROOT):
        joined = " ".join(cmd)
        if "jobs submit" in joined and "--kind chatgpt_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-chat", "status": "queued"}),
                stderr="",
            )
        if "jobs get job-chat" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "job_id": "job-chat",
                        "status": "in_progress",
                        "conversation_export_path": "jobs/job-chat/conversation.json",
                    }
                ),
                stderr="",
            )
        if "jobs events job-chat" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": [{"type": "conversation_exported"}]}),
                stderr="",
            )
        if "jobs submit" in joined and "--kind gemini_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-gem", "status": "queued"}),
                stderr="",
            )
        if "jobs get job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-gem", "status": "completed"}),
                stderr="",
            )
        if "jobs events job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": []}),
                stderr="",
            )
        if "jobs answer job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"answer": {"chunk": "ok"}}),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_live_matrix(output_dir=tmp_path / "bundle", python_bin="/tmp/python")

    assert result["ok"] is True
    assert result["any_completed"] is True
    providers = {item["provider"]: item for item in result["providers"]}
    assert providers["chatgpt"]["outcome"] == "exported_pending_wait"
    assert providers["chatgpt"]["acceptable"] is True
    assert providers["gemini"]["outcome"] == "completed"
    assert providers["gemini"]["completed"] is True
    assert set(providers) == {"gemini", "chatgpt"}
    summary = json.loads((tmp_path / "bundle" / "summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is True


def test_run_live_matrix_waits_through_queue_and_retry_after(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "test-token")
    sleep_calls: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    calls = {
        "gemini_get": 0,
        "chatgpt_get": 0,
    }

    def fake_run_command(cmd: list[str], *, env=None, cwd=module.REPO_ROOT):
        joined = " ".join(cmd)
        if "jobs submit" in joined and "--kind gemini_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "job_id": "job-gem",
                        "status": "queued",
                        "estimated_wait_seconds": 183,
                    }
                ),
                stderr="",
            )
        if "jobs get job-gem" in joined:
            calls["gemini_get"] += 1
            if calls["gemini_get"] == 1:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps(
                        {
                            "job_id": "job-gem",
                            "status": "in_progress",
                            "estimated_wait_seconds": 183,
                            "phase": "send",
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-gem", "status": "completed"}),
                stderr="",
            )
        if "jobs events job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": []}),
                stderr="",
            )
        if "jobs answer job-gem" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"answer": {"chunk": "ok"}}),
                stderr="",
            )
        if "jobs submit" in joined and "--kind chatgpt_web.ask" in joined:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"job_id": "job-chat", "status": "queued"}),
                stderr="",
            )
        if "jobs get job-chat" in joined:
            calls["chatgpt_get"] += 1
            if calls["chatgpt_get"] == 1:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps(
                        {
                            "job_id": "job-chat",
                            "status": "in_progress",
                            "retry_after_seconds": 26,
                            "phase": "wait",
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "job_id": "job-chat",
                        "status": "in_progress",
                        "conversation_export_path": "jobs/job-chat/conversation.json",
                    }
                ),
                stderr="",
            )
        if "jobs events job-chat" in joined:
            if calls["chatgpt_get"] >= 2:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps({"events": [{"type": "conversation_exported"}]}),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"events": []}),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_live_matrix(output_dir=tmp_path / "bundle", python_bin="/tmp/python")

    assert result["ok"] is True
    providers = {item["provider"]: item for item in result["providers"]}
    assert providers["gemini"]["completed"] is True
    assert providers["chatgpt"]["outcome"] == "exported_pending_wait"
    assert providers["gemini"]["poll_attempts"] == 2
    assert providers["chatgpt"]["poll_attempts"] == 2
    assert set(providers) == {"gemini", "chatgpt"}
    assert sleep_calls
    assert max(sleep_calls) >= 20.0
