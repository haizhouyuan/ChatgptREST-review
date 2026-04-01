#!/usr/bin/env python3
"""Build CLI-Anything market manifest for candidate intake.

Converts CLI-Anything generation output into market_skill_candidates import format.
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_candidate(
    *,
    skill_id: str,
    capability_ids: list[str],
    source_uri: str,
    summary: str,
    validation_bundle_dir: str | None = None,
    package_dir: str | None = None,
) -> dict[str, Any]:
    """Build a single market candidate from CLI-Anything output.

    Args:
        skill_id: Unique skill identifier (e.g., "cli-anything-freecad")
        capability_ids: List of capability IDs this skill provides
        source_uri: Source URI (e.g., "file:///path/to/agent-harness")
        summary: Brief description of the skill
        validation_bundle_dir: Path to validation bundle directory
        package_dir: Path to generated package directory

    Returns:
        Candidate record ready to be embedded in a market manifest
    """
    candidate_id = f"cli-anything-{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    evidence: dict[str, Any] = {}
    if validation_bundle_dir:
        evidence["validation_bundle_dir"] = str(validation_bundle_dir)
    if package_dir:
        evidence["package_dir"] = str(package_dir)

    candidate = {
        "candidate_id": candidate_id,
        "skill_id": skill_id,
        "source_market": "cli-anything",
        "source_uri": source_uri,
        "capability_ids": capability_ids,
        "status": "quarantine",
        "trust_level": "unreviewed",
        "quarantine_state": "pending",
        "linked_gap_id": "",
        "summary": summary,
        "evidence": evidence,
        "created_at": now,
        "updated_at": now,
    }

    return candidate


def build_manifest(
    *,
    skill_id: str,
    capability_ids: list[str],
    source_uri: str,
    summary: str,
    validation_bundle_dir: str | None = None,
    package_dir: str | None = None,
) -> dict[str, Any]:
    """Build market manifest from CLI-Anything output."""
    candidate = build_candidate(
        skill_id=skill_id,
        capability_ids=capability_ids,
        source_uri=source_uri,
        summary=summary,
        validation_bundle_dir=validation_bundle_dir,
        package_dir=package_dir,
    )
    return {
        "schema_version": "market_skill_candidates.v1",
        "source_market": "cli-anything",
        "generated_at": _now_iso(),
        "candidates": [candidate],
    }


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build CLI-Anything market manifest for candidate intake"
    )
    parser.add_argument("--skill-id", required=True, help="Unique skill identifier")
    parser.add_argument(
        "--capability-id",
        action="append",
        dest="capability_ids",
        required=True,
        help="Capability ID (repeatable)",
    )
    parser.add_argument("--source-uri", required=True, help="Source URI")
    parser.add_argument("--summary", required=True, help="Brief description")
    parser.add_argument(
        "--validation-bundle-dir",
        default=None,
        help="Path to validation bundle directory",
    )
    parser.add_argument(
        "--package-dir",
        default=None,
        help="Path to generated package directory",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args(argv)

    manifest = build_manifest(
        skill_id=args.skill_id,
        capability_ids=args.capability_ids,
        source_uri=args.source_uri,
        summary=args.summary,
        validation_bundle_dir=args.validation_bundle_dir,
        package_dir=args.package_dir,
    )

    output = json.dumps(manifest, indent=2, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Manifest written to {args.out}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
