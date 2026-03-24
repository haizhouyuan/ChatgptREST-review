"""Artifact manifest validation and generation.

Schema: ``docs/contracts/artifact-manifest-v1.schema.json``

Phase 0 of artifact governance blueprint v2.
Provides:
- ``validate_manifest(data)`` — validate a dict against the minimal required schema
- ``generate_job_manifest(job_dir)`` — generate a manifest from a job's existing files
- ``ArtifactType`` — enum of valid artifact types (from ADR-001)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "ArtifactType",
    "ManifestError",
    "validate_manifest",
    "generate_job_manifest",
]

SCHEMA_VERSION = "artifact-manifest-v1"

REQUIRED_FIELDS = frozenset({
    "artifact_id",
    "artifact_type",
    "canonical_path",
    "created_at",
    "schema_version",
})


class ArtifactType(str, Enum):
    """Object types from ADR-001."""
    RUNTIME_EVIDENCE = "runtime_evidence"
    EVIDENCE_ARTIFACT = "evidence_artifact"
    GOVERNED_CLAIM = "governed_claim"
    PROFILE_MEMORY = "profile_memory"
    EPISODIC_FEEDBACK = "episodic_feedback"


VALID_RETENTION_CLASSES = frozenset({"hot", "warm", "archive_only"})
VALID_REVIEW_STATUSES = frozenset({"draft", "candidate", "approved", "expired", "archived"})


class ManifestError(ValueError):
    """Raised when a manifest fails validation."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_manifest(data: dict[str, Any]) -> list[str]:
    """Validate a manifest dict against the Phase 0 minimal schema.

    Returns a list of error messages (empty = valid).
    Raises ``ManifestError`` if ``data`` is not a dict.
    """
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a dict")

    errors: list[str] = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")
        elif not isinstance(data[field], str) or not data[field].strip():
            errors.append(f"field '{field}' must be a non-empty string")

    # schema_version must match
    sv = data.get("schema_version")
    if sv and sv != SCHEMA_VERSION:
        errors.append(f"schema_version must be '{SCHEMA_VERSION}', got '{sv}'")

    # artifact_type must be valid
    at = data.get("artifact_type")
    valid_types = {e.value for e in ArtifactType}
    if at and at not in valid_types:
        errors.append(f"artifact_type '{at}' not in {sorted(valid_types)}")

    # Optional field validation
    rc = data.get("retention_class")
    if rc is not None and rc not in VALID_RETENTION_CLASSES:
        errors.append(f"retention_class '{rc}' not in {sorted(VALID_RETENTION_CLASSES)}")

    rs = data.get("review_status")
    if rs is not None and rs not in VALID_REVIEW_STATUSES:
        errors.append(f"review_status '{rs}' not in {sorted(VALID_REVIEW_STATUSES)}")

    rp = data.get("related_paths")
    if rp is not None and not isinstance(rp, list):
        errors.append("related_paths must be an array")

    for dt_field in ("created_at", "updated_at", "expires_at"):
        v = data.get(dt_field)
        if v and isinstance(v, str):
            try:
                datetime.fromisoformat(v)
            except ValueError:
                errors.append(f"'{dt_field}' is not a valid ISO 8601 datetime")

    return errors


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file (first 1MB for speed)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(1_048_576))
    return h.hexdigest()


def generate_job_manifest(
    job_dir: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Generate a manifest.json from a job directory's existing files.

    Reads ``request.json`` and ``result.json`` as de facto manifest sources.
    """
    job_dir = Path(job_dir)
    job_id = job_dir.name

    # Relative canonical path
    if repo_root:
        canonical = str(job_dir.relative_to(repo_root))
    else:
        canonical = str(job_dir)

    # Extract from request.json
    request_path = job_dir / "request.json"
    request_data: dict[str, Any] = {}
    if request_path.exists():
        try:
            request_data = json.loads(request_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    # Extract from result.json
    result_path = job_dir / "result.json"
    result_data: dict[str, Any] = {}
    if result_path.exists():
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    # Determine created_at
    created_at = (
        request_data.get("created_at")
        or result_data.get("created_at")
        or datetime.now(timezone.utc).isoformat()
    )

    manifest: dict[str, Any] = {
        "artifact_id": job_id,
        "artifact_type": ArtifactType.RUNTIME_EVIDENCE.value,
        "canonical_path": canonical,
        "created_at": created_at,
        "schema_version": SCHEMA_VERSION,
    }

    # Optional enrichment from request/result
    if job_id:
        manifest["job_id"] = job_id

    kind = request_data.get("kind") or request_data.get("input", {}).get("kind", "")
    if kind:
        manifest["source_system"] = str(kind).split(".")[0]  # e.g., "chatgpt_web" -> "chatgpt_web"

    client = request_data.get("client_name") or ""
    if client:
        manifest["producer"] = client

    # Content hash from answer file
    answer_candidates = ["answer.md", "answer.txt", "answer.html"]
    for name in answer_candidates:
        answer_path = job_dir / name
        if answer_path.exists():
            manifest["content_hash"] = _file_sha256(answer_path)
            break

    # Related paths
    related = []
    for name in ["events.jsonl", "conversation.json", "request.json", "result.json"]:
        p = job_dir / name
        if p.exists():
            related.append(str(Path(canonical) / name))
    if related:
        manifest["related_paths"] = related

    manifest["retention_class"] = "hot"
    manifest["review_status"] = "draft"

    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    """CLI entry point for manifest operations."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Artifact manifest tools")
    sub = ap.add_subparsers(dest="cmd")

    # validate
    val = sub.add_parser("validate", help="Validate a manifest.json file")
    val.add_argument("path", help="Path to manifest.json")

    # generate
    gen = sub.add_parser("generate", help="Generate manifest from job dir")
    gen.add_argument("job_dir", help="Path to job directory")
    gen.add_argument("--repo-root", help="Repository root for relative paths")
    gen.add_argument("--write", action="store_true", help="Write manifest.json to job dir")

    args = ap.parse_args()

    if args.cmd == "validate":
        data = json.loads(Path(args.path).read_text(encoding="utf-8"))
        errors = validate_manifest(data)
        if errors:
            for e in errors:
                print(f"  ❌ {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print("  ✅ Valid manifest")

    elif args.cmd == "generate":
        job_dir = Path(args.job_dir)
        repo_root = Path(args.repo_root) if args.repo_root else None
        manifest = generate_job_manifest(job_dir, repo_root=repo_root)
        out = json.dumps(manifest, indent=2, ensure_ascii=False)
        if args.write:
            (job_dir / "manifest.json").write_text(out + "\n", encoding="utf-8")
            print(f"  ✅ Wrote {job_dir / 'manifest.json'}")
        else:
            print(out)

    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _cli()
