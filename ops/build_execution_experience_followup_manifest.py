#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    output_path: str | Path,
    acceptance_pack: dict[str, Any],
    revision_worklist: dict[str, Any],
    deferred_revisit_queue: dict[str, Any],
    rejected_archive_queue: dict[str, Any],
) -> dict[str, Any]:
    manifest = {
        "ok": True,
        "branches": {
            "accept": {
                "candidates": int(acceptance_pack.get("accepted_candidates", 0)),
                "manifest_path": str(acceptance_pack.get("manifest_path") or ""),
                "smoke_manifest_path": str(acceptance_pack.get("smoke_manifest_path") or ""),
            },
            "revise": {
                "candidates": int(revision_worklist.get("total_revise_candidates", 0)),
                "worklist_path": str(revision_worklist.get("output_tsv") or ""),
                "summary_path": str(revision_worklist.get("summary_path") or ""),
            },
            "defer": {
                "candidates": int(deferred_revisit_queue.get("total_deferred_candidates", 0)),
                "queue_path": str(deferred_revisit_queue.get("output_tsv") or ""),
                "summary_path": str(deferred_revisit_queue.get("summary_path") or ""),
            },
            "reject": {
                "candidates": int(rejected_archive_queue.get("total_rejected_candidates", 0)),
                "queue_path": str(rejected_archive_queue.get("output_tsv") or ""),
                "summary_path": str(rejected_archive_queue.get("summary_path") or ""),
            },
        },
    }
    manifest["total_followup_candidates"] = sum(item["candidates"] for item in manifest["branches"].values())
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
    parser = argparse.ArgumentParser(description="Build a follow-up manifest for execution experience decision branches.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--acceptance-pack-manifest", required=True)
    parser.add_argument("--acceptance-pack-smoke-manifest", required=True)
    parser.add_argument("--revision-worklist-summary", required=True)
    parser.add_argument("--deferred-revisit-summary", required=True)
    parser.add_argument("--rejected-archive-summary", required=True)
    args = parser.parse_args()

    acceptance_pack = _load_json(Path(args.acceptance_pack_manifest))
    acceptance_pack["manifest_path"] = args.acceptance_pack_manifest
    acceptance_pack["smoke_manifest_path"] = args.acceptance_pack_smoke_manifest
    acceptance_pack["accepted_candidates"] = acceptance_pack.get("counts", {}).get("accepted_candidates", 0)

    revision_worklist = _load_json(Path(args.revision_worklist_summary))
    deferred_revisit_queue = _load_json(Path(args.deferred_revisit_summary))
    rejected_archive_queue = _load_json(Path(args.rejected_archive_summary))

    result = build_manifest(
        output_path=args.output,
        acceptance_pack=acceptance_pack,
        revision_worklist=revision_worklist,
        deferred_revisit_queue=deferred_revisit_queue,
        rejected_archive_queue=rejected_archive_queue,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
