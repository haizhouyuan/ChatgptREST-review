import asyncio
import re
from types import SimpleNamespace

import pytest

from chatgpt_web_mcp.providers.gemini import core as gemini_core


class _FakePage:
    def __init__(self) -> None:
        self.timeouts: list[int] = []
        self.more_clicked = 0
        self.drive_clicked = 0
        self.expanded = False

    async def wait_for_timeout(self, ms: int) -> None:
        self.timeouts.append(ms)

    def locator(self, selector: str):
        return _FakeLocator(self, selector)


class _FakeLocator:
    def __init__(self, page: _FakePage, selector: str) -> None:
        self._page = page
        self._selector = selector

    def _elements(self):
        if 'mat-mdc-list-item' not in self._selector and 'button' not in self._selector and 'role=' not in self._selector:
            return []
        elems = [_FakeMenuElement(self._page, kind='more', text='更多上传选项')]
        if self._page.expanded:
            elems.append(_FakeMenuElement(self._page, kind='drive', text='从云端硬盘添加'))
        return elems

    async def count(self) -> int:
        return len(self._elements())

    def nth(self, idx: int):
        return self._elements()[idx]


class _FakeMenuElement:
    def __init__(self, page: _FakePage, *, kind: str, text: str) -> None:
        self._page = page
        self._kind = kind
        self._text = text

    async def is_visible(self) -> bool:
        return True

    async def inner_text(self, timeout: int = 500) -> str:  # noqa: ARG002
        return self._text

    async def get_attribute(self, name: str):
        if name == 'aria-label':
            return self._text
        return ''

    async def click(self) -> None:
        if self._kind == 'more':
            self._page.more_clicked += 1
            self._page.expanded = True
        elif self._kind == 'drive':
            self._page.drive_clicked += 1

    async def scroll_into_view_if_needed(self, timeout: int = 2000) -> None:  # noqa: ARG002
        return None


def test_gemini_click_upload_menu_item_expands_more_upload_options(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(gemini_core, '_human_pause', _noop)

    page = _FakePage()
    asyncio.run(gemini_core._gemini_click_upload_menu_item(page, label_re=gemini_core._GEMINI_DRIVE_MENU_ITEM_RE))

    assert page.more_clicked >= 1
    assert page.drive_clicked == 1


def test_gemini_open_drive_picker_retries_after_picker_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    infos: list[str] = []

    async def _noop(*_args, **_kwargs) -> None:
        return None

    async def _fake_open_upload_menu(*_args, **_kwargs) -> None:
        calls.append('open_menu')

    async def _fake_click_upload_menu_item(*_args, **_kwargs) -> None:
        calls.append('click_item')

    attempts = {'count': 0}

    async def _fake_wait_for_drive_picker_modal_open(*_args, **_kwargs) -> None:
        attempts['count'] += 1
        calls.append(f'wait_picker_{attempts["count"]}')
        if attempts['count'] == 1:
            raise TimeoutError('Timed out waiting for visible Google Drive picker iframe.')

    async def _fake_info(_ctx, message: str) -> None:
        infos.append(message)

    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_closed_before_retry', _noop)
    monkeypatch.setattr(gemini_core, '_gemini_open_upload_menu', _fake_open_upload_menu)
    monkeypatch.setattr(gemini_core, '_gemini_click_upload_menu_item', _fake_click_upload_menu_item)
    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_modal_open', _fake_wait_for_drive_picker_modal_open)
    monkeypatch.setattr(gemini_core, '_gemini_dismiss_overlays', _noop)
    monkeypatch.setattr(gemini_core, '_ctx_info', _fake_info)

    page = _FakePage()
    asyncio.run(gemini_core._gemini_open_drive_picker(page, ctx=None, attempts=3))

    assert calls == ['open_menu', 'click_item', 'wait_picker_1', 'open_menu', 'click_item', 'wait_picker_2']
    assert any('attempt 1/3 failed' in item for item in infos)


def test_gemini_open_drive_picker_fails_closed_after_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_args, **_kwargs) -> None:
        return None

    async def _fake_open_upload_menu(*_args, **_kwargs) -> None:
        return None

    async def _fake_click_upload_menu_item(*_args, **_kwargs) -> None:
        return None

    async def _fake_wait_for_drive_picker_modal_open(*_args, **_kwargs) -> None:
        raise TimeoutError('Timed out waiting for visible Google Drive picker iframe.')

    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_closed_before_retry', _noop)
    monkeypatch.setattr(gemini_core, '_gemini_open_upload_menu', _fake_open_upload_menu)
    monkeypatch.setattr(gemini_core, '_gemini_click_upload_menu_item', _fake_click_upload_menu_item)
    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_modal_open', _fake_wait_for_drive_picker_modal_open)
    monkeypatch.setattr(gemini_core, '_gemini_dismiss_overlays', _noop)
    monkeypatch.setattr(gemini_core, '_ctx_info', _noop)

    page = _FakePage()
    with pytest.raises(RuntimeError, match=r'Gemini Drive picker unavailable after 2 attempt\(s\)') as excinfo:
        asyncio.run(gemini_core._gemini_open_drive_picker(page, ctx=None, attempts=2))

    assert 'Timed out waiting for visible Google Drive picker iframe.' in str(excinfo.value)


