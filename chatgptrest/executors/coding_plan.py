from __future__ import annotations

from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.kernel.llm_connector import LLMConfig, LLMConnector


class CodingPlanExecutor(BaseExecutor):
    """Executor for API-backed coding/plan asks via LLMConnector.

    This gives automation lanes a stable, non-browser path that can use the
    Coding Plan API chain (MiniMax-M2.5, Qwen, Kimi, GLM) and its built-in
    fallback logic.
    """

    def __init__(self) -> None:
        self._connector = LLMConnector(config=LLMConfig())

    async def run(
        self,
        *,
        job_id: str,
        kind: str,
        input: dict[str, object],  # noqa: A002
        params: dict[str, object],
    ) -> ExecutorResult:
        del job_id, kind
        question = str(input.get("question") or "").strip()
        if not question:
            return ExecutorResult(status="error", answer="", meta={"error": "empty question"})

        system_prompt = str(params.get("system_prompt") or input.get("system_prompt") or "").strip()
        provider = str(params.get("provider") or "coding_plan").strip()
        preset = str(params.get("preset") or "planning").strip()
        timeout = params.get("timeout_seconds")
        timeout_seconds = float(timeout) if timeout is not None else None

        response = self._connector.ask(
            question,
            system_msg=system_prompt,
            provider=provider,
            preset=preset,
            timeout=timeout_seconds,
        )

        if response.status != "success":
            return ExecutorResult(
                status="error" if response.status in {"error", "timeout", "cooldown"} else response.status,
                answer=response.text,
                answer_format="markdown",
                meta={
                    "provider": response.provider or provider,
                    "preset": response.preset or preset,
                    "status": response.status,
                    "error": response.error,
                    "latency_ms": response.latency_ms,
                },
            )

        return ExecutorResult(
            status="completed",
            answer=response.text,
            answer_format="markdown",
            meta={
                "provider": response.provider or provider,
                "preset": response.preset or preset,
                "latency_ms": response.latency_ms,
                "tokens_estimated": response.tokens_estimated,
            },
        )
