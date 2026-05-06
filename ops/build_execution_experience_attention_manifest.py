#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    output_path: str | Path,
    review_pack: dict[str, Any],
    reviewer_manifest: dict[str, Any],
    review_backlog: dict[str, Any],
    review_backlog_path: str | Path,
    review_decision_scaffold_path: str | Path,
    review_validation: dict[str, Any] | None,
    governance_queues: dict[str, Any],
    followup_manifest: dict[str, Any],
) -> dict[str, Any]:
    validation = review_validation if isinstance(review_validation, dict) else {}
    manifest = {
        "ok": True,
        "scope": {
            "review_plane_only": True,
            "default_runtime_cutover": False,
            "active_knowledge_promotion": False,
        },
        "review": {
            "selected_candidates": int(review_pack.get("selected_candidates", 0)),
            "pack_path": str(review_pack.get("pack_path") or ""),
            "reviewer_manifest_path": str(reviewer_manifest.get("manifest_path") or ""),
            "review_output_dir": str(reviewer_manifest.get("review_output_dir") or ""),
            "review_backlog_candidates": int(review_backlog.get("backlog_candidates", 0)),
            "review_backlog_path": str(review_backlog_path),
            "review_decision_scaffold_path": str(review_decision_scaffold_path),
            "review_output_validation_path": str(validation.get("review_output_validation_path") or ""),
            "validation_available": bool(validation),
            "validation_structurally_valid": validation.get("structurally_valid") if validation else None,
            "validation_complete": validation.get("complete") if validation else None,
            "missing_reviewers": list(validation.get("missing_reviewers") or []),
            "unexpected_reviewers": list(validation.get("unexpected_reviewers") or []),
        },
        "governance": {
            "summary_path": str(governance_queues.get("summary_path") or ""),
            "state_routes": dict(governance_queues.get("queue_files") or {}),
            "action_routes": dict(governance_queues.get("action_files") or {}),
        },
        "followup": {
            "total_candidates": int(followup_manifest.get("total_followup_candidates", 0)),
            "routes": dict(followup_manifest.get("branches") or {}),
        },
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["output_path"] = str(out)
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an attention manifest for execution experience review artifacts.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-pack", required=True)
    parser.add_argument("--reviewer-manifest", required=True)
    parser.add_argument("--review-backlog", required=True)
    parser.add_argument("--review-backlog-path", required=True)
    parser.add_argument("--review-decision-scaffold-path", required=True)
    parser.add_argument("--governance-queue-summary", required=True)
    parser.add_argument("--followup-manifest", required=True)
    parser.add_argument("--review-output-validation", default="")
    args = parser.parse_args()

    review_pack = _load_json(Path(args.review_pack))
    reviewer_manifest = _load_json(Path(args.reviewer_manifest))
    review_backlog = _load_json(Path(args.review_backlog))
    governance_queues = _load_json(Path(args.governance_queue_summary))
    followup_manifest = _load_json(Path(args.followup_manifest))
    review_validation = _load_json(Path(args.review_output_validation)) if args.review_output_validation else None
    if review_validation:
        review_validation["review_output_validation_path"] = args.review_output_validation

    result = build_manifest(
        output_path=args.output,
        review_pack=review_pack,
        reviewer_manifest=reviewer_manifest,
        review_backlog=review_backlog,
        review_backlog_path=args.review_backlog_path,
        review_decision_scaffold_path=args.review_decision_scaffold_path,
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