class _ZeroCountLocator:
    first = None

    def __init__(self) -> None:
        self.first = self

    async def count(self) -> int:
        return 0

    def locator(self, _selector: str):
        return self


class _FakePickerScope:
    def __init__(self, url: str, name: str = '') -> None:
        self.url = url
        self.name = name

    def locator(self, _selector: str):
        return _ZeroCountLocator()

    async def wait_for_timeout(self, _ms: int) -> None:
        return None


class _FakePickerProbePage(_FakePickerScope):
    def __init__(self, *, frames=None, popup_pages=None, iframe_debug=None, overlay_debug=None) -> None:
        super().__init__('https://gemini.google.com/app', 'gemini')
        self.frames = list(frames or [])
        pages = [self] + list(popup_pages or [])
        self.context = SimpleNamespace(pages=pages)
        self._iframe_debug = list(iframe_debug or [])
        self._overlay_debug = list(overlay_debug or [])

    async def evaluate(self, script: str):
        if "cdk-overlay-pane" in script or "role=\"dialog\"" in script:
            return list(self._overlay_debug)
        return list(self._iframe_debug)


def test_gemini_get_visible_drive_picker_frame_uses_popup_page_fallback() -> None:
    popup = _FakePickerScope('https://docs.google.com/picker?protocol=gadgets', 'picker-popup')
    page = _FakePickerProbePage(popup_pages=[popup])

    scope = asyncio.run(gemini_core._gemini_get_visible_drive_picker_frame(page, timeout_ms=50))

    assert scope is popup


def test_gemini_get_visible_drive_picker_frame_uses_attached_picker_frame_fallback() -> None:
    frame = _FakePickerScope('https://docs.google.com/picker?protocol=gadgets', 'picker-frame')
    page = _FakePickerProbePage(frames=[frame])

    scope = asyncio.run(gemini_core._gemini_get_visible_drive_picker_frame(page, timeout_ms=50))

    assert scope is frame


def test_gemini_get_visible_drive_picker_frame_timeout_includes_picker_debug() -> None:
    page = _FakePickerProbePage(iframe_debug=[{'src': 'https://example.com/other', 'visible': False}])

    with pytest.raises(TimeoutError, match=r'picker_debug=') as excinfo:
        asyncio.run(gemini_core._gemini_get_visible_drive_picker_frame(page, timeout_ms=20))

    assert 'visible_modal_count' in str(excinfo.value)


class _FakeConsentButton:
    def __init__(self, page, label: str) -> None:
        self._page = page
        self._label = label

    async def is_visible(self) -> bool:
        return True

    async def is_enabled(self) -> bool:
        return True

    async def inner_text(self, timeout: int = 500) -> str:  # noqa: ARG002
        return self._label

    async def get_attribute(self, name: str):  # noqa: ARG002
        return ''

    async def click(self) -> None:
        if self._label == '关联':
            self._page.accept_clicked += 1
            self._page.dialog_visible = False


