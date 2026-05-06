from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from chatgptrest.core.config import load_config
from chatgptrest.executors import repair as repair_mod
from chatgptrest.executors.repair import RepairOpenPrExecutor
from chatgptrest.worker.worker import _executor_for_job


@pytest.fixture()
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return load_config()


def test_executor_for_repair_open_pr(cfg):
    executor = _executor_for_job(cfg, "repair.open_pr", tool_caller=None)
    assert isinstance(executor, RepairOpenPrExecutor)


def test_repair_open_pr_uses_mode_based_codex_profile(cfg, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"ok": True, "output": {"diff": "", "tests": []}}

    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)

    executor = RepairOpenPrExecutor(cfg=cfg, tool_caller=None)
    result = asyncio.run(
        executor.run(
            job_id="repair-open-pr-p1",
            kind="repair.open_pr",
            input={"symptom": "patch the runtime guard"},
            params={"mode": "p1", "timeout_seconds": 120},
        )
    )
    assert result.status == "completed"
    assert captured["model"] == "gpt-5.3-codex"
    assert captured["config_overrides"] == ['model_reasoning_effort="medium"']

    report_path = cfg.artifacts_dir / "jobs" / "repair-open-pr-p1" / "repair_open_pr_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["codex_profile"]["model"] == "gpt-5.3-codex"
    assert report["codex_profile"]["reasoning_effort"] == "medium"


def test_repair_open_pr_explicit_model_and_reasoning_override_profile(cfg, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run_codex_with_schema(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"ok": True, "output": {"diff": "", "tests": []}}

    monkeypatch.setattr(repair_mod, "_run_codex_with_schema", fake_run_codex_with_schema)

    executor = RepairOpenPrExecutor(cfg=cfg, tool_caller=None)
    result = asyncio.run(
        executor.run(
            job_id="repair-open-pr-explicit",
            kind="repair.open_pr",
            input={"symptom": "patch the runtime guard"},
            params={
                "mode": "p2",
                "timeout_seconds": 120,
                "model": "gpt-5.3-codex-spark",
                "reasoning_effort": "medium",
            },
        )
    )
    assert result.status == "completed"
    assert captured["model"] == "gpt-5.3-codex-spark"
    assert captured["config_overrides"] == ['model_reasoning_effort="medium"']

    report_path = cfg.artifacts_dir / "jobs" / "repair-open-pr-explicit" / "repair_open_pr_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["codex_profile"]["model_source"] == "explicit"
    assert report["codex_profile"]["reasoning_source"] == "explicit"
