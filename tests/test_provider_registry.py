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
    conversation_platform,
    provider_capability_profile_for_kind,
    provider_id_for_kind,
    provider_spec_for_ask_kind,
    provider_spec_for_kind,
    provider_specs,
    validate_ask_preset,
)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("chatgpt_web.ask", "chatgpt_web_send"),
        ("gemini_web.ask", "gemini_web_send"),
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
    )
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="chatgpt_web.ask") == 61
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="gemini_web.ask") == 33
    assert ask_min_prompt_interval_seconds(cfg=cfg, kind="qwen_web.ask") is None
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


def test_provider_specs_exposes_expected_provider_capability_matrix() -> None:
    specs = {spec.provider_id: spec for spec in provider_specs()}
    assert set(specs) == {"chatgpt", "gemini"}

    chatgpt = specs["chatgpt"]
    assert chatgpt.ask_kind == "chatgpt_web.ask"
    assert chatgpt.kind_namespace == "chatgpt_web."
    assert chatgpt.rate_limit_key == "chatgpt_web_send"
    assert chatgpt.default_preset == "auto"
    assert chatgpt.has_true_non_pro is True
    assert chatgpt.auto_semantics == "true_non_pro"
    assert chatgpt.safe_non_pro_fallback == "auto"
    assert chatgpt.deep_research_support == "flag_only"
    assert chatgpt.supported_presets == frozenset({"auto", "pro_extended", "thinking_heavy", "thinking_extended", "deep_research"})

    gemini = specs["gemini"]
    assert gemini.ask_kind == "gemini_web.ask"
    assert gemini.kind_namespace == "gemini_web."
    assert gemini.rate_limit_key == "gemini_web_send"
    assert gemini.default_preset == "pro"
    assert gemini.has_true_non_pro is False
    assert gemini.auto_semantics == "alias_to_pro"
    assert gemini.safe_non_pro_fallback is None
    assert gemini.deep_research_support == "tool_path"
    assert gemini.supported_presets == frozenset({"pro", "deep_think"})


def test_provider_lookup_helpers_resolve_kind_and_platform() -> None:
    assert provider_spec_for_ask_kind("chatgpt_web.ask").provider_id == "chatgpt"  # type: ignore[union-attr]
    assert provider_spec_for_kind("gemini_web.wait").provider_id == "gemini"  # type: ignore[union-attr]
    assert provider_id_for_kind("gemini_web.ask") == "gemini"
    assert conversation_platform("chatgpt_web.ask") == "chatgpt"
    assert conversation_platform("unknown.kind") == "unknown"
    profile = provider_capability_profile_for_kind("gemini_web.ask")
    assert profile is not None
    assert profile["auto_semantics"] == "alias_to_pro"
    assert profile["safe_non_pro_fallback"] is None


def test_validate_ask_preset_rejects_missing_preset_with_supported_list() -> None:
    with pytest.raises(PresetValidationError) as chatgpt_exc:
        validate_ask_preset(kind="chatgpt_web.ask", params_obj={})
    chatgpt_detail = chatgpt_exc.value.detail
    assert chatgpt_detail["error"] == "missing_preset"
    assert chatgpt_detail["provider_id"] == "chatgpt"
    assert chatgpt_detail["provider_capability_profile"]["auto_semantics"] == "true_non_pro"
    assert chatgpt_detail["supported"] == sorted({"auto", "pro_extended", "thinking_heavy", "thinking_extended", "deep_research"})

    with pytest.raises(PresetValidationError) as gemini_exc:
        validate_ask_preset(kind="gemini_web.ask", params_obj={})
    gemini_detail = gemini_exc.value.detail
    assert gemini_detail["error"] == "missing_preset"
    assert gemini_detail["provider_id"] == "gemini"
    assert gemini_detail["provider_capability_profile"]["auto_semantics"] == "alias_to_pro"
    assert gemini_detail["supported"] == ["deep_think", "pro"]


def test_validate_ask_preset_rejects_invalid_preset_per_provider() -> None:
    with pytest.raises(PresetValidationError) as exc_info:
        validate_ask_preset(kind="gemini_web.ask", params_obj={"preset": "invalid"})
    detail = exc_info.value.detail
    assert detail["error"] == "invalid_preset"
    assert detail["provider_id"] == "gemini"
    assert detail["supported"] == ["deep_think", "pro"]


def test_validate_ask_preset_normalizes_gemini_deepthink_aliases() -> None:
    params = {"preset": "deepthink"}
    validate_ask_preset(kind="gemini_web.ask", params_obj=params)
    assert params["preset"] == "deep_think"

    params2 = {"preset": "pro_deep_think"}
    validate_ask_preset(kind="gemini_web.ask", params_obj=params2)
    assert params2["preset"] == "deep_think"

def test_validate_ask_preset_rejects_removed_provider() -> None:
    params = {"preset": "invalid"}
    with pytest.raises(PresetValidationError) as exc_info:
        validate_ask_preset(kind="qwen_web.ask", params_obj=params)
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("error") == "provider_removed"


def test_thread_url_detection() -> None:
    assert looks_like_thread_url("chatgpt_web.ask", "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert looks_like_thread_url("gemini_web.ask", "https://gemini.google.com/app/abc123def456")
    assert not looks_like_thread_url("qwen_web.ask", "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert not looks_like_thread_url("gemini_web.ask", "https://gemini.google.com/app")


def test_worker_autofix_kind_registry() -> None:
    assert is_worker_autofix_kind("chatgpt_web.ask")
    assert is_worker_autofix_kind("gemini_web.ask")
    assert not is_worker_autofix_kind("qwen_web.ask")
    assert is_worker_autofix_kind("gemini_web.generate_image")
    assert not is_worker_autofix_kind("repair.check")