class _FakeConsentButtons:
    def __init__(self, page) -> None:
        self._page = page

    async def count(self) -> int:
        return 2

    def nth(self, idx: int):
        return [_FakeConsentButton(self._page, '取消'), _FakeConsentButton(self._page, '关联')][idx]


class _FakeConsentDialog:
    def __init__(self, page) -> None:
        self._page = page

    async def inner_text(self, timeout: int = 500) -> str:  # noqa: ARG002
        return '关联 Google Workspace？ 取消 关联'

    def locator(self, selector: str):  # noqa: ARG002
        return _FakeConsentButtons(self._page)


class _FakeConsentDialogs:
    def __init__(self, page) -> None:
        self._page = page

    async def count(self) -> int:
        return 1 if self._page.dialog_visible else 0

    def nth(self, idx: int):  # noqa: ARG002
        return _FakeConsentDialog(self._page)


class _FakeConsentPage(_FakePage):
    def __init__(self) -> None:
        super().__init__()
        self.dialog_visible = True
        self.accept_clicked = 0

    def locator(self, selector: str):
        if 'cdk-overlay-pane:visible' in selector or 'mat-dialog-container:visible' in selector or "[role='dialog']:visible" in selector:
            return _FakeConsentDialogs(self)
        return super().locator(selector)


def test_gemini_maybe_accept_workspace_consent_clicks_accept(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(gemini_core, '_human_pause', _noop)
    monkeypatch.setattr(gemini_core, '_ctx_info', _noop)

    page = _FakeConsentPage()

    accepted = asyncio.run(gemini_core._gemini_maybe_accept_workspace_consent(page, ctx=None, timeout_ms=20))

    assert accepted is True
    assert page.accept_clicked == 1
    assert page.dialog_visible is False


def test_gemini_open_drive_picker_accepts_workspace_consent_before_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def _noop(*_args, **_kwargs) -> None:
        return None

    async def _fake_open_upload_menu(*_args, **_kwargs) -> None:
        calls.append('open_menu')

    async def _fake_click_upload_menu_item(*_args, **_kwargs) -> None:
        calls.append('click_item')

    async def _fake_accept_consent(*_args, **_kwargs) -> bool:
        calls.append('accept_consent')
        return True

    async def _fake_wait_for_drive_picker_modal_open(*_args, **kwargs) -> None:
        calls.append(f"wait_picker_{kwargs.get('timeout_ms')}")

    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_closed_before_retry', _noop)
    monkeypatch.setattr(gemini_core, '_gemini_open_upload_menu', _fake_open_upload_menu)
    monkeypatch.setattr(gemini_core, '_gemini_click_upload_menu_item', _fake_click_upload_menu_item)
    monkeypatch.setattr(gemini_core, '_gemini_maybe_accept_workspace_consent', _fake_accept_consent)
    monkeypatch.setattr(gemini_core, '_gemini_wait_for_drive_picker_modal_open', _fake_wait_for_drive_picker_modal_open)
    monkeypatch.setattr(gemini_core, '_gemini_dismiss_overlays', _noop)
    monkeypatch.setattr(gemini_core, '_ctx_info', _noop)

    page = _FakePage()
    asyncio.run(gemini_core._gemini_open_drive_picker(page, ctx=None, attempts=1))

    assert calls == ['open_menu', 'click_item', 'accept_consent', 'wait_picker_18000']


def test_gemini_get_visible_drive_picker_frame_timeout_includes_visible_overlays() -> None:
    page = _FakePickerProbePage(
        iframe_debug=[{'src': 'https://accounts.google.com/RotateCookiesPage', 'visible': False}],
        overlay_debug=[{'visible': True, 'text': '关联 Google Workspace？', 'className': 'global-consent-dialog-panel'}],
    )

    with pytest.raises(TimeoutError, match=r'visible_overlays') as excinfo:
        asyncio.run(gemini_core._gemini_get_visible_drive_picker_frame(page, timeout_ms=20))

    assert '关联 Google Workspace' in str(excinfo.value)
