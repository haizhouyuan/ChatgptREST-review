#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.finbot import (
    DEFAULT_FINAGENT_PYTHON,
    DEFAULT_FINAGENT_ROOT,
    DEFAULT_FINBOT_ROOT,
    DEFAULT_THEME_CATALOG_PATH,
    ack_inbox_item,
    daily_work,
    list_inbox,
    load_theme_catalog,
    opportunity_deepen,
    refresh_dashboard_projection,
    theme_batch_run,
    theme_radar_scout,
    watchlist_scout,
)


def _emit(payload: dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("dashboard-refresh")
    p.add_argument("--format", choices=("json", "text"), default="text")

    p = sub.add_parser("watchlist-scout")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--scope", default="today")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--finagent-root", default=str(DEFAULT_FINAGENT_ROOT))
    p.add_argument("--python-bin", default=DEFAULT_FINAGENT_PYTHON)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))

    p = sub.add_parser("theme-radar-scout")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--finagent-root", default=str(DEFAULT_FINAGENT_ROOT))
    p.add_argument("--python-bin", default=DEFAULT_FINAGENT_PYTHON)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))

    p = sub.add_parser("theme-batch-run")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--finagent-root", default=str(DEFAULT_FINAGENT_ROOT))
    p.add_argument("--python-bin", default=DEFAULT_FINAGENT_PYTHON)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))
    p.add_argument("--catalog-path", default=str(DEFAULT_THEME_CATALOG_PATH))

    p = sub.add_parser("opportunity-deepen")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--candidate-id", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-age-hours", type=int, default=18)
    p.add_argument("--finagent-root", default=str(DEFAULT_FINAGENT_ROOT))
    p.add_argument("--python-bin", default=DEFAULT_FINAGENT_PYTHON)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))

    p = sub.add_parser("daily-work")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--scope", default="today")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--skip-source-refresh", action="store_true")
    p.add_argument("--refresh-limit", type=int, default=5)
    p.add_argument("--include-theme-batch", action="store_true")
    p.add_argument("--discovery-strategy", default="auto",
                    choices=("auto", "value", "momentum", "growth", "contrarian"),
                    help="Market discovery strategy (default: auto = rotate by hour)")
    p.add_argument("--finagent-root", default=str(DEFAULT_FINAGENT_ROOT))
    p.add_argument("--python-bin", default=DEFAULT_FINAGENT_PYTHON)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))
    p.add_argument("--catalog-path", default=str(DEFAULT_THEME_CATALOG_PATH))

    p = sub.add_parser("theme-catalog")
    p.add_argument("--format", choices=("json", "text"), default="json")
    p.add_argument("--catalog-path", default=str(DEFAULT_THEME_CATALOG_PATH))

    p = sub.add_parser("inbox-list")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))

    p = sub.add_parser("inbox-ack")
    p.add_argument("item_id")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--finbot-root", default=str(DEFAULT_FINBOT_ROOT))

    args = parser.parse_args()
    if args.command == "dashboard-refresh":
        payload = refresh_dashboard_projection()
    elif args.command == "watchlist-scout":
        payload = watchlist_scout(
            finagent_root=Path(args.finagent_root).expanduser(),
            python_bin=args.python_bin,
            root=Path(args.finbot_root).expanduser(),
            scope=args.scope,
            limit=args.limit,
        )
    elif args.command == "theme-radar-scout":
        payload = theme_radar_scout(
            finagent_root=Path(args.finagent_root).expanduser(),
            python_bin=args.python_bin,
            root=Path(args.finbot_root).expanduser(),
            limit=args.limit,
        )
    elif args.command == "theme-batch-run":
        payload = theme_batch_run(
            finagent_root=Path(args.finagent_root).expanduser(),
            python_bin=args.python_bin,
            root=Path(args.finbot_root).expanduser(),
            catalog_path=Path(args.catalog_path).expanduser(),
            limit=args.limit,
        )
    elif args.command == "opportunity-deepen":
        payload = opportunity_deepen(
            candidate_id=(args.candidate_id or None),
            finagent_root=Path(args.finagent_root).expanduser(),
            python_bin=args.python_bin,
            root=Path(args.finbot_root).expanduser(),
            force=bool(args.force),
            max_age_hours=int(args.max_age_hours),
        )
    elif args.command == "daily-work":
        payload = daily_work(
            finagent_root=Path(args.finagent_root).expanduser(),
            python_bin=args.python_bin,
            root=Path(args.finbot_root).expanduser(),
            scope=args.scope,
            limit=args.limit,
            include_source_refresh=not bool(args.skip_source_refresh),
            refresh_limit=int(args.refresh_limit),
            include_theme_batch=bool(args.include_theme_batch),
            discovery_strategy=str(args.discovery_strategy),
            catalog_path=Path(args.catalog_path).expanduser(),
        )
    elif args.command == "theme-catalog":
        payload = load_theme_catalog(Path(args.catalog_path).expanduser())
    elif args.command == "inbox-list":
        payload = list_inbox(root=Path(args.finbot_root).expanduser(), limit=args.limit)
    else:
        payload = ack_inbox_item(args.item_id, root=Path(args.finbot_root).expanduser())
    _emit(payload, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
