from __future__ import annotations

import asyncio

from chatgptrest.executors.base import BaseExecutor, ExecutorResult


class DummyExecutor(BaseExecutor):
    async def run(self, *, job_id: str, kind: str, input: dict[str, object], params: dict[str, object]) -> ExecutorResult:  # noqa: A002
        if kind == "dummy.error_meta":
            return ExecutorResult(status="error", answer="", meta={"error_type": "RuntimeError", "error": "meta error"})

        if kind not in {"dummy.echo", "dummy.conversation_echo"}:
            return ExecutorResult(status="error", answer=f"Unknown kind: {kind}")

        text = str(input.get("text") or "")
        repeat = int(params.get("repeat") or 1)
        delay_ms = int(params.get("delay_ms") or 10)
        await asyncio.sleep(max(0, delay_ms) / 1000.0)
        answer = "\n".join([text] * max(1, repeat))

        meta = None
        if kind == "dummy.conversation_echo":
            url = str(input.get("conversation_url") or "").strip()
            meta = {"conversation_url": url} if url else None

        return ExecutorResult(status="completed", answer=answer, answer_format="text", meta=meta)
