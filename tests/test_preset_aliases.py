from __future__ import annotations

from chatgptrest.api.routes_jobs import (
    _validate_chatgpt_web_ask_preset,
    _validate_gemini_web_ask_preset,
    _validate_qwen_web_ask_preset,
)


def test_chatgpt_web_preset_default_aliases_to_auto() -> None:
    params = {"preset": "default"}
    _validate_chatgpt_web_ask_preset(params)
    assert params["preset"] == "auto"


def test_chatgpt_web_preset_deep_research_alias_enables_dr() -> None:
    params = {"preset": "deep_research", "deep_research": False}
    _validate_chatgpt_web_ask_preset(params)
    assert params["preset"] == "thinking_heavy"
    assert params["deep_research"] is True


def test_chatgpt_web_preset_research_alias_enables_dr() -> None:
    params = {"preset": "research"}
    _validate_chatgpt_web_ask_preset(params)
    assert params["preset"] == "thinking_heavy"
    assert params["deep_research"] is True


def test_gemini_web_preset_default_aliases_to_pro() -> None:
    params = {"preset": "default"}
    _validate_gemini_web_ask_preset(params)
    assert params["preset"] == "pro"


def test_qwen_web_preset_default_aliases_to_auto() -> None:
    params = {"preset": "default"}
    _validate_qwen_web_ask_preset(params)
    assert params["preset"] == "auto"
