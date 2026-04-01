import asyncio

from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


class _DummyMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._n = 0

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append((tool_name, dict(tool_args)))
        self._n += 1
        if tool_name != "gemini_web_wait":
            raise AssertionError(f"unexpected tool: {tool_name}")

        # First poll upgrades /app → /app/<id>, second poll should reuse the upgraded URL.
        upgraded = "https://gemini.google.com/app/d6d83d5b6fe00ea7"
        if self._n == 1:
            return {"ok": True, "status": "in_progress", "answer": "", "conversation_url": upgraded, "run_id": "r1"}

        assert tool_args.get("conversation_url") == upgraded
        return {"ok": True, "status": "completed", "answer": "ok", "conversation_url": upgraded, "run_id": "r2"}


def test_gemini_wait_loop_upgrades_conversation_url_from_wait_result() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _DummyMcpClient()  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-url-upgrade",
            kind="gemini_web.ask",
            input={
                "question": "hello",
                "conversation_url": "https://gemini.google.com/app",
            },
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "completed"
    assert res.meta and res.meta.get("conversation_url") == "https://gemini.google.com/app/d6d83d5b6fe00ea7"

