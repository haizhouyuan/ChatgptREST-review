from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from chatgptrest.core.config import load_config
from chatgptrest.api.routes_jobs import make_router
from chatgptrest.api.routes_advisor import make_advisor_router
from chatgptrest.api.routes_consult import make_consult_router
from chatgptrest.api.routes_issues import make_issues_router
from chatgptrest.api.routes_metrics import make_metrics_router
from chatgptrest.api.routes_ops import make_ops_router
from chatgptrest.api.routes_evomap import make_evomap_router
from chatgptrest.api.routes_cognitive import make_cognitive_router
from chatgptrest.api.routes_dashboard import make_dashboard_router


_cc_sessiond_client = None


@asynccontextmanager
async def _cc_sessiond_lifespan(app: FastAPI):
    global _cc_sessiond_client
    from chatgptrest.api.routes_cc_sessiond import get_cc_sessiond_client
    
    try:
        _cc_sessiond_client = get_cc_sessiond_client()
        if _cc_sessiond_client:
            await _cc_sessiond_client.start()
            logging.getLogger(__name__).info("cc-sessiond scheduler started")
        yield
    finally:
        if _cc_sessiond_client:
            await _cc_sessiond_client.stop()
            logging.getLogger(__name__).info("cc-sessiond scheduler stopped")


def _is_global_bearer_auth_exempt_path(path: str) -> bool:
    path_str = str(path or "")
    return (not path_str.startswith("/v1/")) or path_str in {"/health", "/healthz", "/livez", "/readyz"}


def _record_router_status(
    startup_manifest: dict[str, Any],
    *,
    name: str,
    loaded: bool,
    core: bool,
    error: Exception | None = None,
) -> None:
    entry = {
        "name": str(name),
        "loaded": bool(loaded),
        "core": bool(core),
    }
    if error is not None:
        entry["error_type"] = type(error).__name__
        entry["error"] = str(error)[:500]
    startup_manifest.setdefault("routers", []).append(entry)
    if error is not None and core:
        startup_manifest.setdefault("router_load_errors", []).append(dict(entry))


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


def create_app() -> FastAPI:
    cfg = load_config()
    app = FastAPI(title="ChatgptREST", version="0.1.0", lifespan=_cc_sessiond_lifespan)
    startup_manifest: dict[str, Any] = {
        "status": "starting",
        "routers": [],
        "router_load_errors": [],
        "route_inventory": [],
        "route_count": 0,
    }
    app.state.startup_manifest = startup_manifest

    logger = logging.getLogger(__name__)
    if not cfg.api_token and not cfg.ops_token:
        logger.warning(
            "⚠️  SECURITY: No auth tokens configured (CHATGPTREST_API_TOKEN / "
            "CHATGPTREST_OPS_TOKEN). API is running WITHOUT authentication. "
            "Set at least one token for production deployments."
        )

    if cfg.api_token or cfg.ops_token:

        @app.middleware("http")
        async def _auth_middleware(request: Request, call_next):  # type: ignore[no-redef]
            path = str(request.url.path or "")
            if _is_global_bearer_auth_exempt_path(path):
                return await call_next(request)
            auth = (request.headers.get("authorization") or "").strip()
            token = ""
            if auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1].strip()
            is_ops = path.startswith("/v1/ops/")

            if is_ops:
                candidates = [cfg.ops_token or cfg.api_token]
            else:
                candidates = [cfg.api_token or cfg.ops_token]
                if path.startswith("/v1/jobs") and cfg.ops_token:
                    candidates.append(cfg.ops_token)
            candidates = [c for c in candidates if c]

            if candidates and (not token or not any(hmac.compare_digest(token, expected) for expected in candidates)):
                return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
            return await call_next(request)

    app.include_router(make_router(cfg))
    _record_router_status(startup_manifest, name="jobs_v1", loaded=True, core=True)
    app.include_router(make_advisor_router(cfg))
    _record_router_status(startup_manifest, name="advisor_v1", loaded=True, core=True)
    app.include_router(make_consult_router(cfg))
    _record_router_status(startup_manifest, name="consult_v1", loaded=True, core=True)
    app.include_router(make_issues_router(cfg))
    _record_router_status(startup_manifest, name="issues_v1", loaded=True, core=True)
    app.include_router(make_metrics_router(cfg))
    _record_router_status(startup_manifest, name="metrics_v1", loaded=True, core=True)
    app.include_router(make_ops_router(cfg))
    _record_router_status(startup_manifest, name="ops_v1", loaded=True, core=True)
    app.include_router(make_evomap_router(cfg))
    _record_router_status(startup_manifest, name="evomap_v1", loaded=True, core=True)
    app.include_router(make_cognitive_router())
    _record_router_status(startup_manifest, name="cognitive_v2", loaded=True, core=True)
    app.include_router(make_dashboard_router(cfg))
    _record_router_status(startup_manifest, name="dashboard_v2", loaded=True, core=True)

    # cc-sessiond
    try:
        from chatgptrest.api.routes_cc_sessiond import make_cc_sessiond_router
        app.include_router(make_cc_sessiond_router())
        _record_router_status(startup_manifest, name="cc_sessiond_v1", loaded=True, core=False)
    except Exception as e:
        _record_router_status(startup_manifest, name="cc_sessiond_v1", loaded=False, core=False, error=e)
        logging.getLogger(__name__).warning(
            "cc-sessiond router not loaded: %s", e, exc_info=True
        )

    # v3 LangGraph-based advisor
    try:
        from chatgptrest.api.routes_advisor_v3 import make_v3_advisor_router
        app.include_router(make_v3_advisor_router())
        _record_router_status(startup_manifest, name="advisor_v3", loaded=True, core=True)
    except Exception as e:
        _record_router_status(startup_manifest, name="advisor_v3", loaded=False, core=True, error=e)
        logging.getLogger(__name__).warning(
            "v3 advisor router not loaded: %s", e, exc_info=True
        )

    # v3 public agent facade
    try:
        from chatgptrest.api.routes_agent_v3 import make_v3_agent_router
        app.include_router(make_v3_agent_router())
        _record_router_status(startup_manifest, name="agent_v3", loaded=True, core=True)
    except Exception as e:
        _record_router_status(startup_manifest, name="agent_v3", loaded=False, core=True, error=e)
        logging.getLogger(__name__).warning(
            "v3 agent router not loaded: %s", e, exc_info=True
        )

    startup_manifest["route_inventory"] = _collect_route_inventory(app)
    startup_manifest["route_count"] = len(startup_manifest["route_inventory"])
    startup_manifest["status"] = "ready" if not startup_manifest["router_load_errors"] else "router_load_failed"

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18711)
    args = parser.parse_args()
    uvicorn.run("chatgptrest.api.app:create_app", host=args.host, port=args.port, factory=True)


if __name__ == "__main__":
    main()
