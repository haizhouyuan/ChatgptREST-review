#!/usr/bin/env python3
"""Artifact governance daemon — 6 independent stages.

Phase 2 of artifact governance blueprint v2.

Each stage runs independently with its own input/output/status.
Default mode is ``--dry-run`` (observe-only, no mutations).

Stages:
  1. manifest_audit    — verify manifests exist and are valid
  2. retention_enforce — enforce budget-driven retention
  3. kb_governance     — rescore quality + transition stability
  4. memory_governance — expire stale records + consolidate
  5. review_governance — review-plane artifact lifecycle
  6. promotion_check   — identify promotion-ready candidates

Usage:
    # Run all stages in dry-run
    python ops/artifact_governance_daemon.py --dry-run

    # Run specific stage
    python ops/artifact_governance_daemon.py --stage kb_governance --dry-run

    # Apply all stages
    python ops/artifact_governance_daemon.py --apply

    # Run as periodic cron (writes results to output dir)
    python ops/artifact_governance_daemon.py --apply --output-dir artifacts/monitor/governance/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chatgptrest.governance.batch_wrappers import (
    BatchResult,
    batch_kb_quality_rescore,
    batch_kb_stability_transition,
    batch_kb_prune,
    batch_memory_expire,
    batch_memory_consolidate,
    batch_retention_enforce,
)
from chatgptrest.governance.manifest import validate_manifest

logger = logging.getLogger("artifact_governance")

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "monitor" / "governance"
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "jobs"

STAGE_NAMES = [
    "manifest_audit",
    "retention_enforce",
    "kb_governance",
    "memory_governance",
    "review_governance",
    "promotion_check",
]


# ---------------------------------------------------------------------------
# Stage result container
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Result of a single daemon stage."""
    stage: str = ""
    status: str = "pending"   # pending | running | completed | error | skipped
    dry_run: bool = True
    started_at: str = ""
    finished_at: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
            "errors": self.errors,
        }


