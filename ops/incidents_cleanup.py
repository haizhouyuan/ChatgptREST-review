#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ts)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Resolve stale incidents (manual maintenance tool).")
    p.add_argument("--db-path", default="state/jobdb.sqlite3")
    p.add_argument("--older-than-days", type=float, default=14.0)
    p.add_argument("--severity", default="", help="Optional severity filter (P0/P1/P2)")
    p.add_argument("--status-not", default="resolved", help="Only touch incidents whose status != this value")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    args = p.parse_args(argv)

    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.exists():
        print(f"db not found: {db_path}", file=sys.stderr)
        return 2

    now = time.time()
    older_than_days = max(0.0, float(args.older_than_days))
    cutoff = now - older_than_days * 86400.0
    severity = (str(args.severity or "").strip().upper() or None)
    status_not = str(args.status_not or "resolved").strip().lower()

    with _connect(db_path) as conn:
        where = ["LOWER(status) != ?", "last_seen_at < ?"]
        params: list[Any] = [status_not, float(cutoff)]
        if severity:
            where.append("UPPER(severity) = ?")
            params.append(severity)
        sql = (
            "SELECT incident_id, severity, status, category, count, last_seen_at, signature "
            "FROM incidents "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY last_seen_at ASC "
            "LIMIT ?"
        )
        rows = conn.execute(sql, (*params, int(max(1, args.limit)))).fetchall()

        print(f"db={db_path}")
        print(f"cutoff_utc={_fmt_ts(cutoff)} older_than_days={older_than_days:g} severity={severity or '*'}")
        print(f"candidates={len(rows)} apply={bool(args.apply)}")

        if not rows:
            return 0

        # Show a short preview (first 30).
        for r in rows[:30]:
            sig = str(r["signature"] or "").replace("\n", " ").strip()
            if len(sig) > 140:
                sig = sig[:140] + "…"
            print(
                f"- {r['incident_id']} {str(r['severity'] or '').strip()} {str(r['status'] or '').strip()} "
                f"last_seen={_fmt_ts(float(r['last_seen_at'] or 0.0))} count={int(r['count'] or 0)} sig={sig}"
            )

        if not args.apply:
            print("dry_run: pass --apply to resolve these incidents.")
            return 0

        ids = [str(r["incident_id"]) for r in rows]
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "UPDATE incidents SET status='resolved', updated_at=? WHERE incident_id=?",
            [(float(now), incident_id) for incident_id in ids],
        )
        conn.commit()
        print(f"resolved={len(ids)}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

