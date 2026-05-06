from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_followup_manifest import build_manifest


def test_build_manifest_collects_branch_counts_and_paths(tmp_path: Path) -> None:
    manifest = build_manifest(
        output_path=tmp_path / "followup_manifest.json",
        acceptance_pack={
            "accepted_candidates": 2,
            "manifest_path": str(tmp_path / "accepted_pack" / "manifest.json"),
            "smoke_manifest_path": str(tmp_path / "accepted_pack" / "smoke_manifest.json"),
        },
        revision_worklist={
            "total_revise_candidates": 1,
            "output_tsv": str(tmp_path / "revision_worklist.tsv"),
            "summary_path": str(tmp_path / "revision_worklist.summary.json"),
        },
        deferred_revisit_queue={
            "total_deferred_candidates": 3,
            "output_tsv": str(tmp_path / "deferred_revisit_queue.tsv"),
            "summary_path": str(tmp_path / "deferred_revisit_queue.summary.json"),
        },
        rejected_archive_queue={
            "total_rejected_candidates": 4,
            "output_tsv": str(tmp_path / "rejected_archive_queue.tsv"),
            "summary_path": str(tmp_path / "rejected_archive_queue.summary.json"),
        },
    )

    written = json.loads((tmp_path / "followup_manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_followup_candidates"] == 10
    assert written["branches"]["accept"]["candidates"] == 2
    assert written["branches"]["revise"]["candidates"] == 1
    assert written["branches"]["defer"]["candidates"] == 3
    assert written["branches"]["reject"]["candidates"] == 4

