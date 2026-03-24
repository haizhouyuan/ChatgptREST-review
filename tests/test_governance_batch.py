"""Tests for chatgptrest.governance.batch_wrappers."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chatgptrest.governance.batch_wrappers import (
    BatchResult,
    batch_kb_quality_rescore,
    batch_kb_stability_transition,
    batch_kb_prune,
    batch_memory_expire,
    batch_memory_consolidate,
    batch_retention_enforce,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_artifact(
    artifact_id: str = "art-1",
    quality_score: float = 0.5,
    stability: str = "draft",
    created_at: str = "",
    modified_at: str = "",
) -> MagicMock:
    art = MagicMock()
    art.artifact_id = artifact_id
    art.quality_score = quality_score
    art.stability = stability
    art.created_at = created_at or (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    art.modified_at = modified_at or (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    return art


def _make_registry(artifacts: list | None = None) -> MagicMock:
    reg = MagicMock()
    arts = artifacts or [_make_artifact()]
    reg.search.return_value = arts
    reg.compute_quality.return_value = 0.75
    return reg


# ---------------------------------------------------------------------------
# batch_kb_quality_rescore
# ---------------------------------------------------------------------------

class TestBatchKBQualityRescore:
    def test_dry_run_computes_but_doesnt_apply(self) -> None:
        art = _make_artifact(quality_score=0.3)
        reg = _make_registry([art])
        reg.compute_quality.return_value = 0.7

        result = batch_kb_quality_rescore(reg, dry_run=True)
        assert result.processed == 1
        assert result.dry_run is True
        reg.update_quality.assert_not_called()
        assert result.details[0]["applied"] is False

    def test_apply_updates_scores(self) -> None:
        art = _make_artifact(quality_score=0.3)
        reg = _make_registry([art])
        reg.compute_quality.return_value = 0.7

        result = batch_kb_quality_rescore(reg, dry_run=False)
        assert result.processed == 1
        reg.update_quality.assert_called_once_with("art-1")
        assert result.details[0]["applied"] is True

    def test_skips_unchanged_scores(self) -> None:
        art = _make_artifact(quality_score=0.5)
        reg = _make_registry([art])
        reg.compute_quality.return_value = 0.5  # same

        result = batch_kb_quality_rescore(reg, dry_run=True)
        assert result.skipped == 1
        assert result.processed == 0

    def test_writes_audit_log(self, tmp_path: Path) -> None:
        art = _make_artifact(quality_score=0.3)
        reg = _make_registry([art])
        reg.compute_quality.return_value = 0.7
        audit = tmp_path / "audit.jsonl"

        batch_kb_quality_rescore(reg, dry_run=False, audit_path=audit)
        lines = audit.read_text().strip().split("\n")
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["op"] == "rescore"


# ---------------------------------------------------------------------------
# batch_kb_stability_transition
# ---------------------------------------------------------------------------

class TestBatchKBStabilityTransition:
    def test_draft_to_candidate(self) -> None:
        art = _make_artifact(quality_score=0.7, stability="draft")
        reg = _make_registry([art])

        result = batch_kb_stability_transition(reg, dry_run=True, quality_threshold=0.6)
        assert result.processed == 1
        assert result.details[0]["to"] == "candidate"
        reg.transition_stability.assert_not_called()

    def test_candidate_to_approved(self) -> None:
        art = _make_artifact(quality_score=0.85, stability="candidate")
        reg = _make_registry([art])

        result = batch_kb_stability_transition(reg, dry_run=False)
        assert result.processed == 1
        reg.transition_stability.assert_called_once_with("art-1", "approved")

    def test_candidate_rejected_to_draft(self) -> None:
        art = _make_artifact(quality_score=0.2, stability="candidate")
        reg = _make_registry([art])

        result = batch_kb_stability_transition(reg, dry_run=True)
        assert result.processed == 1
        assert result.details[0]["to"] == "draft"

    def test_approved_to_deprecated(self) -> None:
        art = _make_artifact(quality_score=0.2, stability="approved")
        reg = _make_registry([art])

        result = batch_kb_stability_transition(reg, dry_run=True)
        assert result.processed == 1
        assert result.details[0]["to"] == "deprecated"

    def test_skips_when_no_transition(self) -> None:
        art = _make_artifact(quality_score=0.5, stability="draft")
        reg = _make_registry([art])

        result = batch_kb_stability_transition(reg, dry_run=True, quality_threshold=0.8)
        assert result.skipped == 1


# ---------------------------------------------------------------------------
# batch_kb_prune
# ---------------------------------------------------------------------------

class TestBatchKBPrune:
    def test_dry_run_doesnt_prune(self) -> None:
        pruner = MagicMock()
        result = batch_kb_prune(pruner, dry_run=True)
        assert result.skipped == 1
        pruner.run.assert_not_called()

    def test_apply_runs_pruner(self) -> None:
        pruner = MagicMock()
        pruner.run.return_value = {"pruned": 5, "merged": 2}
        result = batch_kb_prune(pruner, dry_run=False)
        assert result.processed == 7
        pruner.run.assert_called_once()


# ---------------------------------------------------------------------------
# batch_memory_expire
# ---------------------------------------------------------------------------

class TestBatchMemoryExpire:
    def test_dry_run_reports_counts(self) -> None:
        mgr = MagicMock()
        mgr.count_by_tier.return_value = {"working": 10, "episodic": 50, "semantic": 30}
        result = batch_memory_expire(mgr, dry_run=True)
        assert result.total_candidates == 90
        mgr.expire_records.assert_not_called()

    def test_apply_expires(self) -> None:
        mgr = MagicMock()
        mgr.expire_records.return_value = 12
        result = batch_memory_expire(mgr, dry_run=False)
        assert result.processed == 12


# ---------------------------------------------------------------------------
# batch_memory_consolidate
# ---------------------------------------------------------------------------

class TestBatchMemoryConsolidate:
    def test_dry_run_identifies_candidates(self) -> None:
        mgr = MagicMock()
        mgr.get_episodic.return_value = [
            {"record_id": "r1", "access_count": 5},
            {"record_id": "r2", "access_count": 1},
        ]
        result = batch_memory_consolidate(mgr, dry_run=True, min_access_count=3)
        assert result.processed == 1
        assert result.skipped == 1
        mgr.promote.assert_not_called()

    def test_apply_promotes(self) -> None:
        mgr = MagicMock()
        mgr.get_episodic.return_value = [
            {"record_id": "r1", "access_count": 5},
        ]
        result = batch_memory_consolidate(mgr, dry_run=False, min_access_count=3)
        assert result.processed == 1
        mgr.promote.assert_called_once()


# ---------------------------------------------------------------------------
# batch_retention_enforce
# ---------------------------------------------------------------------------

class TestBatchRetentionEnforce:
    def test_dry_run_scans_dirs(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        for i in range(3):
            d = jobs / f"job-{i}"
            d.mkdir()
            (d / "request.json").write_text("{}")

        result = batch_retention_enforce(jobs, dry_run=True, archive_age_days=0)
        assert result.total_candidates == 3
        # All are age=0 which is >= 0, so all candidates
        assert result.processed == 3
        # But nothing applied
        for detail in result.details:
            if "applied" in detail:
                assert detail["applied"] is False

    def test_apply_writes_markers(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        d = jobs / "old-job"
        d.mkdir()
        (d / "request.json").write_text("{}")

        result = batch_retention_enforce(jobs, dry_run=False, archive_age_days=0)
        assert (d / "_retention_archived.json").exists()
        marker = json.loads((d / "_retention_archived.json").read_text())
        assert marker["retention_class"] == "archive_only"

    def test_skips_already_archived(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        d = jobs / "archived-job"
        d.mkdir()
        (d / "_retention_archived.json").write_text("{}")

        result = batch_retention_enforce(jobs, dry_run=True, archive_age_days=0)
        assert result.processed == 0

    def test_nonexistent_root(self) -> None:
        result = batch_retention_enforce(Path("/nonexistent"), dry_run=True)
        assert result.errors == 1
