from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_controller_reply_packet import build_packet


def test_build_packet_collects_manual_send_reply_payload(tmp_path: Path) -> None:
    result = build_packet(
        output_path=tmp_path / "controller_reply_packet.json",
        controller_rollup_manifest={
            "output_path": "/tmp/controller_rollup_manifest.json",
            "summary": {
                "recommended_action": "collect_missing_reviews",
                "reason": "review coverage is incomplete",
                "progress_signal": "improved",
                "validation_available": True,
                "followup_candidates": 1,
            },
            "paths": {
                "review_brief": "/tmp/review_brief.md",
                "review_reply_draft": "/tmp/review_reply_draft.md",
                "progress_delta": "/tmp/progress_delta.json",
            },
        },
        controller_action_plan={
            "output_path": "/tmp/controller_action_plan.json",
            "steps": [
                "send the current review pack and reviewer manifest to the remaining reviewers",
                "wait for missing review outputs to land",
            ],
            "constraints": ["review-plane only", "no auto-commenting"],
        },
        controller_update_note_path="/tmp/controller_update_note.md",
    )

    assert result["decision"]["reply_kind"] == "missing_review_request"
    assert result["decision"]["manual_send_required"] is True
    assert result["decision"]["auto_send_allowed"] is False
    assert "Execution experience review-plane update:" in result["reply"]["comment_markdown"]
    assert "progress_signal=improved" in result["reply"]["comment_markdown"]
    assert result["paths"]["controller_update_note"] == "/tmp/controller_update_note.md"

    written = json.loads((tmp_path / "controller_reply_packet.json").read_text(encoding="utf-8"))
    assert written["constraints"] == ["review-plane only", "no auto-commenting"]


def test_build_packet_handles_parked_reply_kind(tmp_path: Path) -> None:
    result = build_packet(
        output_path=tmp_path / "controller_reply_packet.json",
        controller_rollup_manifest={"summary": {"recommended_action": "park"}},
        controller_action_plan={"constraints": []},
        controller_update_note_path="/tmp/controller_update_note.md",
    )

    assert result["decision"]["reply_kind"] == "parked_status_update"
