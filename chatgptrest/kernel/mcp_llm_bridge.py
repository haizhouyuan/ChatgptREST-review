"""MCP LLM Bridge — unified interface for web/CLI model invocation.

Wraps chatgpt_web_mcp async tools as a sync ``llm_fn(prompt, system_msg) → str``
callable that the advisor graph can use transparently. Provides multi-backend
model invocation through MCP tools:

  - ChatGPT Web:  chatgpt_web_ask (Playwright automation)
  - Gemini Web:   gemini_web_ask / gemini_web_ask_pro (Playwright)
  - Gemini CLI:   subprocess gemini CLI invocation

Usage::

    bridge = McpLlmBridge()
    answer = bridge.ask("chatgpt-web", "What is quantum computing?")
    # → str (the model's answer)

    # Or as llm_fn for graph.py:
    llm_fn = bridge.make_llm_fn("gemini-web")
    answer = llm_fn("Analyze X", "You are a research assistant.")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)


class McpLlmBridge:
    """Bridge between ModelRouter's provider types and actual MCP invocations.

    Translates model names (e.g. "chatgpt-web", "gemini-web", "gemini-cli")
    into the correct MCP tool call (async → sync).
    """

    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout

    def ask(self, model: str, prompt: str, system_msg: str = "") -> str:
        """Invoke an MCP-backed model and return the answer text.

        Args:
            model: Model name from ModelRouter (e.g. "chatgpt-web", "gemini-web", "gemini-cli")
            prompt: The user prompt
            system_msg: Optional system message (prepended to prompt for web models)

        Returns:
            The model's answer as a string, or empty string on failure.
        """
        import time
        start = time.perf_counter()
        answer = ""
        try:
            if model == "chatgpt-web":
                answer = self._call_chatgpt_web(prompt, system_msg)
            elif model == "gemini-web":
                answer = self._call_gemini_web(prompt, system_msg)
            elif model == "gemini-cli":
                answer = self._call_gemini_cli(prompt, system_msg)
            else:
                logger.warning("McpLlmBridge: unknown model %s", model)
                return ""
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self._emit_signal("llm.call_failed", {
                "model": model, "provider": "mcp",
                "error": str(e)[:100], "latency_ms": elapsed_ms,
                "error_category": self._classify_error(e),
            })
            raise

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        sig_type = "llm.call_completed" if answer else "llm.call_failed"
        payload: dict[str, Any] = {
            "model": model, "provider": "mcp",
            "latency_ms": elapsed_ms, "status": "success" if answer else "empty",
            "tokens_est": len(answer) // 4 if answer else 0,
        }
        if not answer:
            payload["error_category"] = "empty_response"
        self._emit_signal(sig_type, payload)
        return answer

    def make_llm_fn(self, model: str):
        """Create an llm_fn callable for a specific MCP model.

        Returns a function matching graph.py's llm_fn interface:
            llm_fn(prompt: str, system_msg: str) -> str
        """
        def _fn(prompt: str, system_msg: str = "") -> str:
            return self.ask(model, prompt, system_msg)
        _fn.__name__ = f"mcp_{model.replace('-', '_')}"
        return _fn

    def is_mcp_model(self, model: str) -> bool:
        """Check if a model requires MCP invocation (vs Coding Plan API)."""
        return model in {"chatgpt-web", "gemini-web", "gemini-cli"}

    # ── ChatGPT Web via chatgpt_web_mcp ─────────────────────────

    def _call_chatgpt_web(self, prompt: str, system_msg: str) -> str:
        """Call ChatGPT Web UI via Playwright MCP tool."""
        full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
        idem_key = self._make_idem_key("chatgpt_web", prompt)

        try:
            from chatgpt_web_mcp._tools_impl import ask as chatgpt_web_ask
            result = self._run_async(chatgpt_web_ask(
                question=full_prompt,
                idempotency_key=idem_key,
                timeout_seconds=self._timeout,
            ))
            if result.get("ok") and result.get("answer"):
                logger.info(
                    "ChatGPT Web: %d chars in %.1fs",
                    len(result["answer"]), result.get("elapsed_seconds", 0),
                )
                return result["answer"]
            else:
                logger.warning("ChatGPT Web failed: %s", result.get("error", "unknown"))
                return ""
        except Exception as e:
            logger.warning("ChatGPT Web invocation error: %s", e)
            return ""

    # ── Gemini Web via chatgpt_web_mcp providers ────────────────

    def _call_gemini_web(self, prompt: str, system_msg: str) -> str:
        """Call Gemini Web UI via Playwright MCP tool."""
        full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt
        idem_key = self._make_idem_key("gemini_web", prompt)

        try:
            from chatgpt_web_mcp.providers.gemini.ask import gemini_web_ask_pro
            result = self._run_async(gemini_web_ask_pro(
                question=full_prompt,
                idempotency_key=idem_key,
                timeout_seconds=self._timeout,
            ))
            if result.get("ok") and result.get("answer"):
                logger.info(
                    "Gemini Web Pro: %d chars in %.1fs",
                    len(result["answer"]), result.get("elapsed_seconds", 0),
                )
                return result["answer"]
            else:
                logger.warning("Gemini Web failed: %s", result.get("error", "unknown"))
                return ""
        except Exception as e:
            logger.warning("Gemini Web invocation error: %s", e)
            return ""

    # ── Gemini CLI (subprocess) ─────────────────────────────────

    def _call_gemini_cli(self, prompt: str, system_msg: str) -> str:
        """Call Gemini CLI as a subprocess.

        Uses ``gemini`` CLI tool with -p flag for non-interactive prompt.
        Leverages Google One Ultra subscription for Gemini Pro 3.1 Preview.
        """
        full_prompt = f"{system_msg}\n\n{prompt}" if system_msg else prompt

        try:
            # Try gemini CLI (from Gemini CLI MCP project)
            result = subprocess.run(
                ["gemini", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=None,  # inherit env
            )
            if result.returncode == 0 and result.stdout.strip():
                answer = result.stdout.strip()
                logger.info("Gemini CLI: %d chars", len(answer))
                return answer
            else:
                logger.warning(
                    "Gemini CLI failed (rc=%d): %s",
                    result.returncode, result.stderr[:200],
                )
                return ""
        except FileNotFoundError:
            logger.warning("Gemini CLI not found — install gemini CLI tool")
            return ""
        except subprocess.TimeoutExpired:
            logger.warning("Gemini CLI timed out after %ds", self._timeout)
            return ""
        except Exception as e:
            logger.warning("Gemini CLI error: %s", e)
            return ""

    # ── EvoMap Signal Emission ────────────────────────────────────

    def _emit_signal(self, signal_type: str, data: dict) -> None:
        """Emit EvoMap signal for MCP LLM observability. Fail-open."""
        try:
            from chatgptrest.evomap.signals import Signal
            from chatgptrest.advisor.graph import _svc
            svc = _svc()
            obs = getattr(svc, "evomap_observer", None)
            if obs:
                signal = Signal(
                    signal_type=signal_type,
                    source="mcp_bridge",
                    domain="llm",
                    data=data,
                )
                obs.record(signal)
        except Exception:
            pass  # fail-open: never break MCP calls for observability

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        """Classify an exception into an error category for EvoMap signals."""
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return "timeout"
        if "429" in msg or "rate limit" in msg or "rate_limit" in msg:
            return "rate_limit_429"
        if "context" in msg and ("exceed" in msg or "length" in msg or "too long" in msg):
            return "context_exceeded"
        if "json" in msg and ("decode" in msg or "parse" in msg):
            return "json_decode"
        if "503" in msg or "service unavailable" in msg:
            return "provider_503"
        if "401" in msg or "403" in msg or "auth" in msg or "unauthorized" in msg:
            return "auth_error"
        if "connection" in msg or "connect" in msg:
            return "connection_error"
        return "unknown"

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_idem_key(tool: str, prompt: str) -> str:
        """Generate idempotency key for MCP tool calls."""
        h = hashlib.md5(prompt.encode()[:500]).hexdigest()[:8]
        ts = int(time.time())
        return f"advisor_{tool}_{ts}_{h}"

    @staticmethod
    def _run_async(coro) -> Any:
        """Run an async coroutine from sync code.

        Creates a new event loop if needed (safe for non-async callers).
        If already in an async context, runs coro on a dedicated worker thread
        with its own event loop to avoid deadlock.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # No event loop — create one
            return asyncio.run(coro)
        else:
            # Already in async context — run on a separate thread to avoid deadlock
            # (run_coroutine_threadsafe + result() on the same loop = deadlock)
            import concurrent.futures
            result_box: list[Any] = [None]
            error_box: list[Exception | None] = [None]

            def _worker():
                try:
                    result_box[0] = asyncio.run(coro)
                except Exception as e:
                    error_box[0] = e

            thread = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = thread.submit(_worker)
            future.result(timeout=180)
            thread.shutdown(wait=False)

            if error_box[0] is not None:
                raise error_box[0]
            return result_box[0]
