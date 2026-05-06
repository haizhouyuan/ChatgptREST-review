"""Batch wrappers for weekly governance operations.

Blueprint v2 §12 (Readiness Checklist) identified these primitives that
can be called directly AND the batch enumerations needed around them.

Each wrapper:
- Accepts dry_run=True by default (observe-only)
- Returns a structured result dict
- Logs actions to a JSONL file for audit
- Handles errors per-item without aborting the whole batch

Phase 1a of artifact governance blueprint v2.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "BatchResult",
    "batch_kb_quality_rescore",
    "batch_kb_stability_transition",
    "batch_kb_prune",
    "batch_memory_expire",
    "batch_memory_consolidate",
    "batch_retention_enforce",
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    """Result of a batch governance operation."""
    operation: str = ""
    dry_run: bool = True
    started_at: str = ""
    finished_at: str = ""
    total_candidates: int = 0
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_candidates": self.total_candidates,
            "processed": self.processed,
            "skipped": self.skipped,
            "errors": self.errors,
            "details": self.details,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(audit_path: Path | None, record: dict[str, Any]) -> None:
    """Append a single record to the audit JSONL file."""
    if audit_path is None:
        return
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.exception("Failed to write audit record to %s", audit_path)


# ---------------------------------------------------------------------------
# 1. KB Quality Rescore
# ---------------------------------------------------------------------------

def batch_kb_quality_rescore(
    registry: Any,  # ArtifactRegistry
    *,
    dry_run: bool = True,
    limit: int = 500,
    min_age_days: int = 0,
    audit_path: Path | None = None,
) -> BatchResult:
    """Rescore quality for all artifacts in the KB registry.

    Enumerates all artifacts, recomputes quality_score, and updates
    those whose score changed.

    Args:
        registry: ArtifactRegistry instance
        dry_run: If True, compute but don't write scores
        limit: Max artifacts to process
        min_age_days: Only rescore artifacts older than N days
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(operation="kb_quality_rescore", dry_run=dry_run, started_at=_now_iso())

    # Enumerate all artifacts
    candidates = registry.search(limit=limit)
    result.total_candidates = len(candidates)

    for art in candidates:
        try:
            # Check age filter
            if min_age_days > 0 and art.modified_at:
                try:
                    mod = datetime.fromisoformat(art.modified_at)
                    age = (datetime.now(timezone.utc) - mod).days
                    if age < min_age_days:
                        result.skipped += 1
                        continue
                except ValueError:
                    pass

            old_score = art.quality_score
            new_score = registry.compute_quality(art)

            if abs(new_score - old_score) < 0.001:
                result.skipped += 1
                continue

            detail = {
                "artifact_id": art.artifact_id,
                "old_score": round(old_score, 4),
                "new_score": round(new_score, 4),
                "action": "rescore",
            }

            if not dry_run:
                registry.update_quality(art.artifact_id)
                detail["applied"] = True
            else:
                detail["applied"] = False

            result.details.append(detail)
            result.processed += 1
            _append_audit(audit_path, {"ts": _now_iso(), "op": "rescore", **detail})

        except Exception as exc:
            result.errors += 1
            result.details.append({
                "artifact_id": art.artifact_id,
                "error": str(exc),
            })

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# 2. KB Stability Transition
# ---------------------------------------------------------------------------

