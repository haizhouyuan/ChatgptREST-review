from __future__ import annotations

import asyncio

from chatgptrest.executors.qwen_web_mcp import QwenWebMcpExecutor


def test_qwen_executor_is_retired() -> None:
    ex = QwenWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    res = asyncio.run(
        ex.run(
            job_id="job-qwen-retired",
            kind="qwen_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "error"
    assert "retired" in (res.answer or "")
    assert isinstance(res.meta, dict)
    assert (res.meta or {}).get("error_type") == "ProviderRemoved"
