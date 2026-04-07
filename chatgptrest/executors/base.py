from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ExecutorResult:
    status: str
    answer: str
    answer_format: str = "text"
    meta: dict[str, Any] | None = None


class BaseExecutor:
    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        raise NotImplementedError

    async def _wait_loop_core(
        self,
        *,
        client: Any,
        tool_name: str,
        conversation_url: str,
        wait_timeout_seconds: int,
        max_wait_seconds: int,
        min_chars: int = 0,
        extra_tool_args: dict[str, Any] | None = None,
        on_wait_result: Callable[[dict[str, Any], str], tuple[dict[str, Any], str]] | None = None,
        on_transient_error: Callable[[Exception, int], tuple[bool, float]] | None = None,
        sleep_range: tuple[float, float] = (2.0, 4.0),
        now_fn: Callable[[], float] | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Shared wait loop core for all executors.

        Encapsulates the common pattern:
          1. Check URL availability
          2. Deadline loop: call_tool → check status → sleep → loop

        Args:
            client: ToolCaller instance for call_tool calls.
            tool_name: Driver wait tool name (e.g. "chatgpt_web_wait").
            conversation_url: URL to wait on.
            wait_timeout_seconds: Per-iteration timeout for the wait tool.
            max_wait_seconds: Overall deadline for the wait loop.
            min_chars: Minimum answer chars to request from driver.
            extra_tool_args: Additional args merged into call_tool args.
            on_wait_result: Optional callback(wait_res, cur_url) → (wait_res, cur_url).
                Called after each successful tool call for URL updates or augmentation.
            on_transient_error: Optional callback(exc, failure_count) → (should_continue, sleep_seconds).
                Return (True, N) to retry after N seconds, (False, _) to re-raise.
            sleep_range: (min, max) sleep seconds between iterations.
            now_fn: Optional clock source for deadline accounting. Defaults to time.monotonic.

        Returns:
            (result_dict, final_url)
        """
        cur = str(conversation_url or "").strip()
        if not cur:
            wait_seconds = 30.0
            return (
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "",
                    "error_type": "WaitingForConversationUrl",
                    "error": "conversation_url not available yet; retry later",
                    "retry_after_seconds": wait_seconds,
                    # `not_before` is persisted in the job store and compared against time.time().
                    # Never use a monotonic clock here, otherwise wait jobs can hot-loop forever.
                    "not_before": time.time() + wait_seconds,
                },
                "",
            )

        result: dict[str, Any] = {"status": "in_progress", "conversation_url": cur}
        clock = now_fn or time.monotonic
        deadline = clock() + float(max_wait_seconds)
        transient_failures = 0

        while clock() < deadline:
            remaining = max(30, min(wait_timeout_seconds, int(deadline - clock())))
            tool_args: dict[str, Any] = {
                "conversation_url": cur,
                "timeout_seconds": int(remaining),
                "min_chars": int(min_chars),
            }
            if extra_tool_args:
                tool_args.update(extra_tool_args)

            try:
                wait_res = await asyncio.to_thread(
                    client.call_tool,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    timeout_sec=float(remaining) + 120.0,
                )
            except Exception as exc:
                if on_transient_error:
                    should_continue, sleep_secs = on_transient_error(exc, transient_failures)
                    if should_continue:
                        transient_failures += 1
                        await asyncio.sleep(sleep_secs)
                        continue
                raise

            transient_failures = 0
            if isinstance(wait_res, dict):
                if on_wait_result:
                    wait_res, cur = on_wait_result(wait_res, cur)
                else:
                    new_url = str(wait_res.get("conversation_url") or "").strip()
                    if new_url:
                        cur = new_url
                    wait_res["conversation_url"] = cur
                result = wait_res

            status = str(result.get("status") or "").strip().lower()
            if status and status != "in_progress":
                break

            lo, hi = sleep_range
            await asyncio.sleep(lo + random.random() * (hi - lo))

        return result, cur