@dataclass
class DaemonResult:
    """Aggregate result of all daemon stages."""
    started_at: str = ""
    finished_at: str = ""
    dry_run: bool = True
    stages: list[StageResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "stages": [s.to_dict() for s in self.stages],
            "total_errors": sum(len(s.errors) for s in self.stages),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Stage 1: Manifest Audit
# ---------------------------------------------------------------------------

def stage_manifest_audit(
    artifacts_root: Path,
    *,
    dry_run: bool = True,
    limit: int = 500,
    audit_path: Path | None = None,
) -> StageResult:
    """Verify all job dirs have valid manifests."""
    result = StageResult(stage="manifest_audit", dry_run=dry_run, started_at=_now_iso())

    try:
        if not artifacts_root.exists():
            result.status = "error"
            result.errors.append(f"artifacts root not found: {artifacts_root}")
            result.finished_at = _now_iso()
            return result

        job_dirs = sorted(
            (d for d in artifacts_root.iterdir() if d.is_dir() and not d.name.startswith(".")),
            key=lambda d: d.name,
        )[:limit]

        total = len(job_dirs)
        has_manifest = 0
        valid = 0
        invalid = 0
        missing = 0

        for d in job_dirs:
            manifest_path = d / "manifest.json"
            if not manifest_path.exists():
                missing += 1
                continue

            has_manifest += 1
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                errors = validate_manifest(data)
                if errors:
                    invalid += 1
                else:
                    valid += 1
            except Exception:
                invalid += 1

        result.summary = {
            "total_dirs": total,
            "has_manifest": has_manifest,
            "valid": valid,
            "invalid": invalid,
            "missing": missing,
            "coverage_pct": round(has_manifest / total * 100, 1) if total > 0 else 0,
        }
        result.status = "completed"

    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Stage 2: Retention Enforcement
# ---------------------------------------------------------------------------

def stage_retention_enforce(
    artifacts_root: Path,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> StageResult:
    """Run budget-driven retention enforcement."""
    result = StageResult(stage="retention_enforce", dry_run=dry_run, started_at=_now_iso())

    try:
        br = batch_retention_enforce(artifacts_root, dry_run=dry_run, audit_path=audit_path)
        result.summary = {
            "total_dirs": br.total_candidates,
            "archived": br.processed,
            "errors": br.errors,
        }
        result.status = "completed"
    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Stage 3: KB Governance
# ---------------------------------------------------------------------------

def stage_kb_governance(
    registry: Any | None = None,
    pruner: Any | None = None,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> StageResult:
    """Rescore quality + transition stability + prune."""
    result = StageResult(stage="kb_governance", dry_run=dry_run, started_at=_now_iso())

    if registry is None:
        result.status = "skipped"
        result.summary = {"reason": "no ArtifactRegistry provided"}
        result.finished_at = _now_iso()
        return result

    try:
        # Rescore
        rescore = batch_kb_quality_rescore(registry, dry_run=dry_run, audit_path=audit_path)

        # Stability transitions
        stability = batch_kb_stability_transition(registry, dry_run=dry_run, audit_path=audit_path)

        # Prune
        prune_result = None
        if pruner is not None:
            prune_result = batch_kb_prune(pruner, dry_run=dry_run, audit_path=audit_path)

        result.summary = {
            "rescore": {"processed": rescore.processed, "skipped": rescore.skipped, "errors": rescore.errors},
            "stability": {"processed": stability.processed, "skipped": stability.skipped, "errors": stability.errors},
            "prune": prune_result.to_dict() if prune_result else {"skipped": "no pruner"},
        }
        result.status = "completed"
    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Stage 4: Memory Governance
# ---------------------------------------------------------------------------

def stage_memory_governance(
    memory_mgr: Any | None = None,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> StageResult:
    """Expire stale memory records + consolidate episodic → semantic."""
    result = StageResult(stage="memory_governance", dry_run=dry_run, started_at=_now_iso())

    if memory_mgr is None:
        result.status = "skipped"
        result.summary = {"reason": "no MemoryManager provided"}
        result.finished_at = _now_iso()
        return result

    try:
        expire = batch_memory_expire(memory_mgr, dry_run=dry_run, audit_path=audit_path)
        consolidate = batch_memory_consolidate(memory_mgr, dry_run=dry_run, audit_path=audit_path)

        result.summary = {
            "expire": {"processed": expire.processed, "errors": expire.errors},
            "consolidate": {"processed": consolidate.processed, "skipped": consolidate.skipped, "errors": consolidate.errors},
        }
        result.status = "completed"
    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Stage 5: Review Governance
# ---------------------------------------------------------------------------

def stage_review_governance(
    registry: Any | None = None,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> StageResult:
    """Manage review-plane artifact lifecycle.

    Identifies:
    - Overdue reviews (artifacts with review_due in the past)
    - Stale candidates (candidate stability > 30 days without promotion)
    """
    result = StageResult(stage="review_governance", dry_run=dry_run, started_at=_now_iso())

    if registry is None:
        result.status = "skipped"
        result.summary = {"reason": "no ArtifactRegistry provided"}
        result.finished_at = _now_iso()
        return result

    try:
        now = datetime.now(timezone.utc)
        all_arts = registry.search(limit=1000)

        overdue_reviews = 0
        stale_candidates = 0

        for art in all_arts:
            # Check overdue reviews
            if art.review_due:
                try:
                    due = datetime.fromisoformat(art.review_due)
                    if due < now:
                        overdue_reviews += 1
                except ValueError:
                    pass

            # Check stale candidates
            if art.stability == "candidate" and art.created_at:
                try:
                    created = datetime.fromisoformat(art.created_at)
                    age = (now - created).days
                    if age > 30:
                        stale_candidates += 1
                except ValueError:
                    pass

        result.summary = {
            "total_artifacts": len(all_arts),
            "overdue_reviews": overdue_reviews,
            "stale_candidates": stale_candidates,
        }
        result.status = "completed"
    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Stage 6: Promotion Check
# ---------------------------------------------------------------------------

def stage_promotion_check(
    registry: Any | None = None,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> StageResult:
    """Identify artifacts ready for promotion.

    Candidates:
    - stability == "candidate" with quality_score >= 0.8
    - quarantine_weight >= 0.7 (not blocked/hypothetical)
    """
    result = StageResult(stage="promotion_check", dry_run=dry_run, started_at=_now_iso())

    if registry is None:
        result.status = "skipped"
        result.summary = {"reason": "no ArtifactRegistry provided"}
        result.finished_at = _now_iso()
        return result

    try:
        all_arts = registry.search(limit=1000)
        promotion_ready = []

        for art in all_arts:
            if (
                art.stability == "candidate"
                and art.quality_score >= 0.8
                and art.quarantine_weight >= 0.7
            ):
                promotion_ready.append({
                    "artifact_id": art.artifact_id,
                    "quality_score": round(art.quality_score, 4),
                    "quarantine_weight": art.quarantine_weight,
                    "title": art.title,
                })

        result.summary = {
            "total_scanned": len(all_arts),
            "promotion_ready": len(promotion_ready),
            "candidates": promotion_ready[:20],  # cap for readability
        }
        result.status = "completed"
    except Exception as exc:
        result.status = "error"
        result.errors.append(str(exc))

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Daemon runner
# ---------------------------------------------------------------------------

STAGE_MAP = {
    "manifest_audit": stage_manifest_audit,
    "retention_enforce": stage_retention_enforce,
    "kb_governance": stage_kb_governance,
    "memory_governance": stage_memory_governance,
    "review_governance": stage_review_governance,
    "promotion_check": stage_promotion_check,
}


def run_daemon(
    *,
    stages: list[str] | None = None,
    dry_run: bool = True,
    artifacts_root: Path | None = None,
    registry: Any | None = None,
    pruner: Any | None = None,
    memory_mgr: Any | None = None,
    output_dir: Path | None = None,
    audit_path: Path | None = None,
) -> DaemonResult:
    """Run governance daemon stages.

    Args:
        stages: List of stage names to run (default: all)
        dry_run: If True, observe-only
        artifacts_root: Path to artifacts/jobs/
        registry: ArtifactRegistry instance (optional)
        pruner: KBPruner instance (optional)
        memory_mgr: MemoryManager instance (optional)
        output_dir: Directory to write run results
        audit_path: JSONL audit file path
    """
    run_stages = stages or STAGE_NAMES
    effective_root = artifacts_root or DEFAULT_ARTIFACTS_ROOT
    effective_audit = audit_path

    daemon_result = DaemonResult(started_at=_now_iso(), dry_run=dry_run)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        if not effective_audit:
            effective_audit = output_dir / f"governance_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"

    for stage_name in run_stages:
        if stage_name not in STAGE_MAP:
            logger.warning("Unknown stage: %s", stage_name)
            continue

        logger.info("Running stage: %s (dry_run=%s)", stage_name, dry_run)

        if stage_name == "manifest_audit":
            sr = stage_manifest_audit(effective_root, dry_run=dry_run, audit_path=effective_audit)
        elif stage_name == "retention_enforce":
            sr = stage_retention_enforce(effective_root, dry_run=dry_run, audit_path=effective_audit)
        elif stage_name == "kb_governance":
            sr = stage_kb_governance(registry, pruner, dry_run=dry_run, audit_path=effective_audit)
        elif stage_name == "memory_governance":
            sr = stage_memory_governance(memory_mgr, dry_run=dry_run, audit_path=effective_audit)
        elif stage_name == "review_governance":
            sr = stage_review_governance(registry, dry_run=dry_run, audit_path=effective_audit)
        elif stage_name == "promotion_check":
            sr = stage_promotion_check(registry, dry_run=dry_run, audit_path=effective_audit)
        else:
            continue

        daemon_result.stages.append(sr)
        logger.info("Stage %s: %s", stage_name, sr.status)

    daemon_result.finished_at = _now_iso()

    # Write results
    if output_dir:
        result_path = output_dir / f"governance_run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        result_path.write_text(
            json.dumps(daemon_result.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Results written to %s", result_path)

    return daemon_result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Artifact governance daemon")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Observe-only (default)")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--stage", nargs="*", help=f"Stages to run (default: all). Options: {', '.join(STAGE_NAMES)}")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for results")
    parser.add_argument("--artifacts-root", default=str(DEFAULT_ARTIFACTS_ROOT), help="Path to artifacts/jobs/")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    dry_run = not args.apply

    t0 = time.monotonic()
    result = run_daemon(
        stages=args.stage,
        dry_run=dry_run,
        artifacts_root=Path(args.artifacts_root),
        output_dir=Path(args.output_dir),
    )
    elapsed = time.monotonic() - t0

    output = result.to_dict()
    output["elapsed_seconds"] = round(elapsed, 2)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
