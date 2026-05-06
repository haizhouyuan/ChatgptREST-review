#!/usr/bin/env python3
"""UI canary sidecar — refresh latest.json from maint_daemon's state.

The maint_daemon.py already runs the actual driver self_check probes via
its stdio-based ToolCaller (the driver MCP is NOT accessible via HTTP).
That daemon tracks consecutive_failures, last_ok_ts, last_failure_ts, etc.
in its persistent state file: state/maint_daemon_state.json.

This sidecar's job is simple:
  1. Read the maint_daemon state file
  2. Extract the ui_canary section
  3. Write a normalized snapshot to artifacts/monitor/ui_canary/latest.json
     in the format expected by consumers (guardian, orch agent, ops routes)

Consumers rely on consecutive_failures >= threshold to flag providers as
failed.  This sidecar preserves that metadata from the authoritative source.

If the maint_daemon state is stale (last_run_ts older than --max-age), the
sidecar reports that as a "stale" warning — this means the daemon itself
may not be running.

Designed for systemd oneshot (chatgptrest-ui-canary.service / timer).

Usage:
  python ops/ui_canary_sidecar.py
  python ops/ui_canary_sidecar.py --max-age 600
  python ops/ui_canary_sidecar.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_STATE_PATH = str(REPO_ROOT / "state" / "maint_daemon_state.json")
DEFAULT_THRESHOLD = 2  # consecutive failure threshold matching maint_daemon default
DEFAULT_MAX_AGE = 600  # seconds — if maint_daemon hasn't run ui_canary in this long, warn


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_state(state_path: str) -> dict[str, Any]:
    """Read the maint_daemon state file."""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _build_provider_snapshot(
    provider: str,
    state_row: dict[str, Any],
    *,
    threshold: int,
    now: float,
    max_age: float,
) -> dict[str, Any]:
    """Build a single provider entry for latest.json."""
    last_run_ts = float(state_row.get("last_run_ts") or 0.0)
    last_ok_ts = float(state_row.get("last_ok_ts") or 0.0)
    consecutive_failures = int(state_row.get("consecutive_failures") or 0)
    last_status = str(state_row.get("last_status") or "")
    last_error_type = str(state_row.get("last_error_type") or "")
    last_error = str(state_row.get("last_error") or "")
    last_conversation_url = str(state_row.get("last_conversation_url") or "")
    last_mode_text = str(state_row.get("last_mode_text") or "")

    # Determine ok: provider's last known status is healthy
    ok = consecutive_failures == 0 and last_status not in ("error", "failed", "")

    # Check staleness: if the daemon hasn't run probes recently, mark as stale
    stale = (now - last_run_ts) > max_age if last_run_ts > 0 else True
    if stale:
        ok = False
        if not last_error:
            last_error = f"stale: last probe was {int(now - last_run_ts)}s ago" if last_run_ts > 0 else "never probed"
            last_error_type = "stale"

    return {
        "provider": provider,
        "ok": ok,
        "status": last_status or ("stale" if stale else "unknown"),
        "mode_text": last_mode_text,
        "error_type": last_error_type,
        "error": last_error[:300],
        "conversation_url": last_conversation_url,
        "consecutive_failures": consecutive_failures,
        "threshold": threshold,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="UI canary sidecar — refresh latest.json from maint_daemon state.")
    ap.add_argument(
        "--state-file",
        default=os.environ.get("CHATGPTREST_MAINT_STATE_PATH", DEFAULT_STATE_PATH),
        help="Path to maint_daemon_state.json.",
    )
    ap.add_argument(
        "--threshold",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_THRESHOLD", str(DEFAULT_THRESHOLD))),
        help="Consecutive failure threshold for incident triggering.",
    )
    ap.add_argument(
        "--max-age",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_MAX_AGE", str(DEFAULT_MAX_AGE))),
        help="Max seconds since last probe before marking as stale.",
    )
    ap.add_argument("--json", action="store_true", help="Output JSON only.")
    args = ap.parse_args(argv)

    now = time.time()
    state = _load_state(args.state_file)
    ui_canary_state = state.get("ui_canary")

    if not isinstance(ui_canary_state, dict) or not ui_canary_state:
        snapshot = {
            "ts": _now_iso(),
            "providers": [],
            "error": f"No ui_canary state found in {args.state_file}",
        }
    else:
        providers_out: list[dict[str, Any]] = []
        state_out: dict[str, Any] = {}
        for provider, state_row in ui_canary_state.items():
            if not isinstance(state_row, dict):
                continue
            entry = _build_provider_snapshot(
                provider,
                state_row,
                threshold=args.threshold,
                now=now,
                max_age=args.max_age,
            )
            providers_out.append(entry)
            state_out[provider] = state_row

        snapshot = {
            "ts": _now_iso(),
            "providers": providers_out,
            "state": state_out,
            "source": "ui_canary_sidecar",
            "maint_daemon_state_file": args.state_file,
        }

    # Write to artifacts/monitor/ui_canary/latest.json
    out_dir = REPO_ROOT / "artifacts" / "monitor" / "ui_canary"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "latest.json"

    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

    # Atomic write
    tmp = latest.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(snapshot_json, encoding="utf-8")
    tmp.replace(latest)

    # Also write timestamped snapshot
    snap_dir = out_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_name = f"canary_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z.json"
    (snap_dir / snap_name).write_text(snapshot_json, encoding="utf-8")

    if args.json:
        print(snapshot_json)
    else:
        providers = snapshot.get("providers", [])
        if not providers:
            print(f"[{_now_iso()}] ui_canary: NO DATA — {snapshot.get('error', 'unknown')}")
            # exit 1 ONLY when we failed to produce a snapshot (no state)
            return 1

        all_ok = all(p.get("ok") for p in providers)
        status = "PASS" if all_ok else "DEGRADED"
        print(f"[{_now_iso()}] ui_canary: {status} (snapshot refreshed)")
        for p in providers:
            mark = "✅" if p.get("ok") else "❌"
            mode = p.get("mode_text", "")
            err = p.get("error", "")
            cf = p.get("consecutive_failures", 0)
            detail = mode if p.get("ok") else (err[:80] if err else "unknown")
            suffix = f" (consecutive_failures={cf})" if cf > 0 else ""
            print(f"  {mark} {p['provider']}: {p.get('status', '?')} — {detail}{suffix}")

    # exit 0 = snapshot refreshed successfully, regardless of provider health.
    # Provider degradation is DATA in the snapshot, not a sidecar failure.
    # exit 1 only when the sidecar itself could not produce a snapshot.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
