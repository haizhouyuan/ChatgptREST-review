from __future__ import annotations

from pathlib import Path

import pytest

from chatgptrest.core.config import load_config
from chatgptrest.executors.coding_plan import CodingPlanExecutor
from chatgptrest.executors.factory import executor_for_job
from chatgptrest.executors.local_llm import LocalLLMExecutor


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_CHATGPT_MCP_URL", "http://127.0.0.1:18701/mcp")
    return tmp_path


def test_factory_resolves_local_llm_ask(env: Path) -> None:  # noqa: ARG001
    cfg = load_config()
    ex = executor_for_job(cfg, "local_llm.ask")
    assert isinstance(ex, LocalLLMExecutor)


def test_factory_resolves_coding_plan_ask(env: Path) -> None:  # noqa: ARG001
    cfg = load_config()
    ex = executor_for_job(cfg, "coding_plan.ask")
    assert isinstance(ex, CodingPlanExecutor)
