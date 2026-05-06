from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

try:
    import fcntl  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - platform dependent
    fcntl = None

from chatgpt_web_mcp.env import _truthy_env


def _call_log_path() -> Path | None:
    raw = (
        os.environ.get("MCP_CALL_LOG")
        or os.environ.get("CHATGPT_CALL_LOG")
        or os.environ.get("GEMINI_CALL_LOG")
        or ""
    ).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _call_log_include_prompts() -> bool:
    return _truthy_env("MCP_CALL_LOG_INCLUDE_PROMPTS", False)


def _call_log_include_answers() -> bool:
    return _truthy_env("MCP_CALL_LOG_INCLUDE_ANSWERS", False)


def _maybe_append_call_log(event: dict[str, Any]) -> None:
    path = _call_log_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(event)
        payload.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        payload.setdefault("pid", os.getpid())
        with path.open("a", encoding="utf-8") as f:
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except Exception:
                    pass
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
    except Exception:
        return
