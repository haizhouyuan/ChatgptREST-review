#!/usr/bin/env python3
"""Health probe — periodic system health check for ChatgptREST.

Checks:
  - API liveness (18711)
  - Advisor v3 surface liveness (/v2/advisor/health on 18711)
  - Dashboard liveness (8787)
  - MCP adapter liveness (18712)
  - JobDB accessibility
  - Stuck/stale jobs (using queue_health semantics — report only)
  - KB FTS document count
  - Memory subsystem record count

The --fix flag is REPORT-ONLY: it writes stuck job details into the
snapshot for humans/guardian to act on.  It does NOT mutate job status,
because classify_stuck_wait_job returns stuck=True even for actively
leased jobs and health_probe cannot determine if the lease holder is
still alive.  Only the worker or an explicit operator action should
transition job status.

Designed for systemd oneshot (chatgptrest-health-probe.service / timer).

Usage:
  python ops/health_probe.py
  python ops/health_probe.py --fix           # report remediation candidates
  python ops/health_probe.py --fix --apply   # actually mutate (manual only, NOT in timer)
  python ops/health_probe.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

_CRITICAL_MAINTENANCE_TIMERS = (
    "chatgptrest-health-probe.timer",
    "chatgptrest-backlog-janitor.timer",
    "chatgptrest-ui-canary.timer",
)
_HEALTH_CHECKS_MODULE: Any | None = None


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _health_checks_module() -> Any:
    global _HEALTH_CHECKS_MODULE
    if _HEALTH_CHECKS_MODULE is None:
        _HEALTH_CHECKS_MODULE = _load_sibling_module("health_checks")
    return _HEALTH_CHECKS_MODULE


def _check_http(label: str, url: str, *, timeout: int = 5) -> dict[str, Any]:
    """Delegate basic HTTP liveness probing to the shared helper layer."""
    return _health_checks_module().check_http(label, url, timeout=timeout)


def _check_db(label: str, db_path: str) -> dict[str, Any]:
    """Delegate basic DB probing to the shared helper layer."""
    return _health_checks_module().check_db(label, db_path)


def _check_stuck_jobs(db_path: str, *, threshold_seconds: float = 3600) -> dict[str, Any]:
    """Identify stuck jobs using classify_stuck_wait_job semantics (report only)."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from chatgptrest.ops_shared.queue_health import classify_stuck_wait_job
    except ImportError:
        return {"check": "stuck_jobs", "ok": True, "note": "queue_health not importable; skipping"}

    now = time.time()
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT job_id, kind, status, phase, created_at, updated_at,
                   not_before, lease_owner, lease_expires_at
            FROM jobs
            WHERE status IN ('in_progress', 'needs_followup', 'blocked', 'cooldown')
            """
        ).fetchall()
        conn.close()
    except Exception as exc:
        return {"check": "stuck_jobs", "ok": False, "error": str(exc)[:200]}

    stuck_jobs: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        classification = classify_stuck_wait_job(row_dict, now=now, threshold_seconds=threshold_seconds)
        if classification.get("stuck"):
            stuck_jobs.append({
                "job_id": row_dict["job_id"],
                "kind": row_dict.get("kind", ""),
                "status": row_dict.get("status", ""),
                "phase": row_dict.get("phase", ""),
                "reason": classification.get("reason", ""),
                "idle_seconds": int(classification.get("idle_seconds", 0)),
            })

    # Also identify non-wait stale jobs with expired updated_at AND not_before
    non_wait_stale: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows2 = conn.execute(
            """
            SELECT job_id, kind, status, phase, updated_at, not_before
            FROM jobs
            WHERE status IN ('needs_followup', 'blocked', 'cooldown')
              AND updated_at < ?
              AND (not_before IS NULL OR not_before <= ?)
            """,
            (now - threshold_seconds, now),
        ).fetchall()
        conn.close()
        for r in rows2:
            rd = dict(r)
            jid = rd["job_id"]
            if not any(s["job_id"] == jid for s in stuck_jobs):
                non_wait_stale.append({
                    "job_id": jid,
                    "kind": rd.get("kind", ""),
                    "status": rd.get("status", ""),
                    "idle_seconds": int(now - float(rd.get("updated_at") or 0)),
                })
    except Exception:
        pass

    all_stuck = stuck_jobs + non_wait_stale
    return {
        "check": "stuck_jobs",
        "ok": len(all_stuck) <= 2,
        "stuck_count": len(all_stuck),
        "stuck_wait": len(stuck_jobs),
        "stale_non_wait": len(non_wait_stale),
        "details": all_stuck[:10],
    }


def _report_fix_candidates(db_path: str, *, threshold_seconds: float = 3600) -> dict[str, Any]:
    """Report jobs that would be candidates for remediation (no mutation).

    Only jobs with EXPIRED leases and stale updated_at are candidates.
    Jobs with active leases are excluded — the lease holder decides.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from chatgptrest.ops_shared.queue_health import classify_stuck_wait_job
    except ImportError:
        return {"candidates": 0, "note": "queue_health not importable"}

    now = time.time()
    candidates: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Wait jobs: only expired-lease stuck jobs are candidates (NOT active-lease)
        rows = conn.execute(
            """
            SELECT job_id, kind, status, phase, created_at, updated_at,
                   not_before, lease_owner, lease_expires_at
            FROM jobs
            WHERE status = 'in_progress' AND phase = 'wait'
            """
        ).fetchall()

        for row in rows:
            row_dict = dict(row)
            classification = classify_stuck_wait_job(row_dict, now=now, threshold_seconds=threshold_seconds)
            if classification.get("stuck") and classification.get("reason") == "expired_wait_lease":
                candidates.append({
                    "job_id": row_dict["job_id"],
                    "kind": row_dict.get("kind", ""),
                    "reason": "expired_wait_lease",
                    "idle_seconds": int(classification.get("idle_seconds", 0)),
                    "action": "would_error" if not _has_active_lease(row_dict, now) else "skip_active_lease",
                })

        # Non-wait stale (needs_followup/blocked with expired updated_at AND not_before)
        rows2 = conn.execute(
            """
            SELECT job_id, kind, status, updated_at, not_before
            FROM jobs
            WHERE status IN ('needs_followup', 'blocked', 'cooldown')
              AND updated_at < ?
              AND (not_before IS NULL OR not_before <= ?)
            """,
            (now - threshold_seconds, now),
        ).fetchall()

        for r in rows2:
            rd = dict(r)
            candidates.append({
                "job_id": rd["job_id"],
                "kind": rd.get("kind", ""),
                "reason": f"stale_{rd['status']}",
                "idle_seconds": int(now - float(rd.get("updated_at") or 0)),
                "action": "would_error",
            })

        conn.close()
    except Exception as exc:
        return {"candidates": len(candidates), "details": candidates, "error": str(exc)[:200]}

    return {"candidates": len(candidates), "details": candidates}


