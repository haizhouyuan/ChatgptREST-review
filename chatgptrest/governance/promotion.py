"""Controlled promotion for artifact governance.

Phase 3 of artifact governance blueprint v2.

Implements the controlled promotion gate:
- Verifies artifact meets criteria before promotion
- Enforces state machine transitions
- Audit trail for all promotions
- CLI for interactive and batch promotion

Promotion criteria (configurable):
- quality_score >= threshold (default 0.8)
- quarantine_weight >= 0.7 (not hypothetical/blocked)
- stability == "candidate" (ready for promotion)
- age >= min_candidate_days (default 7)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "PromotionGate",
    "PromotionDecision",
    "promote_artifact",
    "batch_promote",
]


@dataclass
class PromotionDecision:
    """Result of a promotion gate check."""
    artifact_id: str = ""
    eligible: bool = False
    promoted: bool = False
    reason: str = ""
    quality_score: float = 0.0
    quarantine_weight: float = 0.0
    stability: str = ""
    candidate_age_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "eligible": self.eligible,
            "promoted": self.promoted,
            "reason": self.reason,
            "quality_score": round(self.quality_score, 4),
            "quarantine_weight": self.quarantine_weight,
            "stability": self.stability,
            "candidate_age_days": self.candidate_age_days,
        }


class PromotionGate:
    """Gate that controls artifact promotion from candidate → approved.

    Configurable thresholds. Default: quality >= 0.8, weight >= 0.7,
    candidate for >= 7 days.
    """

    def __init__(
        self,
        *,
        quality_threshold: float = 0.8,
        min_quarantine_weight: float = 0.7,
        min_candidate_days: int = 7,
    ):
        self.quality_threshold = quality_threshold
        self.min_quarantine_weight = min_quarantine_weight
        self.min_candidate_days = min_candidate_days

    def check(self, artifact: Any) -> PromotionDecision:
        """Check if an artifact meets promotion criteria.

        Args:
            artifact: An Artifact object (with stability, quality_score,
                      quarantine_weight, created_at attributes)

        Returns:
            PromotionDecision with eligibility and reason.
        """
        decision = PromotionDecision(
            artifact_id=artifact.artifact_id,
            quality_score=artifact.quality_score,
            quarantine_weight=artifact.quarantine_weight,
            stability=artifact.stability,
        )

        # Must be in candidate state
        if artifact.stability != "candidate":
            decision.reason = f"not candidate (current: {artifact.stability})"
            return decision

        # Quality check
        if artifact.quality_score < self.quality_threshold:
            decision.reason = (
                f"quality {artifact.quality_score:.2f} < {self.quality_threshold}"
            )
            return decision

        # Quarantine weight check
        if artifact.quarantine_weight < self.min_quarantine_weight:
            decision.reason = (
                f"quarantine weight {artifact.quarantine_weight:.2f} < {self.min_quarantine_weight}"
            )
            return decision

        # Age check
        if artifact.created_at:
            try:
                created = datetime.fromisoformat(artifact.created_at)
                age = (datetime.now(timezone.utc) - created).days
                decision.candidate_age_days = age
                if age < self.min_candidate_days:
                    decision.reason = (
                        f"candidate age {age}d < {self.min_candidate_days}d"
                    )
                    return decision
            except ValueError:
                decision.reason = "invalid created_at timestamp"
                return decision

        decision.eligible = True
        decision.reason = "meets all criteria"
        return decision


def promote_artifact(
    registry: Any,
    artifact_id: str,
    *,
    gate: PromotionGate | None = None,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> PromotionDecision:
    """Promote a single artifact through the gate.

    Args:
        registry: ArtifactRegistry instance
        artifact_id: ID of the artifact to promote
        gate: PromotionGate with thresholds (default: standard gate)
        dry_run: If True, check eligibility but don't promote
        audit_path: Optional JSONL audit file path

    Returns:
        PromotionDecision with result.
    """
    gate = gate or PromotionGate()

    art = registry.get(artifact_id)
    if art is None:
        return PromotionDecision(
            artifact_id=artifact_id,
            reason="artifact not found",
        )

    decision = gate.check(art)

    if decision.eligible and not dry_run:
        try:
            registry.transition_stability(artifact_id, "approved")
            decision.promoted = True
            logger.info("Promoted %s to approved", artifact_id)
        except Exception as exc:
            decision.promoted = False
            decision.reason = f"transition failed: {exc}"

    # Audit trail
    if audit_path:
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("a", encoding="utf-8") as f:
                record = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "op": "promotion",
                    **decision.to_dict(),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write audit")

    return decision


def batch_promote(
    registry: Any,
    *,
    gate: PromotionGate | None = None,
    dry_run: bool = True,
    limit: int = 100,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    """Promote all eligible artifacts in batch.

    Args:
        registry: ArtifactRegistry instance
        gate: PromotionGate with thresholds
        dry_run: If True, check but don't promote
        limit: Max artifacts to process
        audit_path: Optional JSONL audit file

    Returns:
        Summary dict with counts and details.
    """
    gate = gate or PromotionGate()
    candidates = registry.search(limit=limit)

    results = {
        "total_scanned": len(candidates),
        "eligible": 0,
        "promoted": 0,
        "ineligible": 0,
        "errors": 0,
        "dry_run": dry_run,
        "decisions": [],
    }

    for art in candidates:
        try:
            decision = promote_artifact(
                registry, art.artifact_id,
                gate=gate, dry_run=dry_run, audit_path=audit_path,
            )
            results["decisions"].append(decision.to_dict())

            if decision.eligible:
                results["eligible"] += 1
                if decision.promoted:
                    results["promoted"] += 1
            else:
                results["ineligible"] += 1

        except Exception as exc:
            results["errors"] += 1
            results["decisions"].append({
                "artifact_id": art.artifact_id,
                "error": str(exc),
            })

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Artifact promotion CLI")
    sub = parser.add_subparsers(dest="cmd")

    # Check single artifact
    check_p = sub.add_parser("check", help="Check promotion eligibility")
    check_p.add_argument("artifact_id", help="Artifact ID to check")
    check_p.add_argument("--db", required=True, help="Path to KB registry DB")

    # Batch promote
    batch_p = sub.add_parser("batch", help="Batch promote eligible artifacts")
    batch_p.add_argument("--db", required=True, help="Path to KB registry DB")
    batch_p.add_argument("--apply", action="store_true", help="Actually promote")
    batch_p.add_argument("--limit", type=int, default=100, help="Max to process")
    batch_p.add_argument("--quality", type=float, default=0.8, help="Min quality")
    batch_p.add_argument("--audit", help="Audit JSONL path")

    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chatgptrest.kb.registry import ArtifactRegistry

    if args.cmd == "check":
        reg = ArtifactRegistry(args.db)
        decision = promote_artifact(reg, args.artifact_id, dry_run=True)
        print(json.dumps(decision.to_dict(), indent=2))
        reg.close()

    elif args.cmd == "batch":
        reg = ArtifactRegistry(args.db)
        gate = PromotionGate(quality_threshold=args.quality)
        audit = Path(args.audit) if args.audit else None
        result = batch_promote(
            reg, gate=gate, dry_run=not args.apply,
            limit=args.limit, audit_path=audit,
        )
        print(json.dumps(result, indent=2))
        reg.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
