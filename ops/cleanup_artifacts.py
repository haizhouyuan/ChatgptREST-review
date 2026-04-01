from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect


def _rm_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup old ChatgptREST artifacts to prevent disk bloat.")
    parser.add_argument("--days", type=int, default=14, help="Delete terminal job artifacts older than N days.")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be deleted.")
    parser.add_argument("--db", default=None, help="Override CHATGPTREST_DB_PATH.")
    parser.add_argument("--artifacts", default=None, help="Override CHATGPTREST_ARTIFACTS_DIR.")
    args = parser.parse_args()

    cfg = load_config()
    db_path = Path(args.db).expanduser() if args.db else cfg.db_path
    artifacts_dir = Path(args.artifacts).expanduser() if args.artifacts else cfg.artifacts_dir

    days = int(args.days)
    if days < 0:
        raise ValueError("--days must be >= 0")
    threshold = time.time() - float(days) * 86400.0

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT job_id, status, created_at
            FROM jobs
            WHERE created_at < ?
              AND status IN ('completed', 'error', 'canceled')
            ORDER BY created_at ASC
            """,
            (threshold,),
        ).fetchall()

    to_delete = []
    for row in rows:
        job_id = str(row["job_id"] or "").strip()
        if not job_id:
            continue
        job_dir = artifacts_dir / "jobs" / job_id
        if job_dir.exists():
            to_delete.append(job_dir)

    staging = sorted((artifacts_dir / "jobs").glob("**/*.staging.*")) if (artifacts_dir / "jobs").exists() else []

    for p in to_delete:
        if args.dry_run:
            print(f"[dry-run] rm -rf {p}")
        else:
            _rm_tree(p)

    for p in staging:
        if args.dry_run:
            print(f"[dry-run] rm {p}")
        else:
            try:
                p.unlink()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
