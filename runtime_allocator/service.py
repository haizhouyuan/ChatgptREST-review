"""FastAPI HTTP service wrapping execute_with_fallback().

Endpoints:
- POST /v1/execute          — Run a task with fallback routing
- GET  /health              — Service health check
- GET  /metrics             — Prometheus metrics
- GET  /v1/summary          — Runtime state summary (admin)

Environment:
- PAPERCLIP_API_KEYS        — Comma-separated key:role pairs
- PAPERCLIP_PORT            — Server port (default 8080)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from runtime_allocator.auth import require_admin, require_api_key
from runtime_allocator.runtime_state import RuntimeStateStore
from runtime_allocator.schemas import CommerceDecisionOutput
from runtime_allocator.skill_agent import execute_with_fallback

# ── Structured logging ─────────────────────────────────────────────────────

logger = logging.getLogger("paperclip_service")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
))
logger.addHandler(_handler)


# ── Prometheus metrics ─────────────────────────────────────────────────────

EXECUTION_COUNTER = Counter(
    "paperclip_executions_total",
    "Total task executions",
    ["task_class", "status", "provider_id"],
)
EXECUTION_LATENCY = Histogram(
    "paperclip_execution_latency_seconds",
    "Execution latency",
    ["task_class"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)
FALLBACK_COUNTER = Counter(
    "paperclip_fallbacks_total",
    "Total fallback events",
    ["from_provider", "to_provider"],
)


# ── Pydantic request/response models ───────────────────────────────────────

class ExecuteRequest(BaseModel):
    task_class: str = Field(description="Task class key (e.g. 'dtc_copy')")
    messages: list[dict] = Field(default_factory=list, description="OpenAI-style messages")
    model: str = Field(default="", description="Optional model override")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    response_format: Optional[dict] = Field(default=None)
    timeout: float = Field(default=120.0, ge=1.0)
    company_id: str = Field(default="", description="Multi-tenant company id")
    high_stakes: bool = Field(default=False)
    privacy_tier: str = Field(default="external_cloud")


class ExecuteResponse(BaseModel):
    success: bool
    provider_id: str
    model_name: str
    content: str = ""
    terminal_state: str = ""
    requires_human_review: bool = False
    error: str = ""
    latency_ms: float = 0.0


class HealthResponse(BaseModel):
    status: str
    version: str = "p4.0"
    uptime_seconds: float = 0.0


# ── Lifecycle ──────────────────────────────────────────────────────────────

_start_time: float = 0.0
_store: Optional[RuntimeStateStore] = None


def _get_store() -> RuntimeStateStore:
    global _store
    if _store is None:
        _store = RuntimeStateStore()
    return _store


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.time()
    logger.info("service_start", extra={"version": "p4.0"})
    yield
    logger.info("service_stop")


app = FastAPI(
    title="Paperclip Runtime Allocator",
    version="p4.0",
    lifespan=lifespan,
)


# ── Middleware: request logging + error handling ───────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("request_error", extra={"path": request.url.path, "error": str(exc)})
        raise
    duration = time.time() - start
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", extra={"path": request.url.path, "error": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/v1/execute", response_model=ExecuteResponse)
async def execute(
    req: ExecuteRequest,
    role: str = Depends(require_api_key),
):
    """Execute a task with provider fallback routing."""
    store = _get_store()

    start = time.time()
    try:
        result = execute_with_fallback(
            task_class=req.task_class,
            messages=req.messages,
            state_store=store,
            schema_model=CommerceDecisionOutput,
            model=req.model or None,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            response_format=req.response_format,
            timeout=req.timeout,
            high_stakes=req.high_stakes,
            privacy_tier=req.privacy_tier,
        )
    except Exception as exc:
        latency = time.time() - start
        EXECUTION_COUNTER.labels(
            task_class=req.task_class, status="error", provider_id="none"
        ).inc()
        logger.error(
            "execute_error",
            extra={"task_class": req.task_class, "error": str(exc)},
        )
        return ExecuteResponse(
            success=False,
            provider_id="",
            model_name="",
            error=str(exc),
            latency_ms=round(latency * 1000, 2),
        )

    latency = time.time() - start
    EXECUTION_LATENCY.labels(task_class=req.task_class).observe(latency)
    status_label = "success" if result.success else "blocked"
    EXECUTION_COUNTER.labels(
        task_class=req.task_class,
        status=status_label,
        provider_id=result.provider_id or "none",
    ).inc()

    if result.fallback_from and result.provider_id:
        FALLBACK_COUNTER.labels(
            from_provider=result.fallback_from, to_provider=result.provider_id
        ).inc()

    logger.info(
        "execute_complete",
        extra={
            "task_class": req.task_class,
            "provider_id": result.provider_id,
            "terminal_state": result.terminal_state,
            "latency_ms": round(latency * 1000, 2),
        },
    )

    return ExecuteResponse(
        success=result.success,
        provider_id=result.provider_id or "",
        model_name=result.model_name or "",
        content=result.content or "",
        terminal_state=result.terminal_state or "",
        requires_human_review=result.requires_human_review,
        error=result.error or "",
        latency_ms=round(latency * 1000, 2),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Service health check."""
    uptime = time.time() - _start_time if _start_time else 0.0
    return HealthResponse(status="healthy", uptime_seconds=round(uptime, 2))


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/v1/summary")
async def summary(role: str = Depends(require_admin)):
    """Runtime state summary (admin only)."""
    store = _get_store()
    return store.summary()


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PAPERCLIP_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
