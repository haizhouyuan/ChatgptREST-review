from __future__ import annotations

from pathlib import Path

import pytest

from chatgptrest.core.config import load_config
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

