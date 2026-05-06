"""Tests for ops/artifact_governance_daemon.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ops.artifact_governance_daemon import (
    DaemonResult,
    StageResult,
    run_daemon,
    stage_manifest_audit,
    stage_retention_enforce,
    stage_kb_governance,
    stage_memory_governance,
    stage_review_governance,
    stage_promotion_check,
)


# ---------------------------------------------------------------------------
# Stage 1: manifest_audit
# ---------------------------------------------------------------------------

class TestManifestAudit:
    def test_handles_missing_root(self) -> None:
        r = stage_manifest_audit(Path("/nonexistent"), dry_run=True)
        assert r.status == "error"

    def test_reports_missing_manifests(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        d = jobs / "job-1"
        d.mkdir()
        r = stage_manifest_audit(jobs, dry_run=True)
        assert r.status == "completed"
        assert r.summary["missing"] == 1
        assert r.summary["coverage_pct"] == 0.0

    def test_validates_existing_manifests(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        d = jobs / "job-1"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({
            "artifact_id": "test",
            "artifact_type": "runtime_evidence",
            "canonical_path": "test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "artifact-manifest-v1",
        }))
        r = stage_manifest_audit(jobs, dry_run=True)
        assert r.summary["valid"] == 1
        assert r.summary["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Stage 3: kb_governance
# ---------------------------------------------------------------------------

class TestKBGovernance:
    def test_skips_without_registry(self) -> None:
        r = stage_kb_governance(None, dry_run=True)
        assert r.status == "skipped"

    def test_runs_with_registry(self) -> None:
        reg = MagicMock()
        reg.search.return_value = []
        r = stage_kb_governance(reg, dry_run=True)
        assert r.status == "completed"


# ---------------------------------------------------------------------------
# Stage 4: memory_governance
# ---------------------------------------------------------------------------

class TestMemoryGovernance:
    def test_skips_without_manager(self) -> None:
        r = stage_memory_governance(None, dry_run=True)
        assert r.status == "skipped"

    def test_runs_with_manager(self) -> None:
        mgr = MagicMock()
        mgr.count_by_tier.return_value = {"working": 5}
        mgr.get_episodic.return_value = []
        r = stage_memory_governance(mgr, dry_run=True)
        assert r.status == "completed"


# ---------------------------------------------------------------------------
# Stage 5: review_governance
# ---------------------------------------------------------------------------

class TestReviewGovernance:
    def test_skips_without_registry(self) -> None:
        r = stage_review_governance(None, dry_run=True)
        assert r.status == "skipped"

    def test_finds_overdue_reviews(self) -> None:
        art = MagicMock()
        art.review_due = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        art.stability = "approved"
        art.created_at = datetime.now(timezone.utc).isoformat()
        reg = MagicMock()
        reg.search.return_value = [art]
        r = stage_review_governance(reg, dry_run=True)
        assert r.summary["overdue_reviews"] == 1


# ---------------------------------------------------------------------------
# Stage 6: promotion_check
# ---------------------------------------------------------------------------

class TestPromotionCheck:
    def test_skips_without_registry(self) -> None:
        r = stage_promotion_check(None, dry_run=True)
        assert r.status == "skipped"

    def test_finds_promotion_ready(self) -> None:
        art = MagicMock()
        art.stability = "candidate"
        art.quality_score = 0.9
        art.quarantine_weight = 1.0
        art.artifact_id = "ready-1"
        art.title = "test"
        reg = MagicMock()
        reg.search.return_value = [art]
        r = stage_promotion_check(reg, dry_run=True)
        assert r.summary["promotion_ready"] == 1


# ---------------------------------------------------------------------------
# run_daemon
# ---------------------------------------------------------------------------

class TestRunDaemon:
    def test_runs_all_stages(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        result = run_daemon(dry_run=True, artifacts_root=jobs)
        assert isinstance(result, DaemonResult)
        assert len(result.stages) == 6

    def test_runs_single_stage(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        result = run_daemon(stages=["manifest_audit"], dry_run=True, artifacts_root=jobs)
        assert len(result.stages) == 1
        assert result.stages[0].stage == "manifest_audit"

    def test_writes_output(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        out = tmp_path / "output"
        result = run_daemon(dry_run=True, artifacts_root=jobs, output_dir=out)
        assert out.exists()
        files = list(out.glob("governance_run_*.json"))
        assert len(files) == 1

    def test_to_dict(self, tmp_path: Path) -> None:
        jobs = tmp_path / "jobs"
        jobs.mkdir()
        result = run_daemon(dry_run=True, artifacts_root=jobs)
        d = result.to_dict()
        assert "stages" in d
        assert "total_errors" in d
