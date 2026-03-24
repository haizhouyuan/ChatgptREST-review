from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.driver.api import ToolCaller
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller
from chatgptrest.executors.base import BaseExecutor, ExecutorResult


_QWEN_THREAD_URL_RE = re.compile(r"^https?://(?:[^/]*\.)?qianwen\.com/chat/[0-9a-f]{32}(?:[/?#].*)?$", re.I)


@dataclass(frozen=True)
class QwenWebJobParams:
    preset: str
    send_timeout_seconds: int
    wait_timeout_seconds: int
    min_chars: int
    max_wait_seconds: int
    answer_format: str
    phase: str


def _now() -> float:
    return time.time()


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_phase(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"send", "wait"}:
        return raw
    if raw in {"all", "full", "both"}:
        return "full"
    return "full"


def _normalize_preset(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"default", "defaults", "auto"}:
        return "auto"
    if raw in {"deep_think", "deep-thinking", "thinking", "deep_thinking"}:
        return "deep_thinking"
    if raw in {"deep_research", "research", "deep-research"}:
        return "deep_research"
    return raw or "auto"


class QwenWebMcpExecutor(BaseExecutor):
    def __init__(
        self,
        *,
        mcp_url: str | None = None,
        tool_caller: ToolCaller | None = None,
        client_name: str = "chatgptrest",
        client_version: str = "0.1.0",
    ) -> None:
        if tool_caller is None:
            if not mcp_url:
                raise ValueError("mcp_url is required when tool_caller is not provided")
            tool_caller = McpHttpToolCaller(url=mcp_url, client_name=client_name, client_version=client_version)
        self._client = tool_caller

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        if kind != "qwen_web.ask":
            return ExecutorResult(status="error", answer=f"Unknown kind: {kind}", meta={"error_type": "ValueError"})
        return await self._run_ask(job_id=job_id, input=input, params=params)

    async def _run_ask(self, *, job_id: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:
        question = str(input.get("question") or "").strip()
        if not question:
            return ExecutorResult(status="error", answer="Missing input.question", meta={"error_type": "ValueError"})

        phase = _normalize_phase(params.get("phase") or params.get("execution_phase"))
        preset = _normalize_preset(params.get("preset") or "auto")
        deep_research_requested = bool(params.get("deep_research"))
        if preset == "auto":
            preset = "deep_research" if deep_research_requested else "deep_thinking"
        deep_research_effective = deep_research_requested or preset == "deep_research"
        conversation_url = str(input.get("conversation_url") or "").strip() or None

        base_timeout = _coerce_int(params.get("timeout_seconds"), 600)
        send_timeout_raw = params.get("send_timeout_seconds")
        send_timeout_seconds = max(30, _coerce_int(send_timeout_raw, base_timeout))

        raw_cap = (params.get("send_timeout_cap_seconds") or "").strip() if isinstance(params.get("send_timeout_cap_seconds"), str) else ""
        try:
            cap = int(raw_cap) if raw_cap else 180
        except Exception:
            cap = 180
        if cap > 0:
            send_timeout_seconds = min(send_timeout_seconds, max(30, cap))

        wait_timeout_seconds = max(30, _coerce_int(params.get("wait_timeout_seconds"), base_timeout))
        max_wait_seconds = max(30, _coerce_int(params.get("max_wait_seconds"), 1800))
        min_chars = max(0, _coerce_int(params.get("min_chars"), 200))
        answer_format = str(params.get("answer_format") or "markdown").strip().lower()
        if answer_format not in {"markdown", "text"}:
            answer_format = "markdown"

        job_params = QwenWebJobParams(
            preset=preset,
            send_timeout_seconds=send_timeout_seconds,
            wait_timeout_seconds=wait_timeout_seconds,
            min_chars=min_chars,
            max_wait_seconds=max_wait_seconds,
            answer_format=answer_format,
            phase=phase,
        )

        def _on_qwen_wait_result(wait_res: dict[str, Any], cur_url: str) -> tuple[dict[str, Any], str]:
            new_url = str(wait_res.get("conversation_url") or "").strip()
            if new_url and (not _QWEN_THREAD_URL_RE.match(cur_url) or _QWEN_THREAD_URL_RE.match(new_url)):
                cur_url = new_url
            wait_res["conversation_url"] = cur_url
            return wait_res, cur_url

        async def _wait_loop(*, url: str | None) -> tuple[dict[str, Any], str]:
            return await self._wait_loop_core(
                client=self._client,
                tool_name="qwen_web_wait",
                conversation_url=url or "",
                wait_timeout_seconds=job_params.wait_timeout_seconds,
                max_wait_seconds=job_params.max_wait_seconds,
                min_chars=job_params.min_chars,
                extra_tool_args={"deep_research": bool(deep_research_effective)},
                on_wait_result=_on_qwen_wait_result,
            )

        primary_key = f"chatgptrest:{job_id}:qwen:{job_params.preset}"

        if phase == "wait":
            if not conversation_url:
                return ExecutorResult(
                    status="error",
                    answer="qwen_web.ask params.phase=wait requires input.conversation_url",
                    meta={"error_type": "ValueError"},
                )
            result, conversation_url = await _wait_loop(url=conversation_url)
        else:
            tool_args: dict[str, Any] = {
                "question": question,
                "idempotency_key": primary_key,
                "timeout_seconds": int(job_params.send_timeout_seconds),
                "preset": job_params.preset,
            }
            if conversation_url:
                tool_args["conversation_url"] = conversation_url

            result = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="qwen_web_ask",
                tool_args=tool_args,
                timeout_sec=float(job_params.send_timeout_seconds) + 30.0,
            )
            if not isinstance(result, dict):
                return ExecutorResult(status="error", answer="driver returned non-dict result", meta={"error_type": "TypeError"})

            conversation_url = str(result.get("conversation_url") or conversation_url or "").strip() or None
            status = str(result.get("status") or "").strip().lower()
            if phase == "full" and status == "in_progress":
                result, conversation_url = await _wait_loop(url=conversation_url)

        status = str(result.get("status") or "error").strip().lower()
        if status not in {"completed", "in_progress", "blocked", "cooldown", "error", "canceled", "needs_followup"}:
            status = "error"
        answer = str(result.get("answer") or "")
        meta = dict(result)
        meta["answer_format"] = job_params.answer_format
        meta["conversation_url"] = str(conversation_url or "")
        meta["preset"] = job_params.preset
        meta["deep_research_requested"] = bool(deep_research_requested)
        meta["deep_research_effective"] = bool(deep_research_effective)
        return ExecutorResult(status=status, answer=answer, answer_format=job_params.answer_format, meta=meta)
