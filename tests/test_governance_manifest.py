"""Tests for chatgptrest.governance.manifest."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from chatgptrest.governance.manifest import (
    ArtifactType,
    ManifestError,
    SCHEMA_VERSION,
    generate_job_manifest,
    validate_manifest,
)


# ---------------------------------------------------------------------------
# validate_manifest
# ---------------------------------------------------------------------------

class TestValidateManifest:
    """Tests for validate_manifest."""

    def _minimal(self, **overrides: object) -> dict:
        base = {
            "artifact_id": "test-001",
            "artifact_type": "runtime_evidence",
            "canonical_path": "artifacts/jobs/test-001",
            "created_at": "2026-03-16T09:00:00+00:00",
            "schema_version": SCHEMA_VERSION,
        }
        base.update(overrides)
        return base

    def test_valid_minimal(self) -> None:
        errors = validate_manifest(self._minimal())
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = self._minimal()
        del data["artifact_id"]
        errors = validate_manifest(data)
        assert any("artifact_id" in e for e in errors)

    def test_empty_required_field(self) -> None:
        errors = validate_manifest(self._minimal(artifact_id=""))
        assert any("artifact_id" in e for e in errors)

    def test_wrong_schema_version(self) -> None:
        errors = validate_manifest(self._minimal(schema_version="v99"))
        assert any("schema_version" in e for e in errors)

    def test_invalid_artifact_type(self) -> None:
        errors = validate_manifest(self._minimal(artifact_type="not_a_type"))
        assert any("artifact_type" in e for e in errors)

    def test_valid_all_artifact_types(self) -> None:
        for at in ArtifactType:
            errors = validate_manifest(self._minimal(artifact_type=at.value))
            assert errors == [], f"Failed for {at.value}: {errors}"

    def test_invalid_retention_class(self) -> None:
        errors = validate_manifest(self._minimal(retention_class="frozen"))
        assert any("retention_class" in e for e in errors)

    def test_valid_retention_class(self) -> None:
        for rc in ("hot", "warm", "archive_only"):
            errors = validate_manifest(self._minimal(retention_class=rc))
            assert errors == []

    def test_invalid_review_status(self) -> None:
        errors = validate_manifest(self._minimal(review_status="unknown"))
        assert any("review_status" in e for e in errors)

    def test_valid_review_status(self) -> None:
        for rs in ("draft", "candidate", "approved", "expired", "archived"):
            errors = validate_manifest(self._minimal(review_status=rs))
            assert errors == []

    def test_invalid_datetime(self) -> None:
        errors = validate_manifest(self._minimal(created_at="not-a-date"))
        assert any("created_at" in e for e in errors)

    def test_related_paths_must_be_list(self) -> None:
        errors = validate_manifest(self._minimal(related_paths="not-a-list"))
        assert any("related_paths" in e for e in errors)

    def test_related_paths_valid(self) -> None:
        errors = validate_manifest(self._minimal(related_paths=["a.json", "b.json"]))
        assert errors == []

    def test_not_dict_raises(self) -> None:
        with pytest.raises(ManifestError):
            validate_manifest("not a dict")  # type: ignore[arg-type]

    def test_additional_properties_allowed(self) -> None:
        """Extra fields are allowed (additionalProperties: true)."""
        errors = validate_manifest(self._minimal(custom_field="hello"))
        assert errors == []


# ---------------------------------------------------------------------------
# generate_job_manifest
# ---------------------------------------------------------------------------

class TestGenerateJobManifest:
    """Tests for generate_job_manifest."""

    def test_generates_from_request_json(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "artifacts" / "jobs" / "job-123"
        job_dir.mkdir(parents=True)
        (job_dir / "request.json").write_text(json.dumps({
            "kind": "chatgpt_web.ask",
            "created_at": "2026-03-16T09:00:00+00:00",
            "client_name": "finagent",
        }))
        (job_dir / "answer.md").write_text("Test answer")

        manifest = generate_job_manifest(job_dir, repo_root=tmp_path)
        errors = validate_manifest(manifest)
        assert errors == [], f"Generated manifest has errors: {errors}"
        assert manifest["artifact_id"] == "job-123"
        assert manifest["artifact_type"] == "runtime_evidence"
        assert manifest["source_system"] == "chatgpt_web"
        assert manifest["producer"] == "finagent"
        assert manifest["content_hash"]  # non-empty SHA-256
        assert manifest["schema_version"] == SCHEMA_VERSION

    def test_generates_without_request_json(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-456"
        job_dir.mkdir(parents=True)
        manifest = generate_job_manifest(job_dir)
        errors = validate_manifest(manifest)
        assert errors == [], f"Generated manifest has errors: {errors}"
        assert manifest["artifact_id"] == "job-456"

    def test_canonical_path_relative_to_repo(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "artifacts" / "jobs" / "job-789"
        job_dir.mkdir(parents=True)
        manifest = generate_job_manifest(job_dir, repo_root=tmp_path)
        assert manifest["canonical_path"] == "artifacts/jobs/job-789"

    def test_related_paths_from_existing_files(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-aaa"
        job_dir.mkdir(parents=True)
        (job_dir / "request.json").write_text("{}")
        (job_dir / "events.jsonl").write_text("")
        manifest = generate_job_manifest(job_dir)
        assert "related_paths" in manifest
        related = manifest["related_paths"]
        assert any("request.json" in p for p in related)
        assert any("events.jsonl" in p for p in related)
