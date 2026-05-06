from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_review_pack import build_review_pack


def test_build_review_pack_writes_pack_and_prompt(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "execxp_at_1",
                    "atom_id": "at_1",
                    "lineage_family_id": "fam_1",
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "experience_kind": "lesson",
                    "title": "workflow lesson",
                    "summary": "A reusable workflow lesson.",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = build_review_pack(candidates_path=candidates_path, output_dir=tmp_path / "pack")

    assert result["selected_candidates"] == 1
    pack = json.loads(Path(result["pack_path"]).read_text(encoding="utf-8"))
    assert pack["pack_type"] == "execution_experience_candidate_review"
    assert pack["items"][0]["candidate_id"] == "execxp_at_1"
    assert Path(result["prompt_path"]).exists()
