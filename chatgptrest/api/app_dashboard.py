from __future__ import annotations

import argparse
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from chatgptrest.api.routes_dashboard import make_dashboard_router
from chatgptrest.core.config import AppConfig, load_config
from chatgptrest.dashboard import DashboardService


def _is_auth_exempt_path(path: str) -> bool:
    path_str = str(path or "")
    return path_str in {"/", "/health", "/healthz", "/livez", "/readyz"}


def _collect_route_inventory(app: FastAPI) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for route in app.routes:
        methods = sorted(
            method
            for method in getattr(route, "methods", set()) or set()
            if method not in {"HEAD", "OPTIONS"}
        )
        inventory.append(
            {
                "path": str(getattr(route, "path", "")),
                "name": str(getattr(route, "name", "")),
                "methods": methods,
            }
        )
    inventory.sort(key=lambda item: (item["path"], item["name"], ",".join(item["methods"])))
    return inventory


def _record_router_status(
    startup_manifest: dict[str, Any],
    *,
    name: str,
    loaded: bool,
    error: Exception | None = None,
) -> None:
    entry = {"name": str(name), "loaded": bool(loaded)}
    if error is not None:
        entry["error_type"] = type(error).__name__
        entry["error"] = str(error)[:500]
    startup_manifest.setdefault("routers", []).append(entry)
    if error is not None:
        startup_manifest.setdefault("router_load_errors", []).append(dict(entry))


def _install_auth_middleware(app: FastAPI, cfg: AppConfig) -> None:
    if not cfg.api_token and not cfg.ops_token:
        logging.getLogger(__name__).warning(
            "dashboard app running without auth tokens; set CHATGPTREST_API_TOKEN or CHATGPTREST_OPS_TOKEN for production"
        )
        return

    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next):  # type: ignore[no-redef]
        path = str(request.url.path or "")
        if _is_auth_exempt_path(path):
            return await call_next(request)
        auth = (request.headers.get("authorization") or "").strip()
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        candidates = [cfg.api_token, cfg.ops_token]
        candidates = [candidate for candidate in candidates if candidate]
        if candidates and (not token or not any(hmac.compare_digest(token, candidate) for candidate in candidates)):
            return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
        return await call_next(request)


def create_app() -> FastAPI:
    cfg = load_config()
    service = DashboardService(cfg)
    startup_manifest: dict[str, Any] = {
        "status": "starting",
        "routers": [],
        "router_load_errors": [],
        "route_inventory": [],
        "route_count": 0,
    }

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        try:
            service.refresh_control_plane(force=True)
            service.control_plane.start_background_refresh()
            startup_manifest["background_refresh"] = "started"
            yield
        finally:
            service.control_plane.stop_background_refresh()
            startup_manifest["background_refresh"] = "stopped"

    app = FastAPI(title="ChatgptREST Dashboard", version="0.1.0", lifespan=_lifespan)
    app.state.startup_manifest = startup_manifest
    app.state.dashboard_service = service
    _install_auth_middleware(app, cfg)

    @app.get("/", name="dashboard_app_root")
    def dashboard_app_root() -> RedirectResponse:
        return RedirectResponse(url="/v2/dashboard/overview", status_code=307)

    @app.get("/health", name="dashboard_health")
    @app.get("/healthz", name="dashboard_healthz")
    @app.get("/livez", name="dashboard_livez")
    @app.get("/readyz", name="dashboard_readyz")
    def dashboard_health() -> JSONResponse:
        meta = service.control_plane.get_meta()
        return JSONResponse(
            {
                "ok": True,
                "service": "chatgptrest-dashboard",
                "startup": startup_manifest.get("status"),
                "refresh_status": meta.get("refresh_status", "unknown"),
                "refreshed_at": meta.get("refreshed_at", "0"),
                "root_count": meta.get("root_count", "0"),
                "read_db_path": str(service.control_plane.config.read_db_path),
            }
        )

    try:
        app.include_router(make_dashboard_router(cfg, service=service))
        _record_router_status(startup_manifest, name="dashboard_v2", loaded=True)
    except Exception as exc:  # pragma: no cover - startup failure path
        _record_router_status(startup_manifest, name="dashboard_v2", loaded=False, error=exc)
        raise

    startup_manifest["route_inventory"] = _collect_route_inventory(app)
    startup_manifest["route_count"] = len(startup_manifest["route_inventory"])
    startup_manifest["status"] = "ready" if not startup_manifest["router_load_errors"] else "router_load_failed"
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    uvicorn.run("chatgptrest.api.app_dashboard:create_app", host=args.host, port=args.port, factory=True)


if __name__ == "__main__":
    main()