def batch_kb_stability_transition(
    registry: Any,  # ArtifactRegistry
    *,
    dry_run: bool = True,
    quality_threshold: float = 0.6,
    min_age_days: int = 7,
    limit: int = 200,
    audit_path: Path | None = None,
) -> BatchResult:
    """Transition artifact stability based on quality and age.

    Rules:
    - draft → candidate: quality_score >= threshold AND age >= min_age_days
    - candidate → approved: quality_score >= 0.8 AND has been candidate for >= 7 days
    - approved → deprecated: quality_score < 0.3 (quality degraded)

    Args:
        registry: ArtifactRegistry instance
        dry_run: If True, identify transitions but don't apply
        quality_threshold: Min quality for draft → candidate
        min_age_days: Min age for draft → candidate
        limit: Max artifacts to process
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(operation="kb_stability_transition", dry_run=dry_run, started_at=_now_iso())

    candidates = registry.search(limit=limit)
    result.total_candidates = len(candidates)

    for art in candidates:
        try:
            transition_to = None
            reason = ""

            if art.stability == "draft":
                # draft → candidate: good quality + minimum age
                age_ok = False
                if art.created_at:
                    try:
                        created = datetime.fromisoformat(art.created_at)
                        age = (datetime.now(timezone.utc) - created).days
                        age_ok = age >= min_age_days
                    except ValueError:
                        pass
                if art.quality_score >= quality_threshold and age_ok:
                    transition_to = "candidate"
                    reason = f"quality={art.quality_score:.2f}≥{quality_threshold}, age≥{min_age_days}d"

            elif art.stability == "candidate":
                # candidate → approved: high quality
                if art.quality_score >= 0.8:
                    transition_to = "approved"
                    reason = f"quality={art.quality_score:.2f}≥0.8"
                elif art.quality_score < 0.3:
                    # Reject back to draft
                    transition_to = "draft"
                    reason = f"quality={art.quality_score:.2f}<0.3 (rejected)"

            elif art.stability == "approved":
                # approved → deprecated: quality degraded
                if art.quality_score < 0.3:
                    transition_to = "deprecated"
                    reason = f"quality={art.quality_score:.2f}<0.3 (degraded)"

            if transition_to is None:
                result.skipped += 1
                continue

            detail = {
                "artifact_id": art.artifact_id,
                "from": art.stability,
                "to": transition_to,
                "reason": reason,
                "quality_score": round(art.quality_score, 4),
            }

            if not dry_run:
                registry.transition_stability(art.artifact_id, transition_to)
                detail["applied"] = True
            else:
                detail["applied"] = False

            result.details.append(detail)
            result.processed += 1
            _append_audit(audit_path, {"ts": _now_iso(), "op": "stability_transition", **detail})

        except Exception as exc:
            result.errors += 1
            result.details.append({
                "artifact_id": art.artifact_id,
                "error": str(exc),
            })

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# 3. KB Prune
# ---------------------------------------------------------------------------

def batch_kb_prune(
    pruner: Any,  # KBPruner
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> BatchResult:
    """Run the KBPruner to clean up low-quality or duplicate artifacts.

    Args:
        pruner: KBPruner instance
        dry_run: If True, only report what would be pruned
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(operation="kb_prune", dry_run=dry_run, started_at=_now_iso())

    try:
        if dry_run:
            # KBPruner.run() is destructive, so in dry_run we just report readiness
            result.details.append({"status": "dry_run", "message": "KBPruner.run() would execute"})
            result.skipped = 1
        else:
            prune_result = pruner.run()
            result.processed = sum(prune_result.values()) if isinstance(prune_result, dict) else 0
            result.details.append({"prune_result": prune_result})
            _append_audit(audit_path, {"ts": _now_iso(), "op": "kb_prune", "result": prune_result})
    except Exception as exc:
        result.errors = 1
        result.details.append({"error": str(exc)})

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# 4. Memory Expire/Consolidate
# ---------------------------------------------------------------------------

