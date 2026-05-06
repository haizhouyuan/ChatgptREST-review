from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from chatgptrest.core.config import AppConfig
from chatgptrest.dashboard import DashboardService
from chatgptrest.dashboard.shared_cognition_scoreboard import build_shared_cognition_status_board


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "templates"
STATIC_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "static"
DEFAULT_DEDICATED_DASHBOARD_BASE_URL = "http://127.0.0.1:8787/dashboard"


def _fmt_ts(raw: Any) -> str:
    try:
        value = float(raw)
    except Exception:
        return "n/a"
    if value <= 0:
        return "n/a"
    return dt.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _age_label(raw: Any) -> str:
    try:
        value = float(raw)
    except Exception:
        return "n/a"
    if value <= 0:
        return "n/a"
    delta = max(0.0, dt.datetime.now().timestamp() - value)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86_400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86_400)}d ago"


def _status_tone(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"healthy", "ok", "completed", "closed", "resolved", "idle", "success"}:
        return "success"
    if value in {"running", "working", "in_progress", "queued", "pending", "accent"}:
        return "accent"
    if value in {"warning", "degraded", "open", "needs_followup", "cooldown", "stale"}:
        return "warning"
    if value in {"blocked", "error", "failed", "critical", "danger"}:
        return "danger"
    return "neutral"


def _templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.filters["fmt_ts"] = _fmt_ts
    templates.env.filters["age_label"] = _age_label
    templates.env.filters["status_tone"] = _status_tone
    templates.env.globals["status_tone"] = _status_tone
    return templates


def _dedicated_dashboard_base_url() -> str:
    raw = str(os.environ.get("CHATGPTREST_DEDICATED_DASHBOARD_BASE_URL") or DEFAULT_DEDICATED_DASHBOARD_BASE_URL).strip()
    return raw.rstrip("/")


def _proxy_dashboard_snapshot(*, path: str, fallback) -> dict[str, Any]:
    base_url = _dedicated_dashboard_base_url()
    url = f"{base_url}/api/{str(path).lstrip('/')}"
    try:
        with urllib.request.urlopen(url, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        pass
    return fallback()


def _nav_items() -> list[dict[str, str]]:
    return [
        {"key": "investor", "label": "Investor", "href": "/v2/dashboard/investor"},
        {"key": "overview", "label": "Overview", "href": "/v2/dashboard/overview"},
        {"key": "runs", "label": "Runs", "href": "/v2/dashboard/runs"},
        {"key": "runtime", "label": "Runtime", "href": "/v2/dashboard/runtime"},
        {"key": "identity", "label": "Identity", "href": "/v2/dashboard/identity"},
        {"key": "incidents", "label": "Incidents", "href": "/v2/dashboard/incidents"},
        {"key": "cognitive", "label": "Cognitive", "href": "/v2/dashboard/cognitive"},
        {"key": "graph", "label": "Graph", "href": "/v2/dashboard/graph"},
    ]


def _investor_nav_items() -> list[dict[str, str]]:
    return [
        {"key": "investor", "label": "Investor Home", "href": "/v2/dashboard/investor"},
    ]


def _render_page(
    *,
    request: Request,
    templates: Jinja2Templates,
    template_name: str,
    page_key: str,
    page_title: str,
    page_description: str,
    snapshot: dict[str, Any],
    json_href: str,
) -> Any:
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "page_key": page_key,
            "page_title": page_title,
            "page_description": page_description,
            "nav_items": _nav_items(),
            "json_href": json_href,
            "snapshot": snapshot,
        },
    )


def _render_investor_page(
    *,
    request: Request,
    templates: Jinja2Templates,
    template_name: str,
    page_key: str,
    page_title: str,
    page_description: str,
    snapshot: dict[str, Any],
    json_href: str,
) -> Any:
    return templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "page_key": page_key,
            "page_title": page_title,
            "page_description": page_description,
            "nav_items": _investor_nav_items(),
            "json_href": json_href,
            "snapshot": snapshot,
        },
    )


