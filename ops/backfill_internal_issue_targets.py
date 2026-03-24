#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.core.db import connect
from chatgptrest.ops_shared.issue_targets import backfill_polluted_issue_targets


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill issue.latest_job_id/source away from internal sre./repair. follow-up jobs.")
    ap.add_argument("--db", default="state/jobdb.sqlite3", help="Path to ChatgptREST job DB.")
    ap.add_argument("--issue-id", default="", help="Optional single issue_id to backfill.")
    ap.add_argument("--limit", type=int, default=200, help="Max polluted issues to inspect.")
    ap.add_argument("--dry-run", action="store_true", help="Do not commit DB changes.")
    ap.add_argument("--json-out", default="", help="Optional path to write the JSON summary.")
    args = ap.parse_args()

    db_path = Path(str(args.db)).expanduser()
    if not db_path.is_absolute():
        db_path = (Path(__file__).resolve().parents[1] / db_path).resolve(strict=False)

    with connect(db_path) as conn:
        updates = backfill_polluted_issue_targets(
            conn,
            issue_id=(str(args.issue_id).strip() or None),
            limit=max(1, int(args.limit)),
        )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

    payload = {
        "db_path": db_path.as_posix(),
        "dry_run": bool(args.dry_run),
        "updated_count": len(updates),
        "updates": updates,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if str(args.json_out).strip():
        out_path = Path(str(args.json_out)).expanduser()
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve(strict=False)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
