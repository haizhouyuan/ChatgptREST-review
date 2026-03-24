from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatgptrest.providers.registry import (
    PresetValidationError,
    ask_min_prompt_interval_seconds,
    ask_rate_limit_key,
    is_provider_web_kind,
    is_web_ask_kind,
    is_worker_autofix_kind,
    looks_like_thread_url,
    validate_ask_preset,
)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("chatgpt_web.ask", "chatgpt_web_send"),
        ("gemini_web.ask", "gemini_web_send"),
        ("qwen_web.ask", "qwen_web_send"),
    ],
)
def test_ask_rate_limit_key(kind: str, expected: str) -> None:
    assert ask_rate_limit_key(kind) == expected
    assert is_web_ask_kind(kind) is True
    assert is_provider_web_kind(kind) is True


def test_registry_reads_min_interval_from_config() -> None:
    cfg = SimpleNamespace(
        min_prompt_interval_seconds=61,
        gemini_min_prompt_interval_seconds=33,
        qwen_min_prompt_interval_seconds=5,
    )
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="chatgpt_web.ask") == 61
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="gemini_web.ask") == 33
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="qwen_web.ask") == 5
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="dummy.error_meta") is None


def test_validate_ask_preset_aliases() -> None:
    chatgpt_params = {"preset": "default"}
    validate_ask_preset(kind="chatgpt_web.ask", params_obj=chatgpt_params)
    assert chatgpt_params["preset"] == "auto"

    chatgpt_dr_params = {"preset": "deep_research", "deep_research": False}
    validate_ask_preset(kind="chatgpt_web.ask", params_obj=chatgpt_dr_params)
    assert chatgpt_dr_params["preset"] == "thinking_heavy"
    assert chatgpt_dr_params["deep_research"] is True

    gemini_params = {"preset": "defaults"}
    validate_ask_preset(kind="gemini_web.ask", params_obj=gemini_params)
    assert gemini_params["preset"] == "pro"

    gemini_params2 = {"preset": "thinking"}
    validate_ask_preset(kind="gemini_web.ask", params_obj=gemini_params2)
    assert gemini_params2["preset"] == "pro"

    qwen_params = {"preset": "thinking"}
    validate_ask_preset(kind="qwen_web.ask", params_obj=qwen_params)
    assert qwen_params["preset"] == "deep_thinking"


def test_validate_ask_preset_raises_structured_error() -> None:
    params = {"preset": "invalid"}
    with pytest.raises(PresetValidationError) as exc_info:
        validate_ask_preset(kind="qwen_web.ask", params_obj=params)
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("error") == "invalid_preset"


def test_thread_url_detection() -> None:
    assert looks_like_thread_url("chatgpt_web.ask", "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert looks_like_thread_url("gemini_web.ask", "https://gemini.google.com/app/abc123def456")
    assert looks_like_thread_url("qwen_web.ask", "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert not looks_like_thread_url("gemini_web.ask", "https://gemini.google.com/app")


def test_worker_autofix_kind_registry() -> None:
    assert is_worker_autofix_kind("chatgpt_web.ask")
    assert is_worker_autofix_kind("gemini_web.ask")
    assert is_worker_autofix_kind("qwen_web.ask")
    assert is_worker_autofix_kind("gemini_web.generate_image")
    assert not is_worker_autofix_kind("repair.check")
