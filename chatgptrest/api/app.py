from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from chatgptrest.api.client_ip import get_client_ip
from chatgptrest.api.routes_jobs import make_router
from chatgptrest.api.routes_issues import make_issues_router
from chatgptrest.api.routes_metrics import make_metrics_router
from chatgptrest.api.routes_ops import make_ops_router
from chatgptrest.api.routes_evomap import make_evomap_router
from chatgptrest.api.routes_cognitive import make_cognitive_router
from chatgptrest.api.routes_dashboard import make_dashboard_router
from chatgptrest.core.config import AppConfig, load_config


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
    return (not path_str.startswith("/v1/")) or path_str in {
        "/health",
        "/healthz",
        "/livez",
        "/readyz",
        "/v1/health/runtime-contract",
    }


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


_AUDITED_REJECTION_STATUS_CODES = {400, 401, 403, 409, 429}
_AUDITED_REJECTION_PATH_PREFIXES = ("/v1/jobs", "/v1/ops", "/v1/issues")
_TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _compact_audit_text(value: Any, *, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _safe_audit_detail(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return _compact_audit_text(value, limit=240)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s.lower() in {"authorization", "cookie", "set-cookie", "api_token", "ops_token", "token"}:
                out[key_s] = "<redacted>"
                continue
            out[key_s] = _safe_audit_detail(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_safe_audit_detail(item, depth=depth + 1) for item in list(value)[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _compact_audit_text(value, limit=1000)
        return value
    return _compact_audit_text(value, limit=500)


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_ip(value: Any) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(str(value or "").strip())
    except Exception:
        return None


def _is_tunnel_or_private_addr(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved:
        return True
    if isinstance(addr, ipaddress.IPv4Address) and addr in _TAILSCALE_CGNAT:
        return True
    return False


def _cidr_list_contains(ip_text: str, raw_cidrs: str) -> bool:
    addr = _parse_ip(ip_text)
    if addr is None:
        return False
    for raw in str(raw_cidrs or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            if addr in ipaddress.ip_network(raw, strict=False):
                return True
        except Exception:
            continue
    return False


def _ingress_policy_client_ip(request: Request) -> str:
    direct = _parse_ip(request.client.host if request.client else "")
    x_real_ip = _parse_ip(request.headers.get("x-real-ip"))
    xff_parts = [part.strip() for part in str(request.headers.get("x-forwarded-for") or "").split(",") if part.strip()]

    if direct is not None and _is_tunnel_or_private_addr(direct):
        if x_real_ip is not None:
            return str(x_real_ip)
        for item in reversed(xff_parts):
            candidate = _parse_ip(item)
            if candidate is not None:
                return str(candidate)
    return get_client_ip(request)


def _public_ingress_rejection_detail(request: Request) -> dict[str, Any] | None:
    if not _truthy_env("CHATGPTREST_REJECT_PUBLIC_INGRESS", True):
        return None
    client_ip = _ingress_policy_client_ip(request)
    if _cidr_list_contains(client_ip, os.environ.get("CHATGPTREST_PUBLIC_INGRESS_ALLOW_CIDRS", "")):
        return None
    addr = _parse_ip(client_ip)
    if addr is None or not addr.is_global:
        return None
    return {
        "error": "public_ingress_blocked",
        "error_type": "PublicIngressBlocked",
        "reason": "chatgptrest_is_tunnel_first",
        "client_ip": str(addr),
        "safe_next_action": (
            "Use SSH/Tailscale tunnel access to 127.0.0.1:18711 or 127.0.0.1:18712/mcp; "
            "do not expose ChatgptREST over public HTTP ingress."
        ),
    }


def _record_http_rejection(
    *,
    cfg: AppConfig,
    request: Request,
    status_code: int,
    detail: Any,
    source: str,
) -> None:
    path = str(request.url.path or "")
    if int(status_code) not in _AUDITED_REJECTION_STATUS_CODES:
        return
    if str(source or "") != "public_ingress_middleware" and not any(
        path.startswith(prefix) for prefix in _AUDITED_REJECTION_PATH_PREFIXES
    ):
        return
    try:
        ts = time.time()
        audit_dir = Path(cfg.artifacts_dir) / "monitor" / "api_rejections"
        audit_dir.mkdir(parents=True, exist_ok=True)
        headers = request.headers
        record = {
            "ts": ts,
            "status_code": int(status_code),
            "source": str(source or "http_rejection"),
            "method": str(request.method or ""),
            "path": path,
            "client_ip": get_client_ip(request),
            "x_client_name": headers.get("x-client-name"),
            "x_client_instance": headers.get("x-client-instance"),
            "x_request_id": headers.get("x-request-id"),
            "idempotency_key": headers.get("idempotency-key"),
            "user_agent": _compact_audit_text(headers.get("user-agent"), limit=240),
            "authorization_present": bool(headers.get("authorization")),
            "detail": _safe_audit_detail(detail),
        }
        audit_path = audit_dir / f"{time.strftime('%Y%m%d', time.localtime(ts))}.jsonl"
        with audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        logging.getLogger(__name__).debug("failed to record http rejection audit", exc_info=True)


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
                _record_http_rejection(
                    cfg=cfg,
                    request=request,
                    status_code=401,
                    detail={"ok": False, "error": "unauthorized", "reason": "missing_or_invalid_bearer_token"},
                    source="auth_middleware",
                )
                return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
            return await call_next(request)

    @app.middleware("http")
    async def _public_ingress_middleware(request: Request, call_next):  # type: ignore[no-redef]
        detail = _public_ingress_rejection_detail(request)
        if detail is not None:
            _record_http_rejection(
                cfg=cfg,
                request=request,
                status_code=403,
                detail=detail,
                source="public_ingress_middleware",
            )
            return JSONResponse(status_code=403, content={"detail": detail})
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_audit_handler(request: Request, exc: StarletteHTTPException):  # type: ignore[no-untyped-def]
        _record_http_rejection(
            cfg=cfg,
            request=request,
            status_code=int(exc.status_code),
            detail=getattr(exc, "detail", None),
            source="http_exception",
        )
        return await http_exception_handler(request, exc)

    app.include_router(make_router(cfg))
    _record_router_status(startup_manifest, name="jobs_v1", loaded=True, core=True)
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

    startup_manifest["retired_surfaces"] = ["/v3/agent/*"]
    startup_manifest["retired_surfaces"].extend(["/v1/advisor/*", "/v2/advisor/*", "/v1/advisor/consult*"])

    # Task Harness Runtime
    try:
        from chatgptrest.task_runtime.api_routes import router as task_runtime_router
        app.include_router(task_runtime_router)
        _record_router_status(startup_manifest, name="task_runtime_v1", loaded=True, core=False)
    except Exception as e:
        _record_router_status(startup_manifest, name="task_runtime_v1", loaded=False, core=False, error=e)
        logging.getLogger(__name__).warning(
            "task runtime router not loaded: %s", e, exc_info=True
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
