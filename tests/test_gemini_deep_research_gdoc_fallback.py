from __future__ import annotations

import asyncio

import pytest

import chatgptrest.executors.gemini_web_mcp as gem_mod
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def _patch_now_to_force_wait_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    # _wait_loop will call _now() several times; force exactly one wait poll, then hit deadline.
    timeline = [1000.0, 1000.0, 1000.0, 1045.0, 1060.0, 1080.0]

    def _fake_now() -> float:
        if timeline:
            return float(timeline.pop(0))
        return 1100.0

    monkeypatch.setattr(gem_mod, "_now", _fake_now)


def test_deep_research_wait_deadline_uses_gdoc_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(gem_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setenv("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_ENABLED", "1")
    _patch_now_to_force_wait_deadline(monkeypatch)

    calls: list[tuple[str, dict]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append((tool_name, dict(tool_args)))
            if tool_name == "gemini_web_wait":
                return {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/abc123xyz",
                }
            if tool_name == "gemini_web_deep_research_export_gdoc":
                return {
                    "ok": True,
                    "status": "completed",
                    "answer": ("# 调研报告\n\n" + ("段落内容。\n" * 400)).strip(),
                    "conversation_url": "https://gemini.google.com/app/abc123xyz",
                    "gdoc_url": "https://docs.google.com/document/d/abcdefghijklmnopqrstuvwx/edit",
                    "gdoc_id": "abcdefghijklmnopqrstuvwx",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-dr-gdoc-fallback-ok",
            kind="gemini_web.ask",
            input={"question": "请做深度调研", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={
                "preset": "pro",
                "phase": "wait",
                "deep_research": True,
                "wait_timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 300,
            },
        )
    )
    assert res.status == "completed"
    assert "# 调研报告" in res.answer
    assert len(calls) == 2
    assert calls[0][0] == "gemini_web_wait"
    assert calls[1][0] == "gemini_web_deep_research_export_gdoc"
    meta = dict(res.meta or {})
    assert isinstance(meta.get("fallback"), dict)
    assert meta["fallback"].get("kind") == "gemini_dr_export_gdoc"
    assert meta["fallback"].get("applied") is True
    assert isinstance(meta.get("gdoc_export"), dict)


def test_deep_research_wait_deadline_gdoc_fallback_ack_keeps_in_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(gem_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setenv("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_ENABLED", "1")
    _patch_now_to_force_wait_deadline(monkeypatch)

    calls: list[tuple[str, dict]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append((tool_name, dict(tool_args)))
            if tool_name == "gemini_web_wait":
                return {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/abc123xyz",
                }
            if tool_name == "gemini_web_deep_research_export_gdoc":
                return {
                    "ok": True,
                    "status": "completed",
                    "answer": "我将开始研究，完成后请查收。",
                    "conversation_url": "https://gemini.google.com/app/abc123xyz",
                    "gdoc_url": "https://docs.google.com/document/d/abcdefghijklmnopqrstuvwx/edit",
                    "gdoc_id": "abcdefghijklmnopqrstuvwx",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-dr-gdoc-fallback-ack",
            kind="gemini_web.ask",
            input={"question": "请做深度调研", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={
                "preset": "pro",
                "phase": "wait",
                "deep_research": True,
                "wait_timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 300,
            },
        )
    )
    assert res.status == "in_progress"
    assert len(calls) == 2
    assert calls[1][0] == "gemini_web_deep_research_export_gdoc"
    meta = dict(res.meta or {})
    gdoc_export = dict(meta.get("gdoc_export") or {})
    assert gdoc_export.get("classified_status") == "in_progress"


def test_deep_research_wait_deadline_respects_gdoc_fallback_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(gem_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setenv("CHATGPTREST_GEMINI_DR_GDOC_FALLBACK_ENABLED", "0")
    _patch_now_to_force_wait_deadline(monkeypatch)

    calls: list[tuple[str, dict]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append((tool_name, dict(tool_args)))
            if tool_name == "gemini_web_wait":
                return {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/abc123xyz",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-dr-gdoc-fallback-off",
            kind="gemini_web.ask",
            input={"question": "请做深度调研", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={
                "preset": "pro",
                "phase": "wait",
                "deep_research": True,
                "wait_timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 300,
            },
        )
    )
    assert res.status == "in_progress"
    assert len(calls) == 1
    assert calls[0][0] == "gemini_web_wait"