def make_dashboard_router(cfg: AppConfig, *, service: DashboardService | None = None) -> APIRouter:
    router = APIRouter(prefix="/v2/dashboard", tags=["dashboard"])
    service = service or DashboardService(cfg)
    templates = _templates()

    def _graph_page(request: Request, *, json_href: str) -> Any:
        snapshot = service.graph_snapshot()
        return _render_page(
            request=request,
            templates=templates,
            template_name="graph.html",
            page_key="graph",
            page_title="Execution Lineage Graph",
            page_description="Execution lineage first: task, run, job, lane, issue, and incident relationships from the dashboard control plane.",
            snapshot=snapshot,
            json_href=json_href,
        )

    @router.get("/", name="dashboard_root")
    def dashboard_root() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/overview", status_code=307)

    @router.get("/assets/{asset_name}", name="dashboard_asset")
    def dashboard_asset(asset_name: str) -> FileResponse:
        allowed = {"dashboard.css", "dashboard.js"}
        if asset_name not in allowed:
            raise HTTPException(status_code=404, detail="asset_not_found")
        path = STATIC_DIR / asset_name
        if not path.exists():
            raise HTTPException(status_code=404, detail="asset_missing")
        media_type = "text/css" if asset_name.endswith(".css") else "application/javascript"
        return FileResponse(path=str(path), media_type=media_type)

    @router.get("/api/overview", name="dashboard_overview_api")
    def dashboard_overview_api() -> JSONResponse:
        return JSONResponse(service.overview_snapshot())

    @router.get("/api/command-center", name="dashboard_command_center_api")
    def dashboard_command_center_api() -> JSONResponse:
        return JSONResponse(_proxy_dashboard_snapshot(path="command-center", fallback=service.overview_snapshot))

    @router.get("/api/investor", name="dashboard_investor_api")
    def dashboard_investor_api() -> JSONResponse:
        return JSONResponse(service.investor_snapshot())

    @router.get("/api/status", name="dashboard_status_api")
    def dashboard_status_api() -> JSONResponse:
        return JSONResponse(build_shared_cognition_status_board())

    @router.get("/investor", name="dashboard_investor_page")
    def dashboard_investor_page(request: Request) -> Any:
        snapshot = service.investor_snapshot()
        return _render_investor_page(
            request=request,
            templates=templates,
            template_name="investor.html",
            page_key="investor",
            page_title="Investor Research Desk",
            page_description="Only the investing surface: theme progress, opportunity radar, strongest sources, KOL coverage, and clickable links into reports, specs, and evidence.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/investor",
        )

    @router.get("/api/investor/themes/{theme_slug}", name="dashboard_investor_theme_api")
    def dashboard_investor_theme_api(theme_slug: str) -> JSONResponse:
        try:
            return JSONResponse(service.investor_theme_detail(theme_slug))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "theme_not_found", "theme_slug": str(exc)}) from exc

    @router.get("/investor/themes/{theme_slug}", name="dashboard_investor_theme_page")
    def dashboard_investor_theme_page(request: Request, theme_slug: str) -> Any:
        try:
            snapshot = service.investor_theme_detail(theme_slug)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "theme_not_found", "theme_slug": str(exc)}) from exc
        return _render_investor_page(
            request=request,
            templates=templates,
            template_name="investor_theme_detail.html",
            page_key="investor_theme",
            page_title=snapshot["theme"]["title"],
            page_description="Theme logic, best expression, current posture, forcing events, and direct links back to the spec and run documents.",
            snapshot=snapshot,
            json_href=f"/v2/dashboard/api/investor/themes/{theme_slug}",
        )

    @router.get("/api/investor/opportunities/{candidate_id}", name="dashboard_investor_opportunity_api")
    def dashboard_investor_opportunity_api(candidate_id: str) -> JSONResponse:
        try:
            return JSONResponse(service.investor_opportunity_detail(candidate_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "opportunity_not_found", "candidate_id": str(exc)}) from exc

    @router.get("/investor/opportunities/{candidate_id}", name="dashboard_investor_opportunity_page")
    def dashboard_investor_opportunity_page(request: Request, candidate_id: str) -> Any:
        try:
            snapshot = service.investor_opportunity_detail(candidate_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "opportunity_not_found", "candidate_id": str(exc)}) from exc
        return _render_investor_page(
            request=request,
            templates=templates,
            template_name="investor_opportunity_detail.html",
            page_key="investor_opportunity",
            page_title=snapshot["opportunity"]["candidate_id"],
            page_description="Why the opportunity surfaced, which theme should absorb it, and what first-hand sources should be checked next.",
            snapshot=snapshot,
            json_href=f"/v2/dashboard/api/investor/opportunities/{candidate_id}",
        )

    @router.get("/api/investor/sources/{source_id}", name="dashboard_investor_source_api")
    def dashboard_investor_source_api(source_id: str) -> JSONResponse:
        try:
            return JSONResponse(service.investor_source_detail(source_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": str(exc)}) from exc

    @router.get("/investor/sources/{source_id}", name="dashboard_investor_source_page")
    def dashboard_investor_source_page(request: Request, source_id: str) -> Any:
        try:
            snapshot = service.investor_source_detail(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": str(exc)}) from exc
        return _render_investor_page(
            request=request,
            templates=templates,
            template_name="investor_source_detail.html",
            page_key="investor_source",
            page_title=snapshot["source"]["name"],
            page_description="Why this source matters, where it is used, and whether it should keep occupying an investor attention slot.",
            snapshot=snapshot,
            json_href=f"/v2/dashboard/api/investor/sources/{source_id}",
        )

    @router.get("/api/investor/graph", name="dashboard_investor_graph_api")
    def dashboard_investor_graph_api() -> JSONResponse:
        return JSONResponse(service.investor_graph_snapshot())

    @router.get("/reader", name="dashboard_reader_page")
    def dashboard_reader_page(request: Request, path: str = Query(...)) -> Any:
        try:
            snapshot = service.read_dashboard_document(path)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail={"error": "reader_path_forbidden", "path": str(exc)}) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"error": "reader_path_missing", "path": str(exc)}) from exc
        return _render_page(
            request=request,
            templates=templates,
            template_name="reader.html",
            page_key="investor",
            page_title=snapshot["reader_title"],
            page_description="Whitelisted document reader for finagent reports, specs, and finbot inbox artifacts.",
            snapshot=snapshot,
            json_href="",
        )

    @router.get("/overview", name="dashboard_overview_page")
    def dashboard_overview_page(request: Request) -> Any:
        snapshot = service.overview_snapshot()
        return _render_page(
            request=request,
            templates=templates,
            template_name="overview.html",
            page_key="overview",
            page_title="Dashboard Control Plane",
            page_description="Read-side operator view over execution, runtime guards, identity, incidents, and cognitive overlays.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/overview",
        )

    @router.get("/command-center", name="dashboard_command_center_page")
    def dashboard_command_center_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/overview", status_code=307)

    @router.get("/api/runs", name="dashboard_runs_api")
    def dashboard_runs_api(
        q: str = Query(""),
        status: str = Query(""),
        problem: str = Query(""),
        ingress: str = Query(""),
        running_only: bool = Query(False),
        limit: int = Query(100, ge=1, le=200),
    ) -> JSONResponse:
        return JSONResponse(
            service.runs_snapshot(
                q=q,
                status=status,
                problem=problem,
                ingress=ingress,
                running_only=running_only,
                limit=limit,
            )
        )

    @router.get("/runs", name="dashboard_runs_page")
    def dashboard_runs_page(
        request: Request,
        q: str = Query(""),
        status: str = Query(""),
        problem: str = Query(""),
        ingress: str = Query(""),
        running_only: bool = Query(False),
        limit: int = Query(100, ge=1, le=200),
    ) -> Any:
        snapshot = service.runs_snapshot(
            q=q,
            status=status,
            problem=problem,
            ingress=ingress,
            running_only=running_only,
            limit=limit,
        )
        return _render_page(
            request=request,
            templates=templates,
            template_name="runs.html",
            page_key="runs",
            page_title="Execution Control Plane",
            page_description="What is running, where it is stuck, who depends on it, and whether the problem is job, lane continuity, or team role/checkpoint.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/runs",
        )

    @router.get("/api/runs/{root_run_id:path}", name="dashboard_run_detail_api")
    def dashboard_run_detail_api(root_run_id: str) -> JSONResponse:
        try:
            return JSONResponse(service.run_detail(root_run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "run_not_found", "root_run_id": str(exc)}) from exc

    @router.get("/runs/{root_run_id:path}", name="dashboard_run_detail_page")
    def dashboard_run_detail_page(request: Request, root_run_id: str) -> Any:
        try:
            snapshot = service.run_detail(root_run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "run_not_found", "root_run_id": str(exc)}) from exc
        return _render_page(
            request=request,
            templates=templates,
            template_name="run_detail.html",
            page_key="runs",
            page_title=root_run_id,
            page_description="Unified lineage, timeline, identity links, incidents, and cognitive overlay for one execution chain.",
            snapshot=snapshot,
            json_href=f"/v2/dashboard/api/runs/{root_run_id}",
        )

    @router.get("/api/runtime", name="dashboard_runtime_api")
    def dashboard_runtime_api() -> JSONResponse:
        return JSONResponse(service.runtime_snapshot())

    @router.get("/runtime", name="dashboard_runtime_page")
    def dashboard_runtime_page(request: Request) -> Any:
        snapshot = service.runtime_snapshot()
        return _render_page(
            request=request,
            templates=templates,
            template_name="runtime.html",
            page_key="runtime",
            page_title="Runtime And Safety Control Plane",
            page_description="System health, guard blocks, watchdog alarms, and whether failures are local or broad.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/runtime",
        )

    @router.get("/api/identity", name="dashboard_identity_api")
    def dashboard_identity_api(limit: int = Query(50, ge=1, le=200)) -> JSONResponse:
        return JSONResponse(service.identity_snapshot(limit=limit))

    @router.get("/identity", name="dashboard_identity_page")
    def dashboard_identity_page(request: Request, limit: int = Query(50, ge=1, le=200)) -> Any:
        snapshot = service.identity_snapshot(limit=limit)
        return _render_page(
            request=request,
            templates=templates,
            template_name="identity.html",
            page_key="identity",
            page_title="Identity And Ingress Control Plane",
            page_description="Stable mapping across tenant, team, user, ingress, trace, run, job, lane, issue, and checkpoint identities.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/identity",
        )

    @router.get("/api/incidents", name="dashboard_incidents_api")
    def dashboard_incidents_api(
        q: str = Query(""),
        status: str = Query(""),
        incident_type: str = Query(""),
        limit: int = Query(100, ge=1, le=200),
    ) -> JSONResponse:
        return JSONResponse(
            service.incident_snapshot(
                q=q,
                status=status,
                incident_type=incident_type,
                limit=limit,
            )
        )

    @router.get("/incidents", name="dashboard_incidents_page")
    def dashboard_incidents_page(
        request: Request,
        q: str = Query(""),
        status: str = Query(""),
        incident_type: str = Query(""),
        limit: int = Query(100, ge=1, le=200),
    ) -> Any:
        snapshot = service.incident_snapshot(
            q=q,
            status=status,
            incident_type=incident_type,
            limit=limit,
        )
        return _render_page(
            request=request,
            templates=templates,
            template_name="incidents.html",
            page_key="incidents",
            page_title="Incident And Client View",
            page_description="Operator-first issue surface, still anchored back to execution lineage and identity maps.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/incidents",
        )

    @router.get("/api/cognitive", name="dashboard_cognitive_api")
    def dashboard_cognitive_api() -> JSONResponse:
        return JSONResponse(service.cognitive_snapshot())

    @router.get("/api/evomap", name="dashboard_evomap_api")
    def dashboard_evomap_api() -> JSONResponse:
        return JSONResponse(_proxy_dashboard_snapshot(path="evomap", fallback=service.cognitive_snapshot))

    @router.get("/cognitive", name="dashboard_cognitive_page")
    def dashboard_cognitive_page(request: Request) -> Any:
        snapshot = service.cognitive_snapshot()
        return _render_page(
            request=request,
            templates=templates,
            template_name="cognitive.html",
            page_key="cognitive",
            page_title="Cognitive Control Plane",
            page_description="Explainability and context overlays from OpenMind and EvoMap, kept off the execution hot path.",
            snapshot=snapshot,
            json_href="/v2/dashboard/api/cognitive",
        )

    @router.get("/evomap", name="dashboard_evomap_page")
    def dashboard_evomap_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/cognitive", status_code=307)

    @router.get("/api/graph", name="dashboard_graph_api")
    def dashboard_graph_api() -> JSONResponse:
        return JSONResponse(service.graph_snapshot())

    @router.get("/api/graph/lineage", name="dashboard_graph_lineage_api")
    def dashboard_graph_lineage_api(
        root_run_id: str = Query(""),
        limit: int = Query(12, ge=1, le=50),
    ) -> JSONResponse:
        return JSONResponse(service.graph_lineage(root_run_id=root_run_id, limit=limit))

    @router.get("/api/graph/run/{root_run_id}", name="dashboard_graph_run_api")
    def dashboard_graph_run_api(root_run_id: str) -> JSONResponse:
        return JSONResponse(service.graph_lineage(root_run_id=root_run_id, limit=12))

    @router.get("/api/graph/neighborhood", name="dashboard_graph_neighborhood_api")
    def dashboard_graph_neighborhood_api(
        id: str = Query(..., alias="id"),
        depth: int = Query(2, ge=1, le=3),
        limit_roots: int = Query(6, ge=1, le=12),
    ) -> JSONResponse:
        return JSONResponse(service.graph_neighborhood(id, depth=depth, limit_roots=limit_roots))

    @router.get("/graph", name="dashboard_graph_page")
    def dashboard_graph_page(request: Request) -> Any:
        return _graph_page(request, json_href="/v2/dashboard/api/graph")

    @router.get("/finagent", name="dashboard_finagent_page")
    def dashboard_finagent_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/investor", status_code=307)
    # Compatibility aliases for the earlier prototype navigation.
    @router.get("/api/tasks", name="dashboard_tasks_api")
    def dashboard_tasks_api(
        q: str = Query(""),
        status: str = Query(""),
        limit: int = Query(100, ge=1, le=200),
        attention_only: bool = Query(False),
    ) -> JSONResponse:
        return JSONResponse(
            service.tasks_snapshot(
                search=q,
                status=status,
                attention_only=attention_only,
                limit=limit,
            )
        )

    @router.get("/tasks", name="dashboard_tasks_page")
    def dashboard_tasks_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/runs", status_code=307)

    @router.get("/api/tasks/{task_id}", name="dashboard_task_detail_api")
    def dashboard_task_detail_api(task_id: str) -> JSONResponse:
        try:
            return JSONResponse(service.task_detail(task_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": str(exc)}) from exc

    @router.get("/tasks/{task_id}", name="dashboard_task_detail_page")
    def dashboard_task_detail_page(task_id: str) -> RedirectResponse:
        try:
            detail = service.task_detail(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": str(exc)}) from exc
        return RedirectResponse(url=f"/v2/dashboard/runs/{detail['run']['root_run_id']}", status_code=307)

    @router.get("/api/openmind", name="dashboard_openmind_api")
    def dashboard_openmind_api() -> JSONResponse:
        return JSONResponse(service.openmind_snapshot())

    @router.get("/openmind", name="dashboard_openmind_page")
    def dashboard_openmind_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/cognitive", status_code=307)

    @router.get("/api/openclaw", name="dashboard_openclaw_api")
    def dashboard_openclaw_api() -> JSONResponse:
        return JSONResponse(service.openclaw_snapshot())

    @router.get("/openclaw", name="dashboard_openclaw_page")
    def dashboard_openclaw_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/runtime", status_code=307)

    @router.get("/api/lineage", name="dashboard_lineage_api")
    def dashboard_lineage_api(limit: int = Query(50, ge=1, le=200)) -> JSONResponse:
        return JSONResponse(service.lineage_snapshot(limit=limit))

    @router.get("/lineage", name="dashboard_lineage_page")
    def dashboard_lineage_page() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/identity", status_code=307)

    return router
