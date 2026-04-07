import os
from typing import AsyncIterator, Any, Optional

from .base import SessionBackend, BackendResult


class SDKBackend(SessionBackend):
    """Official Claude Code SDK backend with MiniMax Anthropic-compatible routing."""

    backend_name = "sdk_official"

    def __init__(
        self,
        minimax_api_key: Optional[str] = None,
        minimax_base_url: str = "https://api.minimaxi.com/anthropic",
    ):
        self.minimax_api_key = minimax_api_key or os.environ.get("MINIMAX_API_KEY")
        self.minimax_base_url = minimax_base_url

    def _build_options(
        self,
        sdk_options_cls,
        options: dict,
        *,
        resume: Optional[str] = None,
    ):
        files = options.get("file_paths", [])
        env = {
            "ANTHROPIC_BASE_URL": self.minimax_base_url,
            "ANTHROPIC_API_KEY": self.minimax_api_key or "",
        }
        if extra_env := options.get("env"):
            env.update(extra_env)

        kwargs = {
            "allowed_tools": options.get("allowed_tools", ["Read", "Edit", "Bash", "Glob", "Grep"]),
            "permission_mode": options.get("permission_mode", "bypassPermissions"),
            "model": options.get("model"),
            "max_turns": options.get("max_turns"),
            "cwd": options.get("cwd") or options.get("context", {}).get("cwd"),
            "add_dirs": options.get("add_dirs", []),
            "append_system_prompt": options.get("system_prompt") or None,
            "env": env,
            "resume": resume,
            "continue_conversation": bool(resume),
        }
        if files:
            kwargs["add_dirs"] = [*kwargs["add_dirs"], *files]
        return sdk_options_cls(**kwargs)

    @staticmethod
    def _usage_totals(usage: Optional[dict]) -> tuple[int, int, int]:
        usage = usage or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        return input_tokens, output_tokens, input_tokens + output_tokens

    async def _stream_run(
        self,
        prompt: str,
        options: dict,
        *,
        resume: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        from claude_code_sdk import (
            query,
            ClaudeCodeOptions,
            ResultMessage,
        )

        sdk_options = self._build_options(ClaudeCodeOptions, options, resume=resume)

        async for message in query(prompt=prompt, options=sdk_options):
            yield {
                "type": "message",
                "backend": self.backend_name,
                "message": message,
            }

            if isinstance(message, ResultMessage):
                input_tokens, output_tokens, total_tokens = self._usage_totals(message.usage)
                yield {
                    "type": "completed",
                    "backend": self.backend_name,
                    "backend_run_id": message.session_id,
                    "result": {
                        "subtype": "failed" if message.is_error else "completed",
                        "output_text": message.result or "",
                        "total_cost_usd": message.total_cost_usd,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "turns": message.num_turns,
                        "duration_ms": message.duration_ms,
                        "duration_api_ms": message.duration_api_ms,
                        "session_id": message.session_id,
                        "usage": message.usage,
                        "error": message.result if message.is_error else None,
                    },
                }

    async def create_run(
        self,
        session_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        async for event in self._stream_run(prompt, options):
            yield event

    async def continue_run(
        self,
        session_id: str,
        backend_run_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        if not backend_run_id:
            yield {
                "type": "completed",
                "backend": self.backend_name,
                "result": {
                    "subtype": "failed",
                    "error": "Missing backend_run_id for continuation",
                },
            }
            return
        async for event in self._stream_run(prompt, options, resume=backend_run_id):
            yield event

    async def cancel_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> bool:
        return False

    async def poll_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        return BackendResult(
            ok=False,
            session_id=session_id,
            backend=self.backend_name,
            backend_run_id=backend_run_id,
            state="unknown",
            error="Poll not implemented for SDK backend",
        )

    async def result_from_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        return BackendResult(
            ok=False,
            session_id=session_id,
            backend=self.backend_name,
            backend_run_id=backend_run_id,
            state="unknown",
            error="Result fetch not implemented for SDK backend",
        )
