from __future__ import annotations

import asyncio

import pytest

from chatgpt_web_mcp import _tools_impl as mcp_server
from chatgpt_web_mcp.playwright import cdp as cdp_mod

def test_cdp_ws_connect_falls_back_to_resolved_ws(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    resolved_bases: list[str] = []

    async def _fake_resolve(cdp_url: str, *, ctx):  # noqa: ARG001
        resolved_bases.append(str(cdp_url))
        return "ws://127.0.0.1:9222/devtools/browser/new"

    monkeypatch.setattr(cdp_mod, "_cdp_ws_url_from_http_endpoint", _fake_resolve)

    class _DummyChromium:
        async def connect_over_cdp(self, url: str, timeout=None):  # noqa: ANN001,ARG002
            calls.append(url)
            if url.endswith("/old"):
                raise RuntimeError("stale ws")
            return {"url": url}

    class _DummyPlaywright:
        chromium = _DummyChromium()

    res = asyncio.run(
        mcp_server._connect_over_cdp_resilient(
            _DummyPlaywright(),
            "ws://127.0.0.1:9222/devtools/browser/old",
            ctx=None,
        )
    )
    assert res == {"url": "ws://127.0.0.1:9222/devtools/browser/new"}
    assert calls == [
        "ws://127.0.0.1:9222/devtools/browser/old",
        "ws://127.0.0.1:9222/devtools/browser/new",
    ]
    assert resolved_bases == ["http://127.0.0.1:9222"]


def test_cdp_wss_fallback_uses_https_base(monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_bases: list[str] = []

    async def _fake_resolve(cdp_url: str, *, ctx):  # noqa: ARG001
        resolved_bases.append(str(cdp_url))
        return "wss://example.com/devtools/browser/new"

    monkeypatch.setattr(cdp_mod, "_cdp_ws_url_from_http_endpoint", _fake_resolve)

    class _DummyChromium:
        async def connect_over_cdp(self, url: str, timeout=None):  # noqa: ANN001,ARG002
            if url.endswith("/old"):
                raise RuntimeError("stale wss")
            return {"url": url}

    class _DummyPlaywright:
        chromium = _DummyChromium()

    res = asyncio.run(
        mcp_server._connect_over_cdp_resilient(
            _DummyPlaywright(),
            "wss://example.com:443/devtools/browser/old",
            ctx=None,
        )
    )
    assert res == {"url": "wss://example.com/devtools/browser/new"}
    assert resolved_bases == ["https://example.com:443"]


def test_cdp_ws_direct_connect_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    resolved = False

    async def _fake_resolve(cdp_url: str, *, ctx):  # noqa: ARG001
        nonlocal resolved
        resolved = True
        return "ws://127.0.0.1:9222/devtools/browser/new"

    monkeypatch.setattr(cdp_mod, "_cdp_ws_url_from_http_endpoint", _fake_resolve)

    class _DummyChromium:
        async def connect_over_cdp(self, url: str, timeout=None):  # noqa: ANN001,ARG002
            return {"url": url}

    class _DummyPlaywright:
        chromium = _DummyChromium()

    res = asyncio.run(
        mcp_server._connect_over_cdp_resilient(
            _DummyPlaywright(),
            "ws://127.0.0.1:9222/devtools/browser/ok",
            ctx=None,
        )
    )
    assert res == {"url": "ws://127.0.0.1:9222/devtools/browser/ok"}
    assert resolved is False



def test_cdp_ws_connect_none_browser_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_resolve(cdp_url: str, *, ctx):  # noqa: ARG001
        return None

    monkeypatch.setattr(cdp_mod, "_cdp_ws_url_from_http_endpoint", _fake_resolve)

    class _DummyChromium:
        async def connect_over_cdp(self, url: str, timeout=None):  # noqa: ANN001,ARG002
            return None

    class _DummyPlaywright:
        chromium = _DummyChromium()

    with pytest.raises(RuntimeError):
        asyncio.run(
            mcp_server._connect_over_cdp_resilient(
                _DummyPlaywright(),
                "ws://127.0.0.1:9222/devtools/browser/ok",
                ctx=None,
            )
        )


def test_cdp_http_connect_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def _fake_resolve(cdp_url: str, *, ctx):  # noqa: ARG001
        return "ws://127.0.0.1:9222/devtools/browser/new"

    monkeypatch.setattr(cdp_mod, "_cdp_ws_url_from_http_endpoint", _fake_resolve)
    monkeypatch.setattr(cdp_mod, "_cdp_connect_retries", lambda: 2)
    monkeypatch.setattr(cdp_mod, "_cdp_connect_retry_delay_seconds", lambda: 0.0)

    class _DummyChromium:
        async def connect_over_cdp(self, url: str, timeout=None):  # noqa: ANN001,ARG002
            calls.append(url)
            if len(calls) == 1:
                raise RuntimeError("connect ECONNREFUSED 127.0.0.1:9222")
            return {"url": url}

    class _DummyPlaywright:
        chromium = _DummyChromium()

    res = asyncio.run(
        mcp_server._connect_over_cdp_resilient(
            _DummyPlaywright(),
            "http://127.0.0.1:9222",
            ctx=None,
        )
    )
    assert res == {"url": "ws://127.0.0.1:9222/devtools/browser/new"}
    assert calls == [
        "ws://127.0.0.1:9222/devtools/browser/new",
        "ws://127.0.0.1:9222/devtools/browser/new",
    ]
