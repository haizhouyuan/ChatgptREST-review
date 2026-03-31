from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - platform dependent
    fcntl = None


@asynccontextmanager
async def _flock_exclusive(path: Path) -> Any:
    if fcntl is None:
        yield None
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("a+", encoding="utf-8")
    try:
        await asyncio.to_thread(fcntl.flock, f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        try:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        finally:
            f.close()


_SERVER_SINGLETON_LOCK: Any | None = None


def _server_singleton_lock_file() -> Path:
    raw = (os.environ.get("MCP_SERVER_LOCK_FILE") or ".run/chatgpt_web_mcp_server.lock").strip()
    return Path(raw).expanduser()


def _server_singleton_lock_disabled() -> bool:
    raw = (os.environ.get("MCP_DISABLE_SINGLETON") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _acquire_server_singleton_lock_or_die(*, transport: str) -> None:
    global _SERVER_SINGLETON_LOCK
    if transport == "stdio":
        return
    if _server_singleton_lock_disabled():
        return
    lock_file = _server_singleton_lock_file()
    if fcntl is None:
        return
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    f = lock_file.open("a+", encoding="utf-8")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            f.close()
        finally:
            raise SystemExit(
                f"Another MCP server instance is already running (singleton lock held): {lock_file}. "
                "Stop the existing server, set MCP_DISABLE_SINGLETON=1, "
                "or set MCP_SERVER_LOCK_FILE to a different path."
            )
    try:
        f.seek(0)
        f.truncate()
        f.write(f"pid={os.getpid()}\n")
        f.flush()
    except Exception:
        pass
    _SERVER_SINGLETON_LOCK = f