def _has_active_lease(row: dict[str, Any], now: float) -> bool:
    """Check if a job has an active lease."""
    lease_owner = str(row.get("lease_owner") or "").strip()
    lease_expires_at = float(row.get("lease_expires_at") or 0.0)
    return bool(lease_owner) or lease_expires_at > now


def _apply_fix(db_path: str, *, threshold_seconds: float = 3600) -> dict[str, Any]:
    """Actually mutate stuck jobs — ONLY expired-lease and stale non-wait.

    NEVER touches actively leased jobs. This path requires explicit --apply
    and should NOT be in the systemd timer.
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from chatgptrest.ops_shared.queue_health import classify_stuck_wait_job
    except ImportError:
        return {"fixed": 0, "note": "queue_health not importable"}

    now = time.time()
    fixed_ids: list[str] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Only fix expired-lease stuck jobs (NOT active-lease)
        rows = conn.execute(
            """
            SELECT job_id, kind, status, phase, created_at, updated_at,
                   not_before, lease_owner, lease_expires_at
            FROM jobs
            WHERE status = 'in_progress' AND phase = 'wait'
            """
        ).fetchall()

        for row in rows:
            row_dict = dict(row)
            if _has_active_lease(row_dict, now):
                continue  # Never touch actively leased jobs
            classification = classify_stuck_wait_job(row_dict, now=now, threshold_seconds=threshold_seconds)
            if classification.get("stuck") and classification.get("reason") == "expired_wait_lease":
                conn.execute(
                    """
                    UPDATE jobs SET status = 'error', updated_at = ?,
                           last_error_type = 'HealthProbeExpiredLease',
                           last_error = ?
                    WHERE job_id = ? AND status = 'in_progress'
                    """,
                    (now, f"health_probe --apply: expired lease (idle {int(classification.get('idle_seconds', 0))}s)", row_dict["job_id"]),
                )
                fixed_ids.append(row_dict["job_id"])

        # Non-wait stale
        rows2 = conn.execute(
            """
            SELECT job_id, status, updated_at, not_before
            FROM jobs
            WHERE status IN ('needs_followup', 'blocked', 'cooldown')
              AND updated_at < ?
              AND (not_before IS NULL OR not_before <= ?)
            """,
            (now - threshold_seconds, now),
        ).fetchall()

        for r in rows2:
            rd = dict(r)
            jid = rd["job_id"]
            if jid not in fixed_ids:
                conn.execute(
                    """
                    UPDATE jobs SET status = 'error', updated_at = ?,
                           last_error_type = 'HealthProbeStale',
                           last_error = ?
                    WHERE job_id = ? AND status IN ('needs_followup', 'blocked', 'cooldown')
                    """,
                    (now, f"health_probe --apply: stale {rd['status']} (idle {int(now - float(rd.get('updated_at') or 0))}s)", jid),
                )
                fixed_ids.append(jid)

        conn.commit()
        conn.close()
    except Exception as exc:
        return {"fixed": len(fixed_ids), "fixed_ids": fixed_ids, "error": str(exc)[:200]}

    return {"fixed": len(fixed_ids), "fixed_ids": fixed_ids}


def _check_kb(kb_path: str) -> dict[str, Any]:
    """Check KB FTS database."""
    try:
        conn = sqlite3.connect(f"file:{kb_path}?mode=ro", uri=True)
        count = conn.execute("SELECT count(*) FROM kb_fts").fetchone()[0]
        conn.close()
        return {"check": "kb_fts", "ok": count > 0, "doc_count": count}
    except Exception as exc:
        return {"check": "kb_fts", "ok": False, "error": str(exc)[:200]}


def _check_memory(mem_path: str) -> dict[str, Any]:
    """Check memory subsystem."""
    try:
        conn = sqlite3.connect(f"file:{mem_path}?mode=ro", uri=True)
        count = conn.execute("SELECT count(*) FROM memory_records").fetchone()[0]
        conn.close()
        return {"check": "memory", "ok": count > 0, "record_count": count}
    except Exception as exc:
        return {"check": "memory", "ok": False, "error": str(exc)[:200]}


def _load_sibling_module(name: str) -> Any:
    path = REPO_ROOT / "ops" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"chatgptrest_ops_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_public_mcp_ingress_contract() -> dict[str, Any]:
    try:
        mod = _load_sibling_module("check_public_mcp_client_configs")
        snapshot = mod.collect_alignment_report(apply_fix=False)
    except Exception as exc:
        return {"check": "public_mcp_ingress_contract", "ok": False, "error": str(exc)[:200]}

    failed_paths: list[str] = []
    failed_reasons: list[str] = []
    for item in snapshot.get("checks", []):
        if item.get("ok"):
            continue
        failed_paths.append(str(item.get("path", "")))
        failed_reasons.append(str(item.get("reason", "unknown")))
    wrapper = snapshot.get("skill_wrapper")
    if isinstance(wrapper, dict) and not wrapper.get("ok", False):
        failed_paths.append(str(wrapper.get("path", "")))
        failed_reasons.append(str(wrapper.get("reason", "unknown")))
    return {
        "check": "public_mcp_ingress_contract",
        "ok": bool(snapshot.get("ok")),
        "num_failed": int(snapshot.get("num_failed", 0)),
        "failed_paths": failed_paths,
        "failed_reasons": failed_reasons,
        "fix_hint": "python3 ops/check_public_mcp_client_configs.py --fix",
    }


def _systemctl_user_show(unit: str, *properties: str) -> dict[str, str]:
    cmd = [
        "systemctl",
        "--user",
        "show",
        unit,
        f"--property={','.join(properties)}",
        "--no-pager",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"systemctl exited {proc.returncode}").strip())
    out: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[str(key).strip()] = str(value).strip()
    return out


def _check_maintenance_timers() -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    failed_units: list[str] = []
    for unit in _CRITICAL_MAINTENANCE_TIMERS:
        try:
            state = _systemctl_user_show(unit, "ActiveState", "SubState", "UnitFileState")
            active_state = str(state.get("ActiveState") or "").strip().lower()
            sub_state = str(state.get("SubState") or "").strip().lower()
            unit_file_state = str(state.get("UnitFileState") or "").strip().lower()
            ok = active_state == "active" and unit_file_state in {
                "enabled",
                "static",
                "linked",
                "linked-runtime",
                "generated",
            }
            item = {
                "unit": unit,
                "ok": ok,
                "active_state": active_state,
                "sub_state": sub_state,
                "unit_file_state": unit_file_state,
            }
        except Exception as exc:
            ok = False
            item = {"unit": unit, "ok": False, "error": str(exc)[:200]}
        details.append(item)
        if not ok:
            failed_units.append(unit)
    return {
        "check": "maintenance_timers",
        "ok": not failed_units,
        "failed_units": failed_units,
        "details": details,
        "fix_hint": "systemctl --user enable --now chatgptrest-health-probe.timer chatgptrest-backlog-janitor.timer chatgptrest-ui-canary.timer",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ChatgptREST health probe.")
    ap.add_argument("--fix", action="store_true", help="Report remediation candidates (no mutation).")
    ap.add_argument("--apply", action="store_true", help="Actually mutate stuck jobs (requires --fix, NOT for timer).")
    ap.add_argument("--json", action="store_true", help="Output JSON only.")
    ap.add_argument("--threshold", type=int, default=3600, help="Stuck job threshold in seconds.")
    args = ap.parse_args(argv)

    db_path = os.environ.get("CHATGPTREST_DB_PATH", str(REPO_ROOT / "state" / "jobdb.sqlite3"))
    kb_path = os.environ.get("OPENMIND_KB_PATH", os.path.expanduser("~/.openmind/kb_search.db"))
    mem_path = os.environ.get("OPENMIND_MEMORY_DB", os.path.expanduser("~/.openmind/memory.db"))

    # Run checks
    results: list[dict[str, Any]] = []
    results.append(_check_http("api_18711", "http://127.0.0.1:18711/v1/ops/status", timeout=5))
    results.append(_check_http("advisor_v3", "http://127.0.0.1:18711/v2/advisor/health", timeout=5))
    results.append(_check_http("dashboard_8787", "http://127.0.0.1:8787/health", timeout=5))
    results.append(_check_http("mcp_18712", "http://127.0.0.1:18712/", timeout=5))
    results.append(_check_db("jobdb", db_path))
    results.append(_check_stuck_jobs(db_path, threshold_seconds=args.threshold))
    results.append(_check_kb(kb_path))
    results.append(_check_memory(mem_path))
    results.append(_check_public_mcp_ingress_contract())
    results.append(_check_maintenance_timers())

    fix_result: dict[str, Any] | None = None
    if args.fix:
        if args.apply:
            fix_result = _apply_fix(db_path, threshold_seconds=args.threshold)
        else:
            fix_result = _report_fix_candidates(db_path, threshold_seconds=args.threshold)

    snapshot = {
        "ts": _now_iso(),
        "checks": results,
        "all_ok": all(r.get("ok") for r in results),
        "fix_mode": "apply" if (args.fix and args.apply) else ("report" if args.fix else None),
        "fix_result": fix_result,
    }

    # Write to artifacts/monitor/health_probe/latest.json
    out_dir = REPO_ROOT / "artifacts" / "monitor" / "health_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "latest.json"
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

    tmp = latest.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(snapshot_json, encoding="utf-8")
    tmp.replace(latest)

    if args.json:
        print(snapshot_json)
    else:
        status = "PASS" if snapshot["all_ok"] else "FAIL"
        print(f"[{_now_iso()}] health_probe: {status}")
        for r in results:
            mark = "✅" if r.get("ok") else "❌"
            detail = json.dumps({k: v for k, v in r.items() if k != "check"}, ensure_ascii=False)
            print(f"  {mark} {r['check']}: {detail}")
        if fix_result:
            mode = "APPLIED" if (args.fix and args.apply) else "CANDIDATES"
            print(f"  🔧 fix ({mode}): {json.dumps(fix_result, ensure_ascii=False)}")

    return 0 if snapshot["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
