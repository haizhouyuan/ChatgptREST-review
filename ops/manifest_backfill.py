#!/usr/bin/env python3
"""Backfill manifest.json for existing job artifact directories.

Phase 1b of artifact governance blueprint v2.

Usage:
    # Dry run (default): show what would be created
    python ops/manifest_backfill.py --dry-run

    # Count only
    python ops/manifest_backfill.py --count-only

    # Apply to first 100 dirs
    python ops/manifest_backfill.py --apply --limit 100

    # Force regenerate (overwrite existing manifests)
    python ops/manifest_backfill.py --apply --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chatgptrest.governance.manifest import (
    generate_job_manifest,
    validate_manifest,
)

logger = logging.getLogger("manifest_backfill")

DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "jobs"


def backfill(
    artifacts_root: Path,
    *,
    repo_root: Path | None = None,
    dry_run: bool = True,
    force: bool = False,
    limit: int = 0,
    count_only: bool = False,
) -> dict:
    """Backfill manifest.json for all job directories.

    Args:
        artifacts_root: Path to the jobs directory (e.g. artifacts/jobs/)
        repo_root: Repository root for relative paths. Defaults to PROJECT_ROOT.
        dry_run: If True, don't actually write manifests
        force: Overwrite existing manifests
        limit: Max dirs to process (0=all)
        count_only: Only count dirs, don't process

    Returns summary dict with counts.
    """
    effective_root = repo_root or PROJECT_ROOT

    if not artifacts_root.exists():
        logger.error("Artifacts root not found: %s", artifacts_root)
        return {"error": f"not found: {artifacts_root}"}

    # Scan directories
    job_dirs = sorted(
        (d for d in artifacts_root.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=lambda d: d.name,
    )

    total = len(job_dirs)
    has_manifest = sum(1 for d in job_dirs if (d / "manifest.json").exists())
    needs_manifest = total - has_manifest

    if count_only:
        return {
            "total_job_dirs": total,
            "has_manifest": has_manifest,
            "needs_manifest": needs_manifest,
        }

    # Process
    created = 0
    skipped = 0
    errors = 0
    processed = 0

    for d in job_dirs:
        if limit > 0 and processed >= limit:
            break

        manifest_path = d / "manifest.json"

        # Skip existing unless force
        if manifest_path.exists() and not force:
            skipped += 1
            processed += 1
            continue

        try:
            manifest = generate_job_manifest(d, repo_root=effective_root)
            validation_errors = validate_manifest(manifest)

            if validation_errors:
                logger.warning("Invalid manifest for %s: %s", d.name, validation_errors)
                errors += 1
                processed += 1
                continue

            if dry_run:
                logger.info("[DRY-RUN] Would create %s", manifest_path)
            else:
                manifest_path.write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                logger.debug("Created %s", manifest_path)

            created += 1

        except Exception as exc:
            logger.warning("Error for %s: %s", d.name, exc)
            errors += 1

        processed += 1

    return {
        "total_job_dirs": total,
        "processed": processed,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill manifest.json for job artifact dirs")
    parser.add_argument(
        "--artifacts-root",
        default=str(DEFAULT_ARTIFACTS_ROOT),
        help="Path to artifacts/jobs/ directory",
    )
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (default)")
    parser.add_argument("--apply", action="store_true", help="Actually write manifests")
    parser.add_argument("--force", action="store_true", help="Overwrite existing manifests")
    parser.add_argument("--limit", type=int, default=0, help="Max dirs to process (0=all)")
    parser.add_argument("--count-only", action="store_true", help="Only count, don't process")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    dry_run = not args.apply

    t0 = time.monotonic()
    result = backfill(
        Path(args.artifacts_root),
        dry_run=dry_run,
        force=args.force,
        limit=args.limit,
        count_only=args.count_only,
    )
    elapsed = time.monotonic() - t0

    result["elapsed_seconds"] = round(elapsed, 2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
