import asyncio
import re
import time

from chatgpt_web_mcp.providers.gemini import core as gemini_core
from chatgpt_web_mcp.providers.gemini.self_check import _self_check_error_result
from chatgpt_web_mcp.server import (
    _gemini_classify_error_type,
    _gemini_infer_tool_checked_from_placeholder,
    _gemini_mode_is_ambiguous,
    _gemini_mode_is_pro,
    _gemini_set_tool_checked,
    _gemini_mode_switch_fail_open,
    _gemini_tool_label_matches,
    _gemini_tool_checked_from_attr,
)


def test_gemini_mode_is_pro_variants() -> None:
    assert _gemini_mode_is_pro("Pro")
    assert _gemini_mode_is_pro("Pro · Deep Think")
    assert _gemini_mode_is_pro("当前模式 Pro")
    assert not _gemini_mode_is_pro("Thinking")


def test_gemini_mode_is_ambiguous_variants() -> None:
    assert _gemini_mode_is_ambiguous("模式")
    assert _gemini_mode_is_ambiguous("Mode")
    assert _gemini_mode_is_ambiguous("mode selector")
    assert not _gemini_mode_is_ambiguous("Pro")


def test_gemini_mode_switch_fail_open_default(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODE_SWITCH_FAIL_OPEN", raising=False)
    assert _gemini_mode_switch_fail_open() is True


def test_gemini_mode_switch_fail_open_respects_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODE_SWITCH_FAIL_OPEN", "0")
    assert _gemini_mode_switch_fail_open() is False
    monkeypatch.setenv("GEMINI_MODE_SWITCH_FAIL_OPEN", "1")
    assert _gemini_mode_switch_fail_open() is True


def test_gemini_import_code_not_found_classification() -> None:
    assert (
        _gemini_classify_error_type(
            error_text="Gemini tool not found: (导入代码|Import code)",
            fallback="RuntimeError",
        )
        == "GeminiImportCodeNotFound"
    )


def test_gemini_deep_research_not_found_classification() -> None:
    assert (
        _gemini_classify_error_type(
            error_text="Gemini tool not found: (Deep Research|深入研究|深度研究)",
            fallback="RuntimeError",
        )
        == "GeminiDeepResearchToolNotFound"
    )


def test_gemini_tool_checked_from_attr_supports_deselect_chip_class() -> None:
    assert _gemini_tool_checked_from_attr(None, "toolbox-drawer-item-deselect-button") is True
    assert _gemini_tool_checked_from_attr("false", "toolbox-drawer-item-deselect-button") is False


def test_gemini_infer_tool_checked_from_placeholder_variants() -> None:
    assert (
        _gemini_infer_tool_checked_from_placeholder(
            label_pattern=r"(Deep Research|深入研究|深度研究)",
            placeholder="你想研究什么？",
        )
        is True
    )
    assert (
        _gemini_infer_tool_checked_from_placeholder(
            label_pattern=r"(生成图片|生成图像|Generate image)",
            placeholder="Describe your image",
        )
        is True
    )
    assert (
        _gemini_infer_tool_checked_from_placeholder(
            label_pattern=r"(Deep\\s*Think|深度思考|深入思考)",
            placeholder="与 Gemini 对话",
        )
        is None
    )


def test_gemini_tool_label_matches_deep_research_fuzzy() -> None:
    label_re = re.compile(r"(Deep Research|深入研究|深度研究)", re.I)
    assert _gemini_tool_label_matches(label_re=label_re, text="Deep Research")
    assert _gemini_tool_label_matches(label_re=label_re, text="深度调研")
    assert _gemini_tool_label_matches(label_re=label_re, text="深入調研")
    assert not _gemini_tool_label_matches(label_re=label_re, text="生成图片")


def test_gemini_tool_label_matches_deep_think_variant_thinking_with_3_pro() -> None:
    label_re = re.compile(r"(Deep\s*Think|Thinking\s+with\s+3\s*Pro|深度思考|深入思考)", re.I)
    assert _gemini_tool_label_matches(label_re=label_re, text="Thinking with 3 Pro")
    assert _gemini_tool_label_matches(label_re=label_re, text="Deep Think")


def test_gemini_set_tool_checked_accepts_fallback_inference(monkeypatch) -> None:
    class _FakeItem:
        async def get_attribute(self, _name: str):
            return None

        async def scroll_into_view_if_needed(self) -> None:
            return None

        async def click(self) -> None:
            return None

    async def _fake_find_tool_item(*_args, **_kwargs):
        return _FakeItem()

    async def _fake_infer_tool_checked_state(*_args, **_kwargs):
        return True

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gemini_core, "_gemini_find_tool_item", _fake_find_tool_item)
    monkeypatch.setattr(gemini_core, "_gemini_infer_tool_checked_state", _fake_infer_tool_checked_state)
    monkeypatch.setattr(gemini_core, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_core, "_human_pause", _noop)

    got = asyncio.run(
        _gemini_set_tool_checked(
            object(),
            label_re=re.compile(r"(Deep Research|深入研究|深度研究)", re.I),
            checked=True,
            ctx=None,
            fail_open=False,
        )
    )
    assert got is True


def test_gemini_set_tool_checked_accepts_fallback_inference_false(monkeypatch) -> None:
    class _FakeItem:
        async def get_attribute(self, _name: str):
            return None

        async def scroll_into_view_if_needed(self) -> None:
            return None

        async def click(self) -> None:
            return None

    async def _fake_find_tool_item(*_args, **_kwargs):
        return _FakeItem()

    async def _fake_infer_tool_checked_state(*_args, **_kwargs):
        return False

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gemini_core, "_gemini_find_tool_item", _fake_find_tool_item)
    monkeypatch.setattr(gemini_core, "_gemini_infer_tool_checked_state", _fake_infer_tool_checked_state)
    monkeypatch.setattr(gemini_core, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_core, "_human_pause", _noop)

    got = asyncio.run(
        _gemini_set_tool_checked(
            object(),
            label_re=re.compile(r"(Deep Research|深入研究|深度研究)", re.I),
            checked=False,
            ctx=None,
            fail_open=False,
        )
    )
    assert got is False


def test_gemini_self_check_error_result_classifies_unsupported_region() -> None:
    class _Page:
        url = "https://gemini.google.com/app"

    payload = _self_check_error_result(
        exc=RuntimeError("Gemini 目前不支持你所在的地区"),
        page=_Page(),
        started_at=time.time() - 1.0,
        run_id="run-gemini-self-check",
        mode_text="",
        tools_btn={"visible": False},
        tools=[],
        artifacts={},
    )
    assert payload["error_type"] == "GeminiUnsupportedRegion"
    assert payload["region_supported"] is False
