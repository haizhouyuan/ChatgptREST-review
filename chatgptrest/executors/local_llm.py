"""Local LLM executor – calls Ollama/vLLM OpenAI-compatible API directly.

Unlike other executors that use browser automation (MCP), this executor
makes direct HTTP calls to a local LLM endpoint. No driver/MCP required.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.executors.config import LocalLLMExecutorConfig


@dataclass(frozen=True)
class LocalLLMJobParams:
    preset: str = "default"
    max_tokens: int = 4096
    temperature: float | None = None
    system_prompt: str = ""


_CFG = LocalLLMExecutorConfig()

_PRESET_TEMPS: dict[str, float] = {
    "default": 0.3,
    "code": 0.1,
    "creative": 0.8,
}


def _build_messages(*, question: str, system_prompt: str = "") -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})
    return messages


def _call_openai_compat(
    *,
    endpoint_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    url = endpoint_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urlopen(req, timeout=timeout_seconds)
    return json.loads(resp.read().decode("utf-8"))


class LocalLLMExecutor(BaseExecutor):
    """Executor that calls a local LLM via its OpenAI-compatible API."""

    async def run(
        self,
        *,
        job_id: str,
        kind: str,
        input: dict[str, Any],  # noqa: A002
        params: dict[str, Any],
    ) -> ExecutorResult:
        question = str(input.get("question") or "").strip()
        if not question:
            return ExecutorResult(status="error", answer="", meta={"error": "empty question"})

        preset = str(params.get("preset") or "default").strip()
        temperature = params.get("temperature")
        if temperature is None:
            temperature = _PRESET_TEMPS.get(preset, _CFG.default_temperature)
        temperature = float(temperature)

        max_tokens = int(params.get("max_tokens") or _CFG.default_max_tokens)
        system_prompt = str(params.get("system_prompt") or input.get("system_prompt") or "").strip()
        messages = _build_messages(question=question, system_prompt=system_prompt)

        started = time.monotonic()
        try:
            result = _call_openai_compat(
                endpoint_url=_CFG.endpoint_url,
                model=_CFG.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_seconds=_CFG.request_timeout_seconds,
            )
        except (URLError, HTTPError) as exc:
            return ExecutorResult(
                status="error",
                answer="",
                meta={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "endpoint_url": _CFG.endpoint_url,
                    "model": _CFG.model_name,
                },
            )

        elapsed_ms = int((time.monotonic() - started) * 1000)
        choices = result.get("choices", [])
        if not choices:
            return ExecutorResult(
                status="error",
                answer="",
                meta={"error": "no choices in response", "raw": json.dumps(result)[:500]},
            )

        message = choices[0].get("message", {})
        content = str(message.get("content") or "").strip()
        reasoning = str(message.get("reasoning") or "").strip()
        if not content and reasoning:
            content = f"[Model reasoning only – increase max_tokens]\n\n{reasoning}"

        usage = result.get("usage", {})
        meta: dict[str, Any] = {
            "model": result.get("model", _CFG.model_name),
            "endpoint_url": _CFG.endpoint_url,
            "preset": preset,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "elapsed_ms": elapsed_ms,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "finish_reason": choices[0].get("finish_reason", ""),
        }
        if reasoning:
            meta["has_reasoning"] = True
            meta["reasoning_chars"] = len(reasoning)

        return ExecutorResult(
            status="completed",
            answer=content,
            answer_format="markdown",
            meta=meta,
        )
