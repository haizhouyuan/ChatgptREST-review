"""Tests for ops/manifest_backfill.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ops.manifest_backfill import backfill


class TestBackfill:
    def _make_jobs(self, tmp_path: Path) -> Path:
        """Create a jobs subdir under a mock repo root."""
        jobs = tmp_path / "artifacts" / "jobs"
        jobs.mkdir(parents=True)
        return jobs

    def _make_job_dir(self, jobs_dir: Path, name: str, with_request: bool = True) -> Path:
        d = jobs_dir / name
        d.mkdir()
        if with_request:
            (d / "request.json").write_text(json.dumps({
                "kind": "chatgpt_web.ask",
                "created_at": "2026-03-16T09:00:00+00:00",
            }))
        return d

    def test_count_only(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        self._make_job_dir(jobs, "job-1")
        self._make_job_dir(jobs, "job-2")
        result = backfill(jobs, repo_root=tmp_path, count_only=True)
        assert result["total_job_dirs"] == 2
        assert result["needs_manifest"] == 2

    def test_dry_run_no_file_created(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        d = self._make_job_dir(jobs, "job-1")
        result = backfill(jobs, repo_root=tmp_path, dry_run=True)
        assert result["created"] == 1
        assert not (d / "manifest.json").exists()

    def test_apply_creates_manifest(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        d = self._make_job_dir(jobs, "job-1")
        result = backfill(jobs, repo_root=tmp_path, dry_run=False)
        assert result["created"] == 1
        assert (d / "manifest.json").exists()
        manifest = json.loads((d / "manifest.json").read_text())
        assert manifest["artifact_id"] == "job-1"
        assert manifest["schema_version"] == "artifact-manifest-v1"

    def test_skip_existing(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        d = self._make_job_dir(jobs, "job-1")
        (d / "manifest.json").write_text("{}")
        result = backfill(jobs, repo_root=tmp_path, dry_run=False)
        assert result["skipped"] == 1
        assert result["created"] == 0

    def test_force_overwrites(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        d = self._make_job_dir(jobs, "job-1")
        (d / "manifest.json").write_text("{}")
        result = backfill(jobs, repo_root=tmp_path, dry_run=False, force=True)
        assert result["created"] == 1
        manifest = json.loads((d / "manifest.json").read_text())
        assert manifest["schema_version"] == "artifact-manifest-v1"

    def test_limit(self, tmp_path: Path) -> None:
        jobs = self._make_jobs(tmp_path)
        for i in range(5):
            self._make_job_dir(jobs, f"job-{i}")
        result = backfill(jobs, repo_root=tmp_path, dry_run=False, limit=2)
        assert result["created"] == 2
        assert result["processed"] == 2

    def test_nonexistent_root(self) -> None:
        result = backfill(Path("/nonexistent"))
        assert "error" in result
