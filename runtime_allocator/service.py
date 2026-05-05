"""FastAPI HTTP service wrapping execute_with_fallback().

Endpoints:
- POST /v1/execute          — Run a task with fallback routing
- POST /v1/preflight        — Pre-execution safety check
- POST /v1/closeout         — Post-execution validation
- GET  /health              — Service health check
- GET  /v1/health/providers — Per-provider health status
- GET  /metrics             — Prometheus metrics
- GET  /v1/summary          — Runtime state summary (admin)
- GET  /v1/billing/daily    — Daily cost attribution
- GET  /v1/billing/alerts   — Budget overage alerts

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
from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope
from runtime_allocator.cost_attribution import CostAttribution
from runtime_allocator.preflight_gate import preflight
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
GATE_COUNTER = Counter(
    "paperclip_gate_checks_total",
    "Total gate checks",
    ["gate", "status"],
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
    write_scope: str = Field(default="read_only", description="read_only | append_only | mutate")


class ExecuteResponse(BaseModel):
    success: bool
    provider_id: str
    model_name: str
    content: str = ""
    terminal_state: str = ""
    requires_human_review: bool = False
    error: str = ""
    latency_ms: float = 0.0
    preflight_status: str = ""
    closeout_status: str = ""


class PreflightRequest(BaseModel):
    task_prompt: str
    agent_slug: str = ""
    task_type: str
    model_lane: str = ""
    write_scope: Optional[str] = None


class CloseoutRequest(BaseModel):
    task_type: str
    write_scope: str = "read_only"
    files_changed: list[str] = Field(default_factory=list)
    files_declared: list[str] = Field(default_factory=list)
    evidence_spans: list[str] = Field(default_factory=list)
    memory_deltas: list[dict] = Field(default_factory=list)
    review_state: str = "pending"


class HealthResponse(BaseModel):
    status: str
    version: str = "p4.0"
    uptime_seconds: float = 0.0


# ── Lifecycle ──────────────────────────────────────────────────────────────

_start_time: float = 0.0
_store: Optional[RuntimeStateStore] = None
_cost_attribution: Optional[CostAttribution] = None


def _get_store() -> RuntimeStateStore:
    global _store
    if _store is None:
        _store = RuntimeStateStore()
    return _store


def _get_cost_attribution() -> CostAttribution:
    global _cost_attribution
    if _cost_attribution is None:
        _cost_attribution = CostAttribution(_get_store())
    return _cost_attribution


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

    # ── Preflight gate ──────────────────────────────────────────────────
    pf = preflight(
        task_prompt=req.messages[0].get("content", "") if req.messages else "",
        agent_slug="api_client",
        task_type=req.task_class,
        model_lane="",
        declared_write_scope=WriteScope(req.write_scope) if req.write_scope else None,
    )
    GATE_COUNTER.labels(gate="preflight", status=pf.status.value).inc()
    if pf.status == GateStatus.BLOCKED:
        logger.warning("preflight_blocked", extra={"task_class": req.task_class, "reasons": pf.reason_codes})
        return ExecuteResponse(
            success=False,
            provider_id="blocked",
            model_name="",
            terminal_state="blocked",
            error=f"Preflight blocked: {pf.detail}",
            preflight_status=pf.status.value,
        )
    if pf.status == GateStatus.HUMAN_REVIEW_REQUIRED:
        logger.info("preflight_review", extra={"task_class": req.task_class, "reasons": pf.reason_codes})

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
            preflight_status=pf.status.value,
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

    # ── Closeout gate ───────────────────────────────────────────────────
    co = closeout(
        task_type=req.task_class,
        write_scope=WriteScope(req.write_scope),
        files_changed=[],
        files_declared=[],
        evidence_spans=[result.content] if result.content else [],
        memory_deltas=[],
        review_state="pending",
    )
    GATE_COUNTER.labels(gate="closeout", status=co.status.value).inc()
    if co.status == GateStatus.BLOCKED:
        logger.warning("closeout_blocked", extra={"task_class": req.task_class, "reasons": co.reason_codes})

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
        requires_human_review=result.requires_human_review or (pf.status == GateStatus.HUMAN_REVIEW_REQUIRED),
        error=result.error or "",
        latency_ms=round(latency * 1000, 2),
        preflight_status=pf.status.value,
        closeout_status=co.status.value,
    )


@app.post("/v1/preflight")
async def preflight_check(
    req: PreflightRequest,
    role: str = Depends(require_api_key),
):
    """Standalone preflight safety check."""
    result = preflight(
        task_prompt=req.task_prompt,
        agent_slug=req.agent_slug,
        task_type=req.task_type,
        model_lane=req.model_lane,
        declared_write_scope=WriteScope(req.write_scope) if req.write_scope else None,
    )
    GATE_COUNTER.labels(gate="preflight", status=result.status.value).inc()
    return result.model_dump()


@app.post("/v1/closeout")
async def closeout_check(
    req: CloseoutRequest,
    role: str = Depends(require_api_key),
):
    """Standalone closeout validation."""
    result = closeout(
        task_type=req.task_type,
        write_scope=WriteScope(req.write_scope),
        files_changed=req.files_changed,
        files_declared=req.files_declared,
        evidence_spans=req.evidence_spans,
        memory_deltas=req.memory_deltas,
        review_state=req.review_state,
    )
    GATE_COUNTER.labels(gate="closeout", status=result.status.value).inc()
    return result.model_dump()


@app.get("/health", response_model=HealthResponse)
async def health():
    """Service health check."""
    uptime = time.time() - _start_time if _start_time else 0.0
    return HealthResponse(status="healthy", uptime_seconds=round(uptime, 2))


@app.get("/v1/health/providers")
async def provider_health(role: str = Depends(require_api_key)):
    """Per-provider health status."""
    store = _get_store()
    with store._connect() as conn:
        rows = conn.execute("SELECT * FROM runtime_health").fetchall()
    return {
        "providers": [
            {
                "provider_id": r["provider_id"],
                "status": r["status"],
                "last_probe_at": r["last_probe_at"],
                "consecutive_failures": r["consecutive_failures"],
                "circuit_open_until": r["circuit_open_until"],
            }
            for r in rows
        ]
    }


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


@app.get("/v1/billing/daily")
async def billing_daily(
    company_id: str = "",
    date: Optional[str] = None,
    role: str = Depends(require_api_key),
):
    """Daily cost attribution per provider."""
    ca = _get_cost_attribution()
    return ca.daily_summary(company_id=company_id, date=date)


@app.get("/v1/billing/alerts")
async def billing_alerts(
    company_id: str = "",
    daily_budget_usd: float = 10.0,
    role: str = Depends(require_api_key),
):
    """Check if daily budget is exceeded."""
    ca = _get_cost_attribution()
    alert = ca.alert_if_over_budget(company_id=company_id, daily_budget_usd=daily_budget_usd)
    if alert:
        return alert
    return {"alert": None, "company_id": company_id, "daily_budget_usd": daily_budget_usd}


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PAPERCLIP_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
