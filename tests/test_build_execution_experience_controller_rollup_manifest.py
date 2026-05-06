from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_controller_rollup_manifest import build_manifest


def test_build_manifest_collects_all_controller_surface_paths(tmp_path: Path) -> None:
    result = build_manifest(
        output_path=tmp_path / "controller_rollup_manifest.json",
        controller_packet={
            "output_path": "/tmp/controller_packet.json",
            "summary": {
                "recommended_action": "collect_missing_reviews",
                "reason": "review coverage is incomplete",
                "validation_available": True,
                "followup_candidates": 1,
            },
            "paths": {
                "governance_snapshot": "/tmp/governance_snapshot.json",
                "attention_manifest": "/tmp/attention_manifest.json",
                "review_brief": "/tmp/review_brief.md",
                "review_reply_draft": "/tmp/review_reply_draft.md",
            },
        },
        controller_action_plan={
            "output_path": "/tmp/controller_action_plan.json",
            "artifacts": ["/tmp/reviewer_manifest.json"],
            "constraints": ["review-plane only"],
        },
        controller_update_note_path="/tmp/controller_update_note.md",
        progress_delta={
            "output_path": "/tmp/progress_delta.json",
            "status": {"progress_signal": "improved"},
        },
    )

    assert result["summary"]["progress_signal"] == "improved"
    assert result["paths"]["controller_update_note"] == "/tmp/controller_update_note.md"
    assert result["availability"]["progress_delta"] is True

    written = json.loads((tmp_path / "controller_rollup_manifest.json").read_text(encoding="utf-8"))
    assert written["paths"]["progress_delta"] == "/tmp/progress_delta.json"
    assert written["artifacts"] == ["/tmp/reviewer_manifest.json"]


def test_build_manifest_handles_first_cycle_without_progress_delta(tmp_path: Path) -> None:
    result = build_manifest(
        output_path=tmp_path / "controller_rollup_manifest.json",
        controller_packet={"summary": {}, "paths": {}},
        controller_action_plan={"artifacts": [], "constraints": []},
        controller_update_note_path="/tmp/controller_update_note.md",
        progress_delta=None,
    )

    assert result["summary"]["progress_signal"] == ""
    assert result["availability"]["progress_delta"] is False