def batch_memory_expire(
    memory_mgr: Any,  # MemoryManager
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> BatchResult:
    """Expire stale memory records using MemoryManager.expire_records().

    Args:
        memory_mgr: MemoryManager instance
        dry_run: If True, only report what would be expired
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(operation="memory_expire", dry_run=dry_run, started_at=_now_iso())

    try:
        if dry_run:
            counts = memory_mgr.count_by_tier()
            result.total_candidates = sum(counts.values())
            result.details.append({"tier_counts": counts, "status": "dry_run"})
            result.skipped = result.total_candidates
        else:
            expired = memory_mgr.expire_records()
            result.processed = expired
            result.details.append({"expired_count": expired})
            _append_audit(audit_path, {"ts": _now_iso(), "op": "memory_expire", "expired": expired})
    except Exception as exc:
        result.errors = 1
        result.details.append({"error": str(exc)})

    result.finished_at = _now_iso()
    return result


def batch_memory_consolidate(
    memory_mgr: Any,  # MemoryManager
    *,
    dry_run: bool = True,
    source_tier: str = "episodic",
    target_tier: str = "semantic",
    min_access_count: int = 3,
    limit: int = 100,
    audit_path: Path | None = None,
) -> BatchResult:
    """Consolidate memory records from episodic → semantic tier.

    Identifies episodic records that have been accessed multiple times
    (indicating importance) and promotes them to semantic tier.

    Args:
        memory_mgr: MemoryManager instance
        dry_run: If True, only identify candidates
        source_tier: Source tier to scan (default: episodic)
        target_tier: Target tier to promote to (default: semantic)
        min_access_count: Min access count to qualify for promotion
        limit: Max records to process
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(
        operation="memory_consolidate",
        dry_run=dry_run,
        started_at=_now_iso(),
    )

    try:
        # Get episodic records
        records = memory_mgr.get_episodic(limit=limit)
        result.total_candidates = len(records)

        for rec in records:
            rec_dict = rec if isinstance(rec, dict) else (rec.to_dict() if hasattr(rec, "to_dict") else {})
            record_id = rec_dict.get("record_id", "")
            access_count = rec_dict.get("access_count", 0)

            if access_count < min_access_count:
                result.skipped += 1
                continue

            detail = {
                "record_id": record_id,
                "access_count": access_count,
                "from_tier": source_tier,
                "to_tier": target_tier,
            }

            if not dry_run:
                try:
                    memory_mgr.promote(record_id, target_tier)
                    detail["applied"] = True
                except Exception as exc:
                    detail["error"] = str(exc)
                    result.errors += 1
                    result.details.append(detail)
                    continue
            else:
                detail["applied"] = False

            result.details.append(detail)
            result.processed += 1
            _append_audit(audit_path, {"ts": _now_iso(), "op": "consolidate", **detail})

    except Exception as exc:
        result.errors += 1
        result.details.append({"error": str(exc)})

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# 5. Retention Enforcement
# ---------------------------------------------------------------------------

def batch_retention_enforce(
    artifacts_root: Path,
    *,
    dry_run: bool = True,
    max_hot_dirs: int = 2000,
    max_hot_bytes: int = 5_000_000_000,   # 5 GB
    archive_age_days: int = 30,
    audit_path: Path | None = None,
) -> BatchResult:
    """Enforce retention policies on job artifact directories.

    Budget-driven triggers (blueprint v2 §10.2):
    - Directory count exceeds max_hot_dirs
    - Total size exceeds max_hot_bytes
    - Individual dirs older than archive_age_days

    In archive mode, marks directories for archive by writing
    a `_retention_archived.json` marker file.

    Args:
        artifacts_root: Path to artifacts/jobs/ directory
        dry_run: If True, only report what would be archived
        max_hot_dirs: Max number of hot directories before triggering
        max_hot_bytes: Max total bytes before triggering
        archive_age_days: Days after which dirs become archive candidates
        audit_path: Optional JSONL audit file path
    """
    result = BatchResult(operation="retention_enforce", dry_run=dry_run, started_at=_now_iso())

    jobs_root = Path(artifacts_root)
    if not jobs_root.exists():
        result.details.append({"error": f"artifacts root not found: {jobs_root}"})
        result.errors = 1
        result.finished_at = _now_iso()
        return result

    # Scan job directories
    try:
        job_dirs = sorted(
            (d for d in jobs_root.iterdir() if d.is_dir() and not d.name.startswith(".")),
            key=lambda d: d.stat().st_mtime,
        )
    except Exception as exc:
        result.errors = 1
        result.details.append({"error": f"scan failed: {exc}"})
        result.finished_at = _now_iso()
        return result

    result.total_candidates = len(job_dirs)
    total_bytes = 0
    now = datetime.now(timezone.utc)
    archive_candidates: list[tuple[Path, str]] = []

    for d in job_dirs:
        try:
            # Skip already archived
            if (d / "_retention_archived.json").exists():
                continue

            stat = d.stat()
            dir_age_days = (now - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)).days

            # Estimate dir size (sum of file sizes)
            dir_size = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
            total_bytes += dir_size

            if dir_age_days >= archive_age_days:
                archive_candidates.append((d, f"age={dir_age_days}d≥{archive_age_days}d"))
        except Exception:
            continue

    # Budget triggers
    budget_triggered = False
    budget_reason = ""
    if len(job_dirs) > max_hot_dirs:
        budget_triggered = True
        budget_reason = f"dir_count={len(job_dirs)}>{max_hot_dirs}"
    elif total_bytes > max_hot_bytes:
        budget_triggered = True
        budget_reason = f"total_bytes={total_bytes}>{max_hot_bytes}"

    result.details.append({
        "scan": {
            "total_dirs": len(job_dirs),
            "total_bytes": total_bytes,
            "age_candidates": len(archive_candidates),
            "budget_triggered": budget_triggered,
            "budget_reason": budget_reason,
        }
    })

    # If budget triggered, add oldest dirs until under budget
    if budget_triggered:
        overflow = max(0, len(job_dirs) - max_hot_dirs)
        for d, reason in archive_candidates[:overflow + len(archive_candidates)]:
            if (d, reason) not in archive_candidates:
                archive_candidates.append((d, f"budget: {budget_reason}"))

    # Process archive candidates
    for d, reason in archive_candidates:
        detail = {
            "dir": d.name,
            "reason": reason,
        }

        if not dry_run:
            try:
                marker = {
                    "archived_at": _now_iso(),
                    "reason": reason,
                    "retention_class": "archive_only",
                }
                (d / "_retention_archived.json").write_text(
                    json.dumps(marker, indent=2) + "\n", encoding="utf-8"
                )
                detail["applied"] = True
            except Exception as exc:
                detail["error"] = str(exc)
                result.errors += 1
        else:
            detail["applied"] = False

        result.details.append(detail)
        result.processed += 1
        _append_audit(audit_path, {"ts": _now_iso(), "op": "retention_archive", **detail})

    result.finished_at = _now_iso()
    return result
