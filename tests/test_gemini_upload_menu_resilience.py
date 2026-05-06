from __future__ import annotations

import asyncio
import re

from chatgpt_web_mcp.providers.gemini import core as gemini_core


class _FakeButton:
    def __init__(self, *, aria_label: str, visible: bool = True) -> None:
        self.aria_label = aria_label
        self.visible = visible
        self.clicked = False


class _FakeLocator:
    def __init__(self, buttons: list[_FakeButton]) -> None:
        self._buttons = list(buttons)

    @property
    def first(self) -> "_FakeLocator":
        if not self._buttons:
            return _FakeLocator([])
        return _FakeLocator([self._buttons[0]])

    async def count(self) -> int:
        return len(self._buttons)

    async def is_visible(self) -> bool:
        return bool(self._buttons and self._buttons[0].visible)

    async def click(self) -> None:
        if not self._buttons:
            raise RuntimeError("locator not present")
        self._buttons[0].clicked = True


class _FakePage:
    def __init__(self, buttons: list[_FakeButton]) -> None:
        self._buttons = list(buttons)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator([button for button in self._buttons if _matches_selector(selector, button)])

    async def wait_for_timeout(self, _ms: int) -> None:
        return None


def _matches_selector(selector: str, button: _FakeButton) -> bool:
    if selector == "button.upload-card-button":
        return False
    if selector == "button[aria-controls='upload-file-menu']":
        return False
    exact = re.match(r"button\[aria-label='(.+)'\]$", selector)
    if exact:
        return button.aria_label == exact.group(1)
    contains_ci = re.match(r"button\[aria-label\*='(.+)' i\]$", selector)
    if contains_ci:
        return contains_ci.group(1).lower() in button.aria_label.lower()
    contains = re.match(r"button\[aria-label\*='(.+)'\]$", selector)
    if contains:
        return contains.group(1) in button.aria_label
    return False


def test_gemini_open_upload_menu_accepts_new_input_area_menu_label(monkeypatch) -> None:
    current_label = "打开输入区域菜单，以选择工具和上传内容类型"
    button = _FakeButton(aria_label=current_label)
    page = _FakePage([button])

    async def _noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(gemini_core, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_core, "_human_pause", _noop)

    asyncio.run(gemini_core._gemini_open_upload_menu(page, ctx=None))

    assert button.clicked is True


def test_gemini_open_upload_menu_accepts_new_english_input_area_label(monkeypatch) -> None:
    label = "Open input area menu to select tools and upload content types"
    button = _FakeButton(aria_label=label)
    page = _FakePage([button])

    async def _noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(gemini_core, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_core, "_human_pause", _noop)

    asyncio.run(gemini_core._gemini_open_upload_menu(page, ctx=None))

    assert button.clicked is True


def test_gemini_open_upload_menu_prefers_exact_current_label_over_generic_match(monkeypatch) -> None:
    generic = _FakeButton(aria_label="打开输入区域菜单")
    current = _FakeButton(aria_label="打开输入区域菜单，以选择工具和上传内容类型")
    page = _FakePage([generic, current])

    async def _noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(gemini_core, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_core, "_human_pause", _noop)

    asyncio.run(gemini_core._gemini_open_upload_menu(page, ctx=None))

    assert current.clicked is True
    assert generic.clicked is False
