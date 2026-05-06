from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from chatgpt_web_mcp.server import _chatgpt_regenerate_reserve, _chatgpt_wait_refresh_reserve


@pytest.fixture()
def _no_prompt_guard_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPT_DISABLE_ANSWER_NOW", "1")


def test_regenerate_reserve_enforces_window_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_prompt_guard_env):
    state_file = tmp_path / "regen_state.json"
    monkeypatch.setenv("CHATGPT_REGENERATE_STATE_FILE", str(state_file))
    monkeypatch.setenv("CHATGPT_REGENERATE_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("CHATGPT_REGENERATE_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("CHATGPT_REGENERATE_MAX_PER_WINDOW", "2")

    g1 = asyncio.run(_chatgpt_regenerate_reserve(conversation_id="c1", reason="t1", phase="p"))
    assert g1["allowed"] is True

    g2 = asyncio.run(_chatgpt_regenerate_reserve(conversation_id="c1", reason="t2", phase="p"))
    assert g2["allowed"] is True

    g3 = asyncio.run(_chatgpt_regenerate_reserve(conversation_id="c1", reason="t3", phase="p"))
    assert g3["allowed"] is False
    assert g3["window_max"] == 2
    assert g3["window_count"] == 2
    assert g3["window_next_allowed_at"] is not None


def test_wait_refresh_reserve_enforces_window_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_prompt_guard_env):
    state_file = tmp_path / "refresh_state.json"
    monkeypatch.setenv("CHATGPT_WAIT_REFRESH_STATE_FILE", str(state_file))
    monkeypatch.setenv("CHATGPT_WAIT_REFRESH_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("CHATGPT_WAIT_REFRESH_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("CHATGPT_WAIT_REFRESH_MAX_PER_WINDOW", "2")

    g1 = asyncio.run(_chatgpt_wait_refresh_reserve(conversation_id="c1", reason="t1", phase="p"))
    assert g1["allowed"] is True

    g2 = asyncio.run(_chatgpt_wait_refresh_reserve(conversation_id="c1", reason="t2", phase="p"))
    assert g2["allowed"] is True

    g3 = asyncio.run(_chatgpt_wait_refresh_reserve(conversation_id="c1", reason="t3", phase="p"))
    assert g3["allowed"] is False
    assert g3["window_max"] == 2
    assert g3["window_count"] == 2
    assert g3["window_next_allowed_at"] is not None

