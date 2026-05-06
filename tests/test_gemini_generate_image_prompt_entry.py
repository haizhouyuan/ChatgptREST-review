from __future__ import annotations

import asyncio

from chatgpt_web_mcp.providers.gemini.generate_image import _gemini_enter_image_prompt
from chatgpt_web_mcp.providers.gemini.generate_image import _gemini_capture_image_bytes_from_page


class _DummyKeyboard:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def press(self, key: str) -> None:
        self.events.append(("press", key))

    async def insert_text(self, text: str) -> None:
        self.events.append(("insert_text", text))


class _DummyPage:
    def __init__(self) -> None:
        self.keyboard = _DummyKeyboard()


class _PromptBox:
    pass


def test_gemini_enter_image_prompt_falls_back_to_keyboard(monkeypatch) -> None:
    async def _boom(prompt_box, prompt: str):  # noqa: ANN001,ARG001
        raise RuntimeError("fill not supported")

    async def _focus(page, prompt_box):  # noqa: ANN001,ARG001
        return prompt_box

    async def _pause(page):  # noqa: ANN001,ARG001
        return None

    monkeypatch.setattr("chatgpt_web_mcp.providers.gemini.generate_image._type_question", _boom)
    monkeypatch.setattr("chatgpt_web_mcp.providers.gemini.generate_image._gemini_focus_prompt_box", _focus)
    monkeypatch.setattr("chatgpt_web_mcp.providers.gemini.generate_image._human_pause", _pause)

    page = _DummyPage()
    prompt_box = _PromptBox()
    asyncio.run(_gemini_enter_image_prompt(page, prompt_box, "draw this"))

    assert page.keyboard.events == [
        ("press", "Control+A"),
        ("press", "Backspace"),
        ("insert_text", "draw this"),
    ]


class _ShotImg:
    def __init__(self, src: str) -> None:
        self._src = src

    async def get_attribute(self, name: str):
        if name == "src":
            return self._src
        return None

    async def screenshot(self, type: str = "png"):
        assert type == "png"
        return b"png-bytes"


class _Imgs:
    def __init__(self, srcs: list[str]) -> None:
        self.srcs = srcs

    async def count(self):
        return len(self.srcs)

    def nth(self, idx: int):
        return _ShotImg(self.srcs[idx])


class _PageWithImages:
    def __init__(self, srcs: list[str]) -> None:
        self._srcs = srcs

    def locator(self, selector: str):
        assert selector == "main img"
        return _Imgs(self._srcs)


def test_gemini_capture_image_bytes_from_page_uses_matching_img_screenshot() -> None:
    page = _PageWithImages(["blob:one", "blob:target"])
    raw, mime_type = asyncio.run(_gemini_capture_image_bytes_from_page(page, src="blob:target"))
    assert raw == b"png-bytes"
    assert mime_type == "image/png"
