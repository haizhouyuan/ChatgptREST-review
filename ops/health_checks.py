"""Public health check helpers for ChatgptREST.

Thin, stable API for basic service liveness probing and runtime resolution.
Used by ``scripts/chatgptrest_bootstrap.py`` (agent bootstrap) and
``ops/health_probe.py`` (deep operational diagnosis).

These functions do basic liveness checks and registry resolution ONLY.
For full operational diagnosis (stuck jobs, lease semantics, timer health,
MCP ingress contract validation), use ``python ops/health_probe.py --json``.

Do NOT add mutation logic or domain-specific stuck-job classification here.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# HTTP status codes that confirm service liveness without a 2xx response.
# 404 is only treated as "alive" for root probes (for example bare MCP `/`),
# not for service-specific health endpoints such as `/v2/advisor/health`.
_DEFAULT_LIVENESS_HTTP_CODES = {401, 403, 405}

_CRITICAL_MAINTENANCE_TIMERS = (
    "chatgptrest-health-probe.timer",
    "chatgptrest-backlog-janitor.timer",
    "chatgptrest-ui-canary.timer",
)


def _http_status_counts_as_alive(url: str, status_code: int, *, alive_statuses: set[int] | None = None) -> bool:
    if alive_statuses is not None:
        return status_code in alive_statuses
    if status_code in _DEFAULT_LIVENESS_HTTP_CODES:
        return True
    if status_code != 404:
        return False
    path = urllib.parse.urlparse(url).path.strip()
    return path in {"", "/"}


def check_http(
    label: str,
    url: str,
    *,
    timeout: int = 5,
    alive_statuses: set[int] | None = None,
) -> dict[str, Any]:
    """Check HTTP endpoint liveness.

    Specific 4xx codes can confirm liveness when they match the probe shape
    (for example auth-required endpoints or a bare MCP root that returns 404).
    Service-specific health endpoints returning 404 are treated as unhealthy by
    default unless the caller explicitly opts in via ``alive_statuses``.
    """
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            return {"check": label, "ok": True, "status": resp.status, "body_preview": body[:200]}
    except urllib.error.HTTPError as exc:
        if _http_status_counts_as_alive(url, exc.code, alive_statuses=alive_statuses):
            return {"check": label, "ok": True, "status": exc.code, "note": f"alive (HTTP {exc.code})"}
        # 5xx = service is listening but unhealthy
        return {"check": label, "ok": False, "status": exc.code, "note": f"unhealthy (HTTP {exc.code})"}
    except Exception as exc:
        return {"check": label, "ok": False, "error": str(exc)[:200]}


def check_db(label: str, db_path: str) -> dict[str, Any]:
    """Check SQLite DB accessibility (read-only)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        conn.close()
        return {"check": label, "ok": True, "tables": tables, "path": db_path}
    except Exception as exc:
        return {"check": label, "ok": False, "error": str(exc)[:200]}


def check_tcp(label: str, host: str, port: int, *, timeout: int = 3) -> dict[str, Any]:
    """Check if a TCP port is reachable (e.g. Chrome CDP on 9222)."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {"check": label, "ok": True, "host": host, "port": port}
    except Exception as exc:
        return {"check": label, "ok": False, "host": host, "port": port, "error": str(exc)[:200]}


def check_systemd_timers(labels: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Check if critical systemd user timers are active."""
    timer_names = labels or _CRITICAL_MAINTENANCE_TIMERS
    results: list[dict[str, Any]] = []
    for timer in timer_names:
        try:
            proc = subprocess.run(
                ["systemctl", "--user", "is-active", timer],
                capture_output=True, timeout=5, text=True,
            )
            active = proc.stdout.strip() == "active"
            results.append({"timer": timer, "active": active, "status": proc.stdout.strip()})
        except Exception as exc:
            results.append({"timer": timer, "active": False, "error": str(exc)[:120]})
    all_active = all(r["active"] for r in results)
    return {"check": "maintenance_timers", "ok": all_active, "timers": results}


def resolve_runtime_registry() -> dict[str, Any]:
    """Load and resolve runtime_registry.yaml.

    Returns:
        {
            "services": [...],
            "databases": [...]
        }
    """
    registry_path = REPO_ROOT / "ops" / "registries" / "runtime_registry.yaml"
    if not registry_path.exists():
        return {"services": [], "databases": [], "error": "runtime_registry.yaml not found"}

    with open(registry_path) as f:
        data = yaml.safe_load(f)

    # Resolve database paths
    for db in data.get("databases", []):
        if "env_var" in db and db["env_var"] in os.environ:
            db["resolved_path"] = os.environ[db["env_var"]]
        elif "default_path" in db:
            default = db["default_path"]
            if default.startswith("~"):
                db["resolved_path"] = str(Path(default).expanduser())
            else:
                db["resolved_path"] = str(REPO_ROOT / default)
        else:
            db["resolved_path"] = None

    return data


def summarize_runtime_quick() -> dict[str, Any]:
    """Quick runtime summary — repo identity, API/MCP/jobdb liveness, public MCP ingress.

    This is the 'quick' mode for bootstrap. Does NOT include:
    - Stuck job analysis
    - Maintenance timer checks
    - Viewer/chrome diagnostics
    - Deep advisor/dashboard checks

    For those, use health_probe.py --json (deep mode).
    """
    registry = resolve_runtime_registry()

    # Check services
    service_checks = []
    for svc in registry.get("services", []):
        if "liveness_url" in svc:
            alive_statuses = None
            if isinstance(svc.get("liveness_http_codes"), list):
                alive_statuses = {
                    int(code)
                    for code in list(svc.get("liveness_http_codes") or [])
                    if isinstance(code, int) or str(code).isdigit()
                }
            result = check_http(svc["name"], svc["liveness_url"], alive_statuses=alive_statuses)
            service_checks.append({
                "name": svc["name"],
                "ok": result["ok"],
                "port": svc.get("port"),
                "agent_entry_url": svc.get("agent_entry_url"),
                "required": svc.get("required", False),
            })

    # Check databases
    db_checks = []
    for db in registry.get("databases", []):
        if db.get("resolved_path"):
            result = check_db(db["name"], db["resolved_path"])
            db_checks.append({
                "name": db["name"],
                "ok": result["ok"],
                "path": db["resolved_path"],
                "required": db.get("required", False),
            })

    # Extract public MCP ingress summary
    public_mcp = next((s for s in service_checks if s["name"] == "public_mcp"), None)

    return {
        "mode": "quick",
        "source": "quick_summary",
        "services": service_checks,
        "databases": db_checks,
        "public_mcp_ingress": {
            "ok": public_mcp["ok"] if public_mcp else False,
            "agent_entry_url": public_mcp.get("agent_entry_url") if public_mcp else None,
        } if public_mcp else None,
        "maintenance_timers": None,
    }
