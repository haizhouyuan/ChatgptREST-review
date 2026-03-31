"""Runtime snapshot generation — quick and deep modes."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "ops"))

from health_checks import summarize_runtime_quick  # noqa: E402


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def generate_runtime_snapshot(mode: Literal["quick", "deep"] = "quick") -> dict[str, Any]:
    """Generate runtime snapshot.

    Args:
        mode: "quick" for basic liveness checks, "deep" for full health_probe output

    Returns:
        Runtime snapshot dict with mode, timestamp, services, databases, etc.
    """
    if mode == "quick":
        snapshot = summarize_runtime_quick()
        snapshot["timestamp"] = _now_iso()
        return snapshot

    # Deep mode: run health_probe.py --json
    snapshot = summarize_runtime_quick()
    snapshot["mode"] = "deep"
    snapshot["timestamp"] = _now_iso()
    try:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "ops" / "health_probe.py"), "--json"],
            capture_output=True,
            timeout=30,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            deep_snapshot = json.loads(proc.stdout)
            snapshot["timestamp"] = deep_snapshot.get("ts", snapshot["timestamp"])
            snapshot["source"] = "health_probe"
            snapshot["all_ok"] = deep_snapshot.get("all_ok", False)
            snapshot["checks"] = list(deep_snapshot.get("checks") or [])
            snapshot["public_mcp_ingress"] = _extract_public_mcp_ingress(deep_snapshot) or snapshot.get("public_mcp_ingress")
            snapshot["maintenance_timers"] = _extract_maintenance_timers(deep_snapshot)
            snapshot["error"] = None
            snapshot["stderr"] = None
            return snapshot
        snapshot["source"] = "health_probe"
        snapshot["all_ok"] = False
        snapshot["checks"] = []
        snapshot["maintenance_timers"] = None
        snapshot["error"] = "health_probe.py failed"
        snapshot["stderr"] = proc.stderr[:500] if proc.stderr else None
        return snapshot
    except Exception as exc:
        snapshot["source"] = "health_probe"
        snapshot["all_ok"] = False
        snapshot["checks"] = []
        snapshot["maintenance_timers"] = None
        snapshot["error"] = str(exc)[:200]
        snapshot["stderr"] = None
        return snapshot


def _extract_public_mcp_ingress(deep_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Extract public MCP ingress contract from deep snapshot."""
    for check in deep_snapshot.get("checks", []):
        if check.get("check") == "public_mcp_ingress_contract":
            return {
                "ok": check.get("ok", False),
                "num_failed": check.get("num_failed", 0),
                "failed_paths": check.get("failed_paths", []),
                "fix_hint": check.get("fix_hint"),
            }
    return None


def _extract_maintenance_timers(deep_snapshot: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Extract maintenance timers from deep snapshot."""
    for check in deep_snapshot.get("checks", []):
        if check.get("check") == "maintenance_timers":
            return list(check.get("details") or [])
    return None
