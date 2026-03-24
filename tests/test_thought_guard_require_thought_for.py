from __future__ import annotations

import pytest

from chatgptrest.executors import chatgpt_web_mcp as m
from chatgptrest.executors.config import ChatGPTExecutorConfig


def test_thought_guard_require_thought_for_fail_closed_on_missing_observation() -> None:
    abnormal, details = m._thought_guard_is_abnormal(
        obs=None,
        min_seconds=300,
        require_thought_for=True,
        trigger_too_short=False,
        trigger_skipping=False,
        trigger_answer_now=False,
    )
    assert abnormal is True
    assert details.get("missing_observation") is True


def test_thought_guard_require_thought_for_triggers_even_if_other_markers_ignored() -> None:
    obs = {
        "skipping": True,
        "answer_now_visible": True,
        # No Thought-for duration present.
    }
    abnormal, details = m._thought_guard_is_abnormal(
        obs=obs,
        min_seconds=300,
        require_thought_for=True,
        trigger_too_short=False,
        trigger_skipping=False,
        trigger_answer_now=False,
    )
    assert abnormal is True
    assert details.get("thought_for_present") is False
    assert details.get("reason") == "missing_thought_for"


def test_thought_guard_require_thought_for_accepts_duration() -> None:
    obs = {
        "thought_seconds": 420,
        "thought_for_present": True,
        "skipping": False,
        "answer_now_visible": False,
    }
    abnormal, details = m._thought_guard_is_abnormal(
        obs=obs,
        min_seconds=300,
        require_thought_for=True,
        trigger_too_short=False,
        trigger_skipping=False,
        trigger_answer_now=False,
    )
    assert abnormal is False
    assert details.get("thought_for_present") is True


def test_thought_guard_too_short_still_triggers_when_enabled() -> None:
    obs = {"thought_seconds": 10, "thought_for_present": True, "skipping": False, "answer_now_visible": False}
    abnormal, details = m._thought_guard_is_abnormal(
        obs=obs,
        min_seconds=300,
        require_thought_for=False,
        trigger_too_short=True,
        trigger_skipping=False,
        trigger_answer_now=False,
    )
    assert abnormal is True
    assert details.get("reason") == "thought_too_short"


def test_thought_guard_defaults_enable_auto_regenerate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS", raising=False)
    monkeypatch.delenv("CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE", raising=False)

    cfg = ChatGPTExecutorConfig()
    assert cfg.thought_guard_min_seconds == 300
    assert cfg.thought_guard_auto_regenerate is True
