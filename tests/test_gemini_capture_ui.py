from __future__ import annotations

import asyncio

from chatgpt_web_mcp.providers.gemini import capture_ui as gemini_capture_ui


class _DummyPage:
    pass


async def _noop_prompt(*_args, **_kwargs):
    return "prompt"


async def _noop_pause(*_args, **_kwargs) -> None:
    return None


def test_looks_like_detached_dom_capture() -> None:
    assert gemini_capture_ui._looks_like_detached_dom_capture(
        {
            "error_type": "Error",
            "error": "Locator.screenshot: Element is not attached to the DOM",
        }
    )
    assert not gemini_capture_ui._looks_like_detached_dom_capture(
        {
            "error_type": "NotFound",
            "error": "element not found",
        }
    )


def test_capture_composer_prompt_retries_after_detached_dom(monkeypatch) -> None:
    calls: list[str] = []

    async def _fake_focus(_page, prompt):
        calls.append(f"focus:{prompt}")
        return f"focused:{prompt}"

    async def _fake_find(_page, timeout_ms: int):
        calls.append(f"find:{timeout_ms}")
        return "refetched"

    async def _fake_screenshot(_page, *, target: str, out_dir, locator):
        calls.append(f"screenshot:{locator}")
        if locator == "focused:prompt":
            return {
                "target": target,
                "error_type": "Error",
                "error": "Locator.screenshot: Element is not attached to the DOM",
            }
        return {
            "target": target,
            "path": str(out_dir / "composer_prompt.png"),
            "mode": "element",
        }

    monkeypatch.setattr(gemini_capture_ui, "_gemini_focus_prompt_box", _fake_focus)
    monkeypatch.setattr(gemini_capture_ui, "_gemini_find_prompt_box", _fake_find)
    monkeypatch.setattr(gemini_capture_ui, "_ui_screenshot", _fake_screenshot)
    monkeypatch.setattr(gemini_capture_ui, "_human_pause", _noop_pause)

    result = asyncio.run(
        gemini_capture_ui._capture_composer_prompt(
            _DummyPage(),
            prompt="prompt",
            run_dir=gemini_capture_ui.Path("/tmp/gemini-capture-ui-test"),
        )
    )

    assert result["path"].endswith("composer_prompt.png")
    assert result["retried_after_detached_dom"] is True
    assert calls == [
        "focus:prompt",
        "screenshot:focused:prompt",
        "find:3000",
        "focus:refetched",
        "screenshot:focused:refetched",
    ]
