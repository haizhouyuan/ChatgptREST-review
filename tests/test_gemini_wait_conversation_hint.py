import asyncio

from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


class _DummyMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append((tool_name, dict(tool_args)))
        if tool_name != "gemini_web_wait":
            raise AssertionError(f"unexpected tool: {tool_name}")

        hint = str(tool_args.get("conversation_hint") or "")
        assert tool_args.get("conversation_url") == "https://gemini.google.com/app"
        assert hint
        assert "hello" in hint
        assert "outline-part1.md" in hint
        assert len(hint) <= 2000

        return {"ok": True, "status": "completed", "answer": "ok", "run_id": "dummy"}


class _SendRecoveringMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append((tool_name, dict(tool_args)))
        if tool_name == "gemini_web_ask_pro":
            return {
                "status": "in_progress",
                "answer": "",
                "conversation_url": "",
                "error_type": "TimeoutError",
                "error": "Timed out waiting for Gemini response.",
            }
        if tool_name == "gemini_web_idempotency_get":
            assert tool_args.get("tool_name") == "gemini_web_ask_pro"
            return {
                "ok": True,
                "status": "completed",
                "record": {
                    "conversation_url": "https://gemini.google.com/app/recovered-thread-1234",
                },
            }
        if tool_name == "gemini_web_wait":
            assert tool_args.get("conversation_url") == "https://gemini.google.com/app/recovered-thread-1234"
            return {
                "ok": True,
                "status": "completed",
                "answer": "recovered",
                "conversation_url": "https://gemini.google.com/app/recovered-thread-1234",
            }
        raise AssertionError(f"unexpected tool: {tool_name}")


class _WaitRecoveringMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append((tool_name, dict(tool_args)))
        if tool_name == "gemini_web_idempotency_get":
            assert tool_args.get("tool_name") == "gemini_web_ask_pro"
            return {
                "ok": True,
                "status": "completed",
                "record": {
                    "conversation_url": "https://gemini.google.com/app",
                },
            }
        if tool_name == "gemini_web_wait":
            assert tool_args.get("conversation_url") == "https://gemini.google.com/app"
            hint = str(tool_args.get("conversation_hint") or "")
            assert "hello" in hint
            assert "outline-part1.md" in hint
            return {
                "ok": True,
                "status": "completed",
                "answer": "wait recovered",
                "conversation_url": "https://gemini.google.com/app/recovered-thread-5678",
            }
        raise AssertionError(f"unexpected tool: {tool_name}")


def test_gemini_wait_passes_conversation_hint_for_base_app_url() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _DummyMcpClient()  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-hint",
            kind="gemini_web.ask",
            input={
                "question": "hello",
                "conversation_url": "https://gemini.google.com/app",
                "file_paths": ["/tmp/outline-part1.md"],
            },
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "completed"


def test_gemini_wait_phase_recovers_base_app_url_from_idempotency() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    client = _WaitRecoveringMcpClient()
    ex._client = client  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-idempotency-recover",
            kind="gemini_web.ask",
            input={
                "question": "hello",
                "file_paths": ["/tmp/outline-part1.md"],
            },
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )

    assert res.status == "completed"
    assert [name for name, _ in client.calls] == ["gemini_web_idempotency_get", "gemini_web_wait"]
    assert isinstance(res.meta, dict)
    assert res.meta.get("conversation_url") == "https://gemini.google.com/app/recovered-thread-5678"


def test_gemini_full_send_without_conversation_url_does_not_enter_wait() -> None:
    calls: list[tuple[str, dict]] = []

    class _DummyMcpClient:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append((tool_name, dict(tool_args)))
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "in_progress",
                    "answer": "",
                    "error_type": "TimeoutError",
                    "error": "Timed out waiting for Gemini response.",
                }
            if tool_name == "gemini_web_idempotency_get":
                return {"ok": False, "status": "not_found"}
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _DummyMcpClient()  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-no-thread-yet",
            kind="gemini_web.ask",
            input={"question": "请继续分析这个主题。"},
            params={"preset": "pro", "timeout_seconds": 60, "max_wait_seconds": 60},
        )
    )

    assert res.status == "in_progress"
    assert [name for name, _ in calls] == ["gemini_web_ask_pro", "gemini_web_idempotency_get"]
    assert isinstance(res.meta, dict)
    assert res.meta.get("error_type") == "WaitingForConversationUrl"


def test_gemini_full_send_recovers_thread_url_from_idempotency_and_enters_wait() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    client = _SendRecoveringMcpClient()
    ex._client = client  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-send-idempotency-recover",
            kind="gemini_web.ask",
            input={"question": "请继续分析这个主题。"},
            params={"preset": "pro", "timeout_seconds": 60, "max_wait_seconds": 60},
        )
    )

    assert res.status == "completed"
    assert [name for name, _ in client.calls] == [
        "gemini_web_ask_pro",
        "gemini_web_idempotency_get",
        "gemini_web_wait",
    ]
    assert isinstance(res.meta, dict)
    assert res.meta.get("conversation_url") == "https://gemini.google.com/app/recovered-thread-1234"
    assert res.meta.get("conversation_url_recovered_from_idempotency") is True
