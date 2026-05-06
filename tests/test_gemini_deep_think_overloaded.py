from __future__ import annotations

import asyncio

from chatgptrest.executors import gemini_web_mcp as gemini
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def test_looks_like_gemini_deep_think_overloaded() -> None:
    msg = (
        "A lot of people are using Deep Think right now and I need a moment to sort through all those deep thoughts! "
        "Please try again in a bit. I can still help without Deep Think. Just unselect it from your tools."
    )
    assert gemini._looks_like_gemini_deep_think_overloaded(msg)
    assert gemini._looks_like_gemini_deep_think_overloaded("深度思考现在太拥挤了，请稍后再试")
    assert not gemini._looks_like_gemini_deep_think_overloaded("OK")


def test_looks_like_gemini_deep_think_unavailable() -> None:
    assert gemini._looks_like_gemini_deep_think_unavailable(
        error_type="GeminiDeepThinkToolNotFound",
        error_text="Gemini tool not found: (Deep\\s*Think|深度思考|深入思考)",
    )
    assert gemini._looks_like_gemini_deep_think_unavailable(
        error_type="RuntimeError",
        error_text="Gemini tool switch did not apply (wanted=True, current=False): (Deep\\s*Think)",
    )
    assert not gemini._looks_like_gemini_deep_think_unavailable(
        error_type="InfraError",
        error_text="Target crashed",
    )


def test_deep_think_overloaded_falls_back_to_pro() -> None:
    overloaded = (
        "A lot of people are using Deep Think right now. "
        "Please try again in a bit. I can still help without Deep Think."
    )
    calls: list[dict] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if tool_name == "gemini_web_ask_pro_deep_think":
                return {
                    "status": "completed",
                    "answer": overloaded,
                    "conversation_url": "https://gemini.google.com/app/abc123",
                    "deep_think_retry": {"max_attempts": 3, "attempts": [{"attempt": 1}], "final_overloaded": True},
                }
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "completed",
                    "answer": "fallback-pro-ok",
                    "conversation_url": "https://gemini.google.com/app/abc123",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-deep-think-fallback",
            kind="gemini_web.ask",
            input={"question": "test deep think fallback"},
            params={"preset": "deep_think", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert res.answer == "fallback-pro-ok"
    assert len(calls) == 2
    assert calls[0]["tool_name"] == "gemini_web_ask_pro_deep_think"
    assert calls[1]["tool_name"] == "gemini_web_ask_pro"
    assert isinstance(res.meta, dict)
    assert isinstance((res.meta or {}).get("fallback"), dict)


def test_deep_think_tool_not_found_falls_back_to_pro() -> None:
    calls: list[dict] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if tool_name == "gemini_web_ask_pro_deep_think":
                return {
                    "status": "error",
                    "answer": "",
                    "error_type": "GeminiDeepThinkToolNotFound",
                    "error": "Gemini tool not found: (Deep\\s*Think|深度思考|深入思考)",
                    "conversation_url": "https://gemini.google.com/app",
                }
            if tool_name == "gemini_web_ask_pro":
                assert "conversation_url" not in tool_args
                return {
                    "status": "completed",
                    "answer": "fallback-pro-after-tool-not-found",
                    "conversation_url": "https://gemini.google.com/app/xyz789",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-deep-think-tool-not-found-fallback",
            kind="gemini_web.ask",
            input={"question": "test deep think unavailable fallback"},
            params={"preset": "deep_think", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert res.answer == "fallback-pro-after-tool-not-found"
    assert len(calls) == 2
    assert calls[0]["tool_name"] == "gemini_web_ask_pro_deep_think"
    assert calls[1]["tool_name"] == "gemini_web_ask_pro"
    assert isinstance(res.meta, dict)
    assert isinstance((res.meta or {}).get("fallback"), dict)
    assert (res.meta or {}).get("fallback", {}).get("reason") == "deep_think_unavailable"


def test_deep_think_overloaded_without_successful_pro_fallback_keeps_original_answer() -> None:
    overloaded = "Deep Think is busy right now. Please try again in a bit."
    calls: list[dict] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if tool_name == "gemini_web_ask_pro_deep_think":
                return {
                    "status": "completed",
                    "answer": overloaded,
                    "conversation_url": "https://gemini.google.com/app/def456",
                    "deep_think_retry": {"max_attempts": 3, "attempts": [{"attempt": 1}, {"attempt": 2}], "final_overloaded": True},
                }
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "error",
                    "answer": "",
                    "error_type": "InfraError",
                    "error": "temporary failure",
                    "conversation_url": "https://gemini.google.com/app/def456",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-deep-think-fallback-fail",
            kind="gemini_web.ask",
            input={"question": "test deep think fallback failure"},
            params={"preset": "deep_think", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "cooldown"
    assert not res.answer  # overloaded garbage answer should be cleared
    assert len(calls) == 2
    assert calls[0]["tool_name"] == "gemini_web_ask_pro_deep_think"
    assert calls[1]["tool_name"] == "gemini_web_ask_pro"
