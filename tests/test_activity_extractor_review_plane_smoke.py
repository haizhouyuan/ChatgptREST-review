from __future__ import annotations

from ops.run_activity_extractor_review_plane_smoke import run_smoke


def test_activity_extractor_review_plane_smoke() -> None:
    report = run_smoke()
    assert report["ok"] is True
    assert report["stats"]["atoms_created"] == 2
    assert {item["promotion_status"] for item in report["atoms"]} == {"staged"}
    assert {item["status"] for item in report["atoms"]} == {"candidate"}

    atom_applicability = {item["canonical_question"]: item["applicability"] for item in report["atoms"]}
    closeout = next(value for key, value in atom_applicability.items() if key.startswith("task result:"))
    commit = next(value for key, value in atom_applicability.items() if key.startswith("commit "))
    assert closeout["role_id"] == "devops"
    assert closeout["lane_id"] == "main"
    assert closeout["executor_kind"] == "codex.controller"
    assert commit["adapter_id"] == "controller_lane_wrapper"
    assert commit["profile_id"] == "mainline_runtime"

    episode_index = {item["episode_type"]: item["source_ext"] for item in report["episodes"]}
    assert episode_index["agent.task.closeout"]["role_id"] == "devops"
    assert episode_index["agent.git.commit"]["trace_id"] == "trace-review-plane-commit"
