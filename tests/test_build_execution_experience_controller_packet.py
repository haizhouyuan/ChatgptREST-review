from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_controller_packet import build_packet


def test_build_packet_collects_controller_summary_and_paths(tmp_path: Path) -> None:
    result = build_packet(
        output_path=tmp_path / "controller_packet.json",
        governance_snapshot={
            "output_path": "/tmp/governance_snapshot.json",
            "totals": {
                "total_candidates": 12,
                "backlog_candidates": 4,
                "followup_candidates": 3,
            },
            "validation_state": {
                "available": True,
            },
            "attention_flags": {
                "backlog_open": True,
                "followup_work_present": True,
            },
        },
        attention_manifest={
            "output_path": "/tmp/attention_manifest.json",
            "followup": {
                "total_candidates": 3,
                "routes": {"accept": {"candidates": 1}},
            },
        },
        review_brief_path="/tmp/review_brief.md",
        review_reply_draft={
            "output_path": "/tmp/review_reply_draft.md",
            "recommended_action": "collect_missing_reviews",
            "reason": "review coverage is incomplete",
        },
    )

    assert result["summary"]["recommended_action"] == "collect_missing_reviews"
    assert result["paths"]["review_brief"] == "/tmp/review_brief.md"
    assert result["followup"]["total_candidates"] == 3

    written = json.loads((tmp_path / "controller_packet.json").read_text(encoding="utf-8"))
    assert written["flags"]["backlog_open"] is True

