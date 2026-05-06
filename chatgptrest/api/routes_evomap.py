"""EvoMap Dashboard API — REST endpoints for EvoMap signals.

Provides:
  - GET /v2/evomap/signals: Recent signals (filter by type, time)
  - GET /v2/evomap/trends: Daily aggregated trends
  - GET /v2/evomap/config: Current config parameters
  - POST /v2/evomap/config: Update config parameters (requires API Key)
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chatgptrest.evomap.paths import ensure_sqlite_parent_dir, resolve_evomap_db_path

logger = logging.getLogger(__name__)


class ConfigUpdate(BaseModel):
    """EvoMap configuration update request."""
    signal_retention_days: int | None = None
    trend_aggregation_window: int | None = None
    alert_threshold_route_shift: float | None = None


# Module-level config (in production, persist to file/DB)
_config: dict[str, Any] = {
    "signal_retention_days": 30,
    "trend_aggregation_window": 7,
    "alert_threshold_route_shift": 0.3,
}


_observer_cache: dict[str, Any] = {}  # singleton cache


def make_evomap_router(cfg: Any = None) -> APIRouter:
    """Create the EvoMap dashboard router."""
    router = APIRouter(prefix="/v2/evomap", tags=["evomap"])

    def _get_observer(request: Any = None):
        """Get or create the EvoMapObserver singleton.

        Phase-2 fix: uses FastAPI app.state for shared observer instead of
        importing closure-local _state from routes_advisor_v3.
        Falls back to own singleton if app.state not available.
        """
        from chatgptrest.evomap.observer import EvoMapObserver

        # 1. Try to reuse observer from FastAPI app.state (set by Advisor v3)
        try:
            if request and hasattr(request, "app"):
                shared = getattr(request.app.state, "evomap_observer", None)
                if isinstance(shared, EvoMapObserver):
                    logger.debug("evomap dashboard: reusing app.state observer")
                    return shared
        except Exception:
            pass

        # 2. Fallback: own singleton keyed by db path.
        evo_db = resolve_evomap_db_path()
        cached = _observer_cache.get("instance")
        if cached is not None and getattr(cached, "db_path", None) == evo_db:
            return cached
        logger.info("evomap dashboard: creating own observer at %s", evo_db)
        ensure_sqlite_parent_dir(evo_db)
        obs = EvoMapObserver(db_path=evo_db)
        _observer_cache["instance"] = obs
        return obs

    @router.get("/signals")
    def get_signals(
        request: Request,
        since: str = Query("", description="ISO timestamp, e.g. 2026-01-01T00:00:00Z"),
        until: str = Query("", description="ISO timestamp"),
        signal_type: str = Query("", description="Filter by signal type"),
        limit: int = Query(100, ge=1, le=1000),
    ) -> JSONResponse:
        """Get recent signals with optional filters."""
        observer = _get_observer(request)
        signals = observer.query(
            since=since,
            until=until,
            signal_type=signal_type,
            limit=limit,
        )
        return JSONResponse({
            "ok": True,
            "count": len(signals),
            "signals": [
                {
                    "signal_id": s.signal_id,
                    "trace_id": s.trace_id,
                    "type": s.signal_type,
                    "value": s.data.get("value"),
                    "timestamp": s.timestamp,
                }
                for s in signals
            ],
        })

    @router.get("/trends")
    def get_trends(
        request: Request,
        days: int = Query(7, ge=1, le=90, description="Number of days to aggregate"),
    ) -> JSONResponse:
        """Get daily aggregated trend data."""
        from datetime import datetime, timedelta, timezone

        observer = _get_observer(request)
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days)).isoformat()

        signals = observer.query(since=since, limit=10000)

        # Aggregate by day and signal_type
        daily: dict[str, dict[str, int]] = {}
        for s in signals:
            # Extract date part from timestamp
            date_key = s.timestamp[:10] if s.timestamp else now.date().isoformat()
            if date_key not in daily:
                daily[date_key] = {}
            daily[date_key][s.signal_type] = daily[date_key].get(s.signal_type, 0) + 1

        return JSONResponse({
            "ok": True,
            "days": days,
            "trends": [
                {"date": date, "counts": counts}
                for date, counts in sorted(daily.items())
            ],
        })

    @router.get("/config")
    def get_config() -> JSONResponse:
        """Get current EvoMap configuration."""
        return JSONResponse({
            "ok": True,
            "config": _config.copy(),
        })

    @router.post("/config")
    def update_config(
        config: ConfigUpdate,
        authorization: str = Header("", alias="Authorization"),
    ) -> JSONResponse:
        """Update EvoMap configuration (requires Bearer token)."""
        expected_key = getattr(cfg, "api_token", None) if cfg else None

        # Extract Bearer token
        token = ""
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()

        # If API key is configured, require it (timing-safe comparison)
        if expected_key and (not token or not hmac.compare_digest(token, expected_key)):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing Bearer token", "hint": "Set Authorization: Bearer <token> header"},
            )

        # Update config from request
        if config.signal_retention_days is not None:
            _config["signal_retention_days"] = config.signal_retention_days
        if config.trend_aggregation_window is not None:
            _config["trend_aggregation_window"] = config.trend_aggregation_window
        if config.alert_threshold_route_shift is not None:
            _config["alert_threshold_route_shift"] = config.alert_threshold_route_shift

        return JSONResponse({
            "ok": True,
            "config": _config.copy(),
        })

    return router
