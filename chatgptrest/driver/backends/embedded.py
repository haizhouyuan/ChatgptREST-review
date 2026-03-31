from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
from typing import Any, Dict

from chatgptrest.driver.api import ToolCallError, ToolCaller


class EmbeddedToolCaller(ToolCaller):
    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        from chatgpt_web_mcp import server as _server

        self._server = _server
        self._tool_map = {
            "chatgpt_web_ask": "ask",
            "chatgpt_web_wait": "wait",
            "chatgpt_web_ask_pro_extended": "ask_pro_extended",
            "chatgpt_web_ask_deep_research": "ask_deep_research",
            "chatgpt_web_ask_web_search": "ask_web_search",
            "chatgpt_web_ask_agent_mode": "ask_agent_mode",
            "chatgpt_web_ask_thinking_heavy_github": "ask_thinking_heavy_github",
        }

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._init_lock:
            if cls._loop is not None and cls._thread is not None and cls._thread.is_alive():
                return cls._loop

            ready = threading.Event()

            def _runner() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                cls._loop = loop
                ready.set()
                loop.run_forever()

            cls._thread = threading.Thread(target=_runner, name="chatgptrest-embedded-driver", daemon=True)
            cls._thread.start()
            if not ready.wait(timeout=5.0) or cls._loop is None:
                raise ToolCallError("Failed to start embedded driver event loop")
            return cls._loop

    def call_tool(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timeout_sec: float = 600.0,
    ) -> Dict[str, Any]:
        loop = self._ensure_loop()
        attr = self._tool_map.get(str(tool_name), str(tool_name))
        func = getattr(self._server, attr, None)
        if func is None or not callable(func):
            raise ToolCallError(f"Unknown embedded tool: {tool_name}")

        kwargs = dict(tool_args or {})
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            sig = None
        if sig is not None and "ctx" in sig.parameters and "ctx" not in kwargs:
            kwargs["ctx"] = None

        async def _run() -> Dict[str, Any]:
            result = func(**kwargs)
            if inspect.isawaitable(result):
                return await asyncio.wait_for(result, timeout=float(timeout_sec))
            return result

        try:
            fut = asyncio.run_coroutine_threadsafe(_run(), loop)
            return fut.result(timeout=float(timeout_sec))
        except concurrent.futures.TimeoutError as exc:
            try:
                fut.cancel()
            except Exception:
                pass
            raise ToolCallError(f"Embedded tool timeout: {tool_name}") from exc
        except Exception as exc:
            raise ToolCallError(str(exc)) from exc
