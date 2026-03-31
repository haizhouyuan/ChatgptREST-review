#!/usr/bin/env python3
from __future__ import annotations

"""
mihomo proxy delay snapshot for ChatgptREST.

This script:
1) Queries mihomo's `/proxies` to discover the currently selected node for one or more groups.
2) Runs `/proxies/{name}/delay` to measure latency.
3) Appends JSONL records to an output log file.

It is intended for incident correlation (e.g. Cloudflare/timeout spikes) and should be run
at a modest frequency (e.g. every 5–15 minutes) via a timer.
"""

import argparse
import time
from pathlib import Path

from chatgptrest.core import mihomo_delay


def main() -> int:
    default_cfg = mihomo_delay.load_mihomo_delay_config()

    ap = argparse.ArgumentParser()
    ap.add_argument("--controller", default=default_cfg.controller)
    ap.add_argument(
        "--targets",
        default=None,
        help="Override per-group delay targets: 'GroupA=https://...,GroupB=https://...'.",
    )
    ap.add_argument("--groups", default=",".join(default_cfg.groups or []))
    ap.add_argument("--url", default=default_cfg.url, help="Fallback URL when a group has no target override.")
    ap.add_argument("--timeout-ms", type=int, default=int(default_cfg.timeout_ms))
    ap.add_argument("--artifacts-dir", default="artifacts", help="ChatgptREST artifacts dir (default: artifacts)")
    ap.add_argument("--out-dir", default="", help="Override MIHOMO_DELAY_LOG_DIR for this run")
    args = ap.parse_args()

    group_urls = dict(default_cfg.group_urls or {})
    if args.targets is not None:
        group_urls = mihomo_delay.parse_targets(str(args.targets))

    groups = mihomo_delay.parse_groups(str(args.groups))
    if args.targets is not None:
        groups = list(group_urls.keys())

    cfg = mihomo_delay.MihomoDelayConfig(
        controller=str(args.controller).rstrip("/"),
        groups=groups,
        url=str(args.url).strip(),
        group_urls=group_urls,
        timeout_ms=max(1000, int(args.timeout_ms)),
    )
    artifacts_dir = Path(str(args.artifacts_dir)).expanduser()
    if str(args.out_dir).strip():
        out_dir = Path(str(args.out_dir).strip()).expanduser()
        log_path = out_dir / f"mihomo_delay_{time.strftime('%Y%m%d')}.jsonl"
    else:
        log_path = mihomo_delay.daily_log_path(artifacts_dir=artifacts_dir)

    try:
        records = mihomo_delay.snapshot_once(cfg=cfg)
    except Exception as exc:  # pragma: no cover - runtime dependent
        mihomo_delay.append_jsonl(
            log_path,
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "ok": False,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        return 2

    for rec in records:
        mihomo_delay.append_jsonl(log_path, rec)

    print(str(log_path))
    return 0 if all(bool(r.get("ok")) for r in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
