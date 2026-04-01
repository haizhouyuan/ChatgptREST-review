"""Concrete Subsystem implementations for maint_daemon decomposition.

Each class here implements the ``Subsystem`` protocol from
``chatgptrest.ops_shared.subsystem`` and encapsulates one logical concern
that was previously inline in ``main()``.

The goal is incremental extraction: each subsystem is added to the
``SubsystemRunner`` in ``main()`` and the corresponding inline code is
replaced by a ``runner.tick_all()`` call.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from chatgptrest.ops_shared.infra import (
    atomic_write_json,
    now_iso,
    truncate_text,
)
from chatgptrest.ops_shared.subsystem import Observation, TickContext

logger = logging.getLogger("maint.subsystems")


# ---------------------------------------------------------------------------
# 1. HealthCheckSubsystem — RSS monitoring + watchdog
# ---------------------------------------------------------------------------


class HealthCheckSubsystem:
    """Self-monitoring: RSS memory check and systemd watchdog kick.

    Runs every 2 seconds (same as the poll interval).  Does not need
    the DB connection — only checks process-level health.
    """

    name = "health_check"
    interval_seconds = 2.0

    def tick(self, ctx: TickContext) -> list[Observation]:
        import resource

        from chatgptrest.ops_shared.infra import now_iso

        observations: list[Observation] = []

        # Kick systemd watchdog
        try:
            addr = __import__("os").environ.get("NOTIFY_SOCKET", "").strip()
            if addr:
                import socket as _sock

                s = _sock.socket(_sock.AF_UNIX, _sock.SOCK_DGRAM)
                try:
                    if addr.startswith("@"):
                        addr = "\0" + addr[1:]
                    s.sendto(b"WATCHDOG=1", addr)
                finally:
                    s.close()
        except Exception:
            pass

        # RSS check
        try:
            rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            rss_mb = 0.0

        if rss_mb > 2048:
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="alert",
                    data={"type": "rss_critical", "rss_mb": round(rss_mb, 1)},
                )
            )
        elif rss_mb > 1024:
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="metric",
                    data={"type": "rss_warning", "rss_mb": round(rss_mb, 1)},
                )
            )

        return observations


# ---------------------------------------------------------------------------
# 2. AutoResolveSubsystem — TTL-based incident auto-resolution
# ---------------------------------------------------------------------------


class AutoResolveSubsystem:
    """Auto-resolve stale incidents that haven't been seen for N hours.

    Required ``ctx.state`` keys:
    - ``log_path``: Path to the daemon JSONL log
    - ``incidents``: dict[str, IncidentState] — mutable incident map
    - ``incident_auto_resolve_after_hours``: int
    - ``incident_auto_resolve_max_per_run``: int
    - ``incident_db``: module with ``resolve_stale_incidents``
    """

    name = "auto_resolve"
    interval_seconds = 300.0  # default; overridden from args in __init__

    def __init__(self, *, interval_seconds: float = 300.0) -> None:
        self.interval_seconds = max(5.0, interval_seconds)

    def tick(self, ctx: TickContext) -> list[Observation]:
        observations: list[Observation] = []
        state = ctx.state

        ttl_hours = int(state.get("incident_auto_resolve_after_hours", 0))
        if ttl_hours <= 0:
            return observations

        conn = ctx.conn
        incidents: dict[str, Any] = state.get("incidents", {})
        log_path: Path | None = state.get("log_path")
        incident_db = state.get("incident_db")
        max_per_run = int(state.get("incident_auto_resolve_max_per_run", 50))

        if conn is None or incident_db is None:
            return observations

        stale_before = float(ctx.now) - float(ttl_hours) * 3600.0

        try:
            conn.execute("BEGIN IMMEDIATE")
            resolved = incident_db.resolve_stale_incidents(
                conn,
                stale_before_ts=float(stale_before),
                now=float(ctx.now),
                limit=max_per_run,
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="error",
                    data={
                        "type": "incident_auto_resolve_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:800],
                    },
                )
            )
            return observations

        if resolved:
            for rec in resolved:
                incidents.pop(str(rec.fingerprint_hash), None)
                if log_path:
                    from chatgptrest.ops_shared.infra import now_iso

                    _append_jsonl_safe(
                        log_path,
                        {
                            "ts": now_iso(),
                            "type": "incident_auto_resolved",
                            "incident_id": str(rec.incident_id),
                            "sig_hash": str(rec.fingerprint_hash),
                            "last_seen_at": float(rec.last_seen_at),
                            "count": int(rec.count),
                            "signature": truncate_text(str(rec.signature), limit=300),
                        },
                    )
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="action",
                    data={
                        "type": "incident_auto_resolve_sweep",
                        "resolved": len(resolved),
                        "ttl_hours": ttl_hours,
                    },
                )
            )

        return observations


# ---------------------------------------------------------------------------
# 3. BlockedStateSubsystem — chatgptMCP blocked-state file → auto-pause
# ---------------------------------------------------------------------------


class BlockedStateSubsystem:
    """Check chatgptMCP blocked-state file and auto-set/clear pause.

    Required ``ctx.state`` keys:
    - ``log_path``: Path to the daemon JSONL log
    - ``chatgptmcp_state_path``: Path to chatgptMCP state JSON
    - ``legacy_blocked_path``: Path to legacy blocked-state JSON
    - ``enable_auto_pause``: bool
    - ``auto_pause_mode``: str ("send" | "all")
    - ``auto_pause_default_seconds``: int
    """

    name = "blocked_state"
    interval_seconds = 15.0

    def __init__(self, *, interval_seconds: float = 15.0) -> None:
        self.interval_seconds = max(5.0, interval_seconds)

    def tick(self, ctx: TickContext) -> list[Observation]:
        import json as _json

        observations: list[Observation] = []
        state = ctx.state
        conn = ctx.conn
        log_path: Path | None = state.get("log_path")

        chatgptmcp_state_path = state.get("chatgptmcp_state_path")
        legacy_blocked_path = state.get("legacy_blocked_path")
        if chatgptmcp_state_path is None:
            return observations

        # Read blocked state
        bs = None
        try:
            if Path(chatgptmcp_state_path).exists():
                bs = _json.loads(Path(chatgptmcp_state_path).read_text(encoding="utf-8"))
        except Exception:
            pass
        if bs is None:
            try:
                if legacy_blocked_path and Path(legacy_blocked_path).exists():
                    bs = _json.loads(Path(legacy_blocked_path).read_text(encoding="utf-8"))
            except Exception:
                pass
        if bs is None or not isinstance(bs, dict):
            return observations

        blocked_until = float(bs.get("blocked_until") or 0.0)
        blocked = bool(blocked_until and blocked_until > ctx.now)

        enable_auto_pause = bool(state.get("enable_auto_pause", False))

        if enable_auto_pause and conn is not None:
            try:
                from chatgptrest.core.pause import clear_pause_state, get_pause_state, set_pause_state

                mode = str(state.get("auto_pause_mode") or "send").strip().lower() or "send"
                if mode not in {"send", "all"}:
                    mode = "send"
                current = get_pause_state(conn)

                if blocked:
                    default_seconds = int(state.get("auto_pause_default_seconds", 300))
                    desired_until = blocked_until if blocked_until > ctx.now else (ctx.now + float(max(60, default_seconds)))
                    desired_until = max(float(desired_until), float(current.until_ts or 0.0))
                    desired_mode = "all" if (mode == "all" or current.mode == "all") else mode
                    desired_reason = current.reason
                    if not desired_reason or desired_reason.startswith("auto_blocked:"):
                        raw_reason = str(bs.get("reason") or "").strip()
                        raw_url = str(bs.get("url") or "").strip()
                        tail = raw_reason or raw_url or "blocked"
                        desired_reason = f"auto_blocked:{tail}"[:200]

                    if (not current.is_active(now=ctx.now)) or current.mode != desired_mode or float(current.until_ts or 0.0) < float(desired_until):
                        set_pause_state(conn, mode=desired_mode, until_ts=float(desired_until), reason=desired_reason)
                        observations.append(
                            Observation(
                                subsystem=self.name,
                                kind="action",
                                data={
                                    "type": "auto_pause_set",
                                    "mode": desired_mode,
                                    "until": float(desired_until),
                                    "reason": desired_reason,
                                },
                            )
                        )
                else:
                    if current.is_active(now=ctx.now) and (current.reason or "").startswith("auto_blocked:"):
                        clear_pause_state(conn)
                        observations.append(
                            Observation(
                                subsystem=self.name,
                                kind="action",
                                data={"type": "auto_pause_cleared", "reason": current.reason},
                            )
                        )
            except Exception as exc:
                observations.append(
                    Observation(
                        subsystem=self.name,
                        kind="error",
                        data={"type": "auto_pause_error", "error": str(exc)[:500]},
                    )
                )

        # Always log blocked state
        observations.append(
            Observation(
                subsystem=self.name,
                kind="metric",
                data={
                    "type": "chatgptmcp_blocked_state",
                    "blocked": blocked,
                    "blocked_until": blocked_until,
                    "reason": bs.get("reason"),
                    "phase": bs.get("phase"),
                    "url": bs.get("url"),
                },
            )
        )

        return observations


# ---------------------------------------------------------------------------
# 4. JobsSummarySubsystem — periodic jobs DB summary snapshot
# ---------------------------------------------------------------------------


class JobsSummarySubsystem:
    """Periodically snapshot the jobs DB summary to the log.

    Required ``ctx.state`` keys:
    - ``log_path``: Path to the daemon JSONL log
    - ``jobs_summary_fn``: callable(conn) -> dict
    """

    name = "jobs_summary"
    interval_seconds = 60.0

    def __init__(self, *, interval_seconds: float = 60.0) -> None:
        self.interval_seconds = max(5.0, interval_seconds)

    def tick(self, ctx: TickContext) -> list[Observation]:
        observations: list[Observation] = []
        conn = ctx.conn
        if conn is None:
            return observations

        summary_fn = ctx.state.get("jobs_summary_fn")
        if summary_fn is None:
            return observations

        try:
            summary = summary_fn(conn)
        except Exception as exc:
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="error",
                    data={"type": "jobs_summary_error", "error": str(exc)[:500]},
                )
            )
            return observations

        observations.append(
            Observation(
                subsystem=self.name,
                kind="metric",
                data={"type": "jobs_summary", "summary": summary},
            )
        )

        return observations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_jsonl_safe(path: Path, payload: dict[str, Any]) -> None:
    """Best-effort append a JSON line to a log file."""
    import json

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
