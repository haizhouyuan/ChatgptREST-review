from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_controller_action_plan import build_plan


def test_build_plan_collects_action_specific_artifacts(tmp_path: Path) -> None:
    result = build_plan(
        output_path=tmp_path / "controller_action_plan.json",
        controller_packet={
            "summary": {
                "recommended_action": "collect_missing_reviews",
                "reason": "review coverage is incomplete",
            },
            "paths": {
                "review_reply_draft": "/tmp/review_reply_draft.md",
                "review_brief": "/tmp/review_brief.md",
            },
        },
        attention_manifest={
            "review": {
                "reviewer_manifest_path": "/tmp/reviewer_manifest.json",
                "pack_path": "/tmp/review_pack/pack.json",
                "review_backlog_path": "/tmp/review_backlog_summary.json",
            }
        },
    )

    assert result["recommended_action"] == "collect_missing_reviews"
    assert "/tmp/reviewer_manifest.json" in result["artifacts"]
    assert result["steps"][0] == "send the current review pack and reviewer manifest to the remaining reviewers"

    written = json.loads((tmp_path / "controller_action_plan.json").read_text(encoding="utf-8"))
    assert written["reason"] == "review coverage is incomplete"

