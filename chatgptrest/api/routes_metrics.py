"""Prometheus-compatible /metrics endpoint.

Returns ``text/plain; charset=utf-8`` via ``PlainTextResponse`` to avoid
FastAPI's default JSON encoding.  Label values are escaped per the
Prometheus exposition format spec.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

from chatgptrest.core.config import AppConfig


def _escape_label(val: Any) -> str:
    """Escape a label value for Prometheus exposition format.

    Rules: backslash → \\\\, newline → \\n, double-quote → \\\".
    """
    s = str(val)
    s = s.replace("\\", "\\\\")
    s = s.replace("\n", "\\n")
    s = s.replace('"', '\\"')
    return s


def make_metrics_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter(tags=["metrics"])

    @router.get(
        "/metrics",
        response_class=PlainTextResponse,
        summary="Prometheus metrics",
    )
    def metrics() -> PlainTextResponse:
        lines: list[str] = []
        now = time.time()

        # ── process uptime ────────────────────────────────────────────
        lines.append("# HELP chatgptrest_up Whether the API is running")
        lines.append("# TYPE chatgptrest_up gauge")
        lines.append("chatgptrest_up 1")

        # ── build info ────────────────────────────────────────────────
        lines.append("# HELP chatgptrest_build_info Build metadata")
        lines.append("# TYPE chatgptrest_build_info gauge")
        sha = _escape_label(os.environ.get("CHATGPTREST_GIT_SHA", "unknown"))
        dirty = _escape_label(os.environ.get("CHATGPTREST_GIT_DIRTY", ""))
        lines.append(
            f'chatgptrest_build_info{{git_sha="{sha}",git_dirty="{dirty}"}} 1'
        )

        body = "\n".join(lines) + "\n"
        return PlainTextResponse(body, media_type="text/plain; charset=utf-8")

    return router
