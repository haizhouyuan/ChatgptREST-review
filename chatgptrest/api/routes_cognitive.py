"""OpenMind cognitive-substrate API routes."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from chatgptrest.advisor.runtime import get_advisor_runtime, get_advisor_runtime_if_ready
from chatgptrest.api.client_ip import get_client_ip
from chatgptrest.cognitive.context_service import (
    ContextResolveOptions,
    ContextResolver,
)
from chatgptrest.cognitive.graph_service import GraphQueryOptions, GraphQueryService
from chatgptrest.cognitive.ingest_service import (
    KnowledgeEntitySeed,
    KnowledgeIngestItem,
    KnowledgeIngestService,
)
from chatgptrest.cognitive.memory_capture_service import (
    MemoryCaptureItem,
    MemoryCaptureService,
)
from chatgptrest.cognitive.policy_service import PolicyHintsOptions, PolicyHintsService
from chatgptrest.cognitive.telemetry_service import (
    TelemetryEventInput,
    TelemetryIngestService,
)

logger = logging.getLogger(__name__)


def _coerce_optional_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


class ContextResolveRequest(BaseModel):
    query: str = Field(min_length=1)
    session_key: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    trace_id: str = ""
    token_budget: int = 8000
    sources: list[str] = Field(default_factory=lambda: ["memory", "knowledge", "graph", "policy"])
    graph_scopes: list[str] = Field(default_factory=lambda: ["personal"])
    repo: str = ""
    working_limit: int = 10
    episodic_limit: int = 5
    semantic_limit: int = 3
    kb_top_k: int = 5


class GraphQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=lambda: ["personal_graph"])
    repo: str = ""
    project_id: str = ""
    limit: int = Field(default=10, ge=1, le=50)
    include_edges: bool = True
    include_paths: bool = True
    trace_id: str = ""


class KnowledgeEntityRequest(BaseModel):
    name: str = Field(min_length=1)
    entity_type: str = "tag"
    normalized_name: str = ""


class KnowledgeIngestItemRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    trace_id: str = ""
    session_key: str = ""
    source_system: str = "openclaw"
    source_ref: str = ""
    content_type: str = "markdown"
    project_id: str = ""
    para_bucket: str = "resource"
    structural_role: str = "analysis"
    domain_tags: list[str] = Field(default_factory=list)
    audience: str = "internal"
    security_label: str = "internal"
    risk_level: str = "low"
    estimated_tokens: int = 0
    source_quality: float | None = None
    graph_extract: bool = True
    entities: list[KnowledgeEntityRequest] = Field(default_factory=list)


class KnowledgeIngestRequest(BaseModel):
    items: list[KnowledgeIngestItemRequest] = Field(min_length=1)


class MemoryCaptureItemRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    summary: str = ""
    trace_id: str = ""
    session_key: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    source_system: str = "openclaw"
    source_ref: str = ""
    security_label: str = "internal"
    confidence: float = 0.85
    category: str = "captured_memory"


class MemoryCaptureRequest(BaseModel):
    items: list[MemoryCaptureItemRequest] = Field(min_length=1)


class TelemetryEventRequest(BaseModel):
    type: str = Field(min_length=1)
    source: str = "openclaw"
    domain: str = "execution"
    data: dict[str, Any] = Field(default_factory=dict)
    session_key: str = ""
    security_label: str = "internal"
    event_id: str = ""
    run_id: str = ""
    parent_run_id: str = ""
    job_id: str = ""
    issue_id: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    repo_name: str = ""
    repo_path: str = ""
    repo_branch: str = ""
    repo_head: str = ""
    repo_upstream: str = ""
    agent_name: str = ""
    agent_source: str = ""
    provider: str = ""
    model: str = ""
    commit_sha: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_shape(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "type" not in data and data.get("event_type"):
            data["type"] = data.get("event_type")
        if "session_key" not in data and data.get("session_id"):
            data["session_key"] = data.get("session_id")
        if "data" in data and not isinstance(data.get("data"), dict):
            data["data"] = {"value": data.get("data")}
        for key in (
            "type",
            "source",
            "domain",
            "session_key",
            "security_label",
            "event_id",
            "run_id",
            "parent_run_id",
            "job_id",
            "issue_id",
            "task_ref",
            "logical_task_id",
            "repo_name",
            "repo_path",
            "repo_branch",
            "repo_head",
            "repo_upstream",
            "agent_name",
            "agent_source",
            "provider",
            "model",
            "commit_sha",
        ):
            if key in data:
                data[key] = _coerce_optional_string(data.get(key))
        return data


class TelemetryIngestRequest(BaseModel):
    trace_id: str = ""
    session_key: str = ""
    events: list[TelemetryEventRequest] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _coerce_shape(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "events" not in data:
            event_type = _coerce_optional_string(data.get("type") or data.get("event_type"))
            if event_type:
                session_key = _coerce_optional_string(data.get("session_key") or data.get("session_id"))
                event: dict[str, Any] = {
                    "type": event_type,
                    "source": _coerce_optional_string(data.get("source")) or "openclaw",
                    "domain": _coerce_optional_string(data.get("domain")) or "execution",
                    "session_key": session_key,
                    "data": dict(data),
                }
                for key in (
                    "security_label",
                    "event_id",
                    "run_id",
                    "parent_run_id",
                    "job_id",
                    "issue_id",
                    "task_ref",
                    "logical_task_id",
                    "repo_name",
                    "repo_path",
                    "repo_branch",
                    "repo_head",
                    "repo_upstream",
                    "agent_name",
                    "agent_source",
                    "provider",
                    "model",
                    "commit_sha",
                ):
                    if key in data:
                        event[key] = data.get(key)
                data = {
                    "trace_id": _coerce_optional_string(data.get("trace_id") or data.get("event_id")),
                    "session_key": session_key,
                    "events": [event],
                }
        data["trace_id"] = _coerce_optional_string(data.get("trace_id"))
        data["session_key"] = _coerce_optional_string(data.get("session_key"))
        events = data.get("events")
        if isinstance(events, dict):
            data["events"] = [events]
        return data


class PolicyHintsRequest(BaseModel):
    query: str = Field(min_length=1)
    session_key: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    trace_id: str = ""
    token_budget: int = 1800
    graph_scopes: list[str] = Field(default_factory=lambda: ["personal"])
    repo: str = ""
    audience: str = "internal"
    security_label: str = "internal"
    risk_level: str = "low"
    estimated_tokens: int = 0
    urgency_hint: str = "whenever"


def make_cognitive_router() -> APIRouter:
    _api_key = os.environ.get("OPENMIND_API_KEY", "")
    _auth_mode = os.environ.get("OPENMIND_AUTH_MODE", "strict")
    _rate_limits: dict[str, list[float]] = {}
    _rate_window = 60.0
    _rate_max = int(os.environ.get("OPENMIND_RATE_LIMIT", "10"))

    def _check_rate_limit(client_ip: str) -> bool:
        import time

        now = time.time()
        window = _rate_limits.get(client_ip, [])
        window = [t for t in window if now - t < _rate_window]
        if len(window) >= _rate_max:
            return False
        window.append(now)
        _rate_limits[client_ip] = window
        return True

    async def _require_openmind_auth(request: Request) -> None:
        if request.url.path.endswith("/health"):
            return
        if _auth_mode == "open":
            return  # Explicit opt-in to unauthenticated access
        # strict mode (default): require API key
        if not _api_key:
            raise HTTPException(status_code=503, detail="API key not configured; set OPENMIND_API_KEY or OPENMIND_AUTH_MODE=open")
        provided = request.headers.get("X-Api-Key", "")
        if provided != _api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    async def _require_openmind_rate_limit(request: Request) -> None:
        if request.url.path.endswith("/health"):
            return
        client_ip = get_client_ip(request)
        if not _check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail={"error": "Rate limit exceeded", "limit": f"{_rate_max} req/{int(_rate_window)}s"},
            )

    router = APIRouter(
        prefix="/v2",
        tags=["openmind-cognitive"],
        dependencies=[Depends(_require_openmind_auth), Depends(_require_openmind_rate_limit)],
    )

    @router.get("/cognitive/health")
    def cognitive_health() -> JSONResponse:
        try:
            runtime = get_advisor_runtime_if_ready()
            if runtime is None:
                return JSONResponse(
                    {
                        "ok": False,
                        "status": "not_initialized",
                        "runtime_ready": False,
                        "memory_ready": False,
                        "kb_ready": False,
                        "graph_ready": False,
                    }
                )
            return JSONResponse(
                {
                    "ok": True,
                    "status": "ok",
                    "runtime_ready": True,
                    "memory_ready": runtime.memory is not None,
                    "kb_ready": runtime.kb_hub is not None,
                    "graph_ready": runtime.evomap_knowledge_db is not None,
                }
            )
        except Exception as exc:
            logger.warning("cognitive health probe failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": str(exc),
                    "memory_ready": False,
                    "kb_ready": False,
                    "graph_ready": False,
                },
            )

    @router.post("/context/resolve")
    def context_resolve(body: ContextResolveRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        resolver = ContextResolver(runtime)
        result = resolver.resolve(
            ContextResolveOptions(
                query=body.query.strip(),
                session_id=body.session_key.strip(),
                account_id=body.account_id.strip(),
                agent_id=body.agent_id.strip(),
                role_id=body.role_id.strip(),
                thread_id=body.thread_id.strip(),
                trace_id=body.trace_id.strip(),
                token_budget=body.token_budget,
                sources=tuple(body.sources or []),
                graph_scopes=tuple(body.graph_scopes or []),
                repo=body.repo.strip(),
                working_limit=body.working_limit,
                episodic_limit=body.episodic_limit,
                semantic_limit=body.semantic_limit,
                kb_top_k=body.kb_top_k,
            )
        )
        return JSONResponse(result.to_dict())

    @router.post("/graph/query")
    def graph_query(body: GraphQueryRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        service = GraphQueryService(runtime)
        result = service.query(
            GraphQueryOptions(
                query=body.query.strip(),
                scopes=tuple(body.scopes or []),
                repo=body.repo.strip(),
                project_id=body.project_id.strip(),
                limit=body.limit,
                include_edges=body.include_edges,
                include_paths=body.include_paths,
                trace_id=body.trace_id.strip(),
            )
        )
        return JSONResponse(result.to_dict())

    @router.post("/knowledge/ingest")
    def knowledge_ingest(body: KnowledgeIngestRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        service = KnowledgeIngestService(runtime)
        result = service.ingest(
            [
                KnowledgeIngestItem(
                    title=item.title,
                    content=item.content,
                    trace_id=item.trace_id.strip(),
                    session_id=item.session_key.strip(),
                    source_system=item.source_system.strip(),
                    source_ref=item.source_ref.strip(),
                    content_type=item.content_type.strip(),
                    project_id=item.project_id.strip(),
                    para_bucket=item.para_bucket.strip(),
                    structural_role=item.structural_role.strip(),
                    domain_tags=list(item.domain_tags or []),
                    audience=item.audience.strip(),
                    security_label=item.security_label.strip(),
                    risk_level=item.risk_level.strip(),
                    estimated_tokens=item.estimated_tokens,
                    source_quality=item.source_quality,
                    graph_extract=item.graph_extract,
                    entities=[
                        KnowledgeEntitySeed(
                            name=entity.name,
                            entity_type=entity.entity_type.strip(),
                            normalized_name=entity.normalized_name.strip(),
                        )
                        for entity in item.entities
                    ],
                )
                for item in body.items
            ]
        )
        return JSONResponse(result.to_dict())

    @router.post("/kb/upsert")
    def kb_upsert(body: KnowledgeIngestRequest) -> JSONResponse:
        return knowledge_ingest(body)

    @router.post("/memory/capture")
    def memory_capture(body: MemoryCaptureRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        service = MemoryCaptureService(runtime)
        result = service.capture(
            [
                MemoryCaptureItem(
                    title=item.title,
                    content=item.content,
                    summary=item.summary.strip(),
                    trace_id=item.trace_id.strip(),
                    session_id=item.session_key.strip(),
                    account_id=item.account_id.strip(),
                    agent_id=item.agent_id.strip(),
                    role_id=item.role_id.strip(),
                    thread_id=item.thread_id.strip(),
                    source_system=item.source_system.strip(),
                    source_ref=item.source_ref.strip(),
                    security_label=item.security_label.strip(),
                    confidence=item.confidence,
                    category=item.category.strip(),
                )
                for item in body.items
            ]
        )
        return JSONResponse(result.to_dict())

    @router.post("/telemetry/ingest")
    def telemetry_ingest(body: TelemetryIngestRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        service = TelemetryIngestService(runtime)
        result = service.ingest(
            trace_id=body.trace_id.strip(),
            session_id=body.session_key.strip(),
            events=[
                TelemetryEventInput(
                    event_type=item.type.strip(),
                    source=item.source.strip(),
                    domain=item.domain.strip(),
                    data=dict(item.data or {}),
                    session_id=item.session_key.strip(),
                    security_label=item.security_label.strip(),
                    event_id=item.event_id.strip(),
                    run_id=item.run_id.strip(),
                    parent_run_id=item.parent_run_id.strip(),
                    job_id=item.job_id.strip(),
                    issue_id=item.issue_id.strip(),
                    task_ref=item.task_ref.strip(),
                    logical_task_id=item.logical_task_id.strip(),
                    repo_name=item.repo_name.strip(),
                    repo_path=item.repo_path.strip(),
                    repo_branch=item.repo_branch.strip(),
                    repo_head=item.repo_head.strip(),
                    repo_upstream=item.repo_upstream.strip(),
                    agent_name=item.agent_name.strip(),
                    agent_source=item.agent_source.strip(),
                    provider=item.provider.strip(),
                    model=item.model.strip(),
                    commit_sha=item.commit_sha.strip(),
                )
                for item in body.events
            ],
        )
        return JSONResponse(result.to_dict())

    @router.post("/policy/hints")
    def policy_hints(body: PolicyHintsRequest) -> JSONResponse:
        runtime = get_advisor_runtime()
        service = PolicyHintsService(runtime)
        result = service.resolve(
            PolicyHintsOptions(
                query=body.query.strip(),
                session_id=body.session_key.strip(),
                account_id=body.account_id.strip(),
                agent_id=body.agent_id.strip(),
                role_id=body.role_id.strip(),
                thread_id=body.thread_id.strip(),
                trace_id=body.trace_id.strip(),
                token_budget=body.token_budget,
                graph_scopes=tuple(body.graph_scopes or []),
                repo=body.repo.strip(),
                audience=body.audience.strip(),
                security_label=body.security_label.strip(),
                risk_level=body.risk_level.strip(),
                estimated_tokens=body.estimated_tokens,
                urgency_hint=body.urgency_hint.strip(),
            )
        )
        return JSONResponse(result.to_dict())

    return router
