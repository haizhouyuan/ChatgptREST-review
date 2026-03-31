#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.ops_shared.issue_github_sync import default_repo_slug, sync_issue_to_github


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "state" / "jobdb.sqlite3"
DEFAULT_REPORT = REPO_ROOT / "artifacts" / "monitor" / "issue_github_sync" / "latest.json"


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _enabled(default: bool = False) -> bool:
    raw = str(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_ENABLED") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--repo", default=str(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_REPO") or "").strip() or None)
    parser.add_argument("--source", default=str(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_SOURCE") or "worker_auto").strip())
    parser.add_argument("--open-limit", type=int, default=int(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_OPEN_LIMIT") or 200))
    parser.add_argument("--closed-limit", type=int, default=int(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_CLOSED_LIMIT") or 100))
    parser.add_argument(
        "--closed-lookback-hours",
        type=float,
        default=float(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_CLOSED_LOOKBACK_HOURS") or 168),
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run even when CHATGPTREST_GITHUB_ISSUE_SYNC_ENABLED is false.")
    return parser.parse_args(argv)


def run_sync(args: argparse.Namespace) -> dict[str, Any]:
    repo = str(args.repo or "").strip() or default_repo_slug(REPO_ROOT)
    if not repo:
        raise SystemExit("GitHub repo slug is required via --repo or remote.origin.url")

    if not args.force and not _enabled(default=False):
        payload = {
            "ok": True,
            "skipped": True,
            "reason": "sync_disabled",
            "repo": repo,
            "ts": time.time(),
        }
        _json_dump(args.report, payload)
        return payload

    now = time.time()
    cutoff = now - float(max(1.0, float(args.closed_lookback_hours)) * 3600.0)
    results: list[dict[str, Any]] = []
    seen_issue_ids: set[str] = set()

    with connect(args.db) as conn:
        open_rows, _, _ = client_issues.list_issues(
            conn,
            source=args.source,
            status="open,in_progress,mitigated",
            limit=max(1, int(args.open_limit)),
        )
        closed_rows, _, _ = client_issues.list_issues(
            conn,
            source=args.source,
            status="closed",
            since_ts=cutoff,
            limit=max(1, int(args.closed_limit)),
        )
        for issue in [*open_rows, *closed_rows]:
            if issue.issue_id in seen_issue_ids:
                continue
            seen_issue_ids.add(issue.issue_id)
            results.append(
                sync_issue_to_github(
                    conn,
                    issue=issue,
                    repo=repo,
                    dry_run=bool(args.dry_run),
                )
            )
        conn.commit()

    payload = {
        "ok": True,
        "skipped": False,
        "repo": repo,
        "source": args.source,
        "dry_run": bool(args.dry_run),
        "ts": now,
        "counts": {
            "processed": len(results),
            "created": len([r for r in results if "create" in str(r.get("action") or "")]),
            "closed": len([r for r in results if "closed" in str(r.get("action") or "")]),
            "commented": len([r for r in results if "commented" in str(r.get("action") or "")]),
            "noop": len([r for r in results if str(r.get("action") or "") == "noop"]),
        },
        "results": results,
    }
    _json_dump(args.report, payload)
    return payload


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    payload = run_sync(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
