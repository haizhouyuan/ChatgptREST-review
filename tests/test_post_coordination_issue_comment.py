from __future__ import annotations

from ops.poll_coordination_issues import CONTROLLER_MARKER
from ops.post_coordination_issue_comment import build_comment_body


def test_build_comment_body_adds_controller_marker() -> None:
    payload = build_comment_body("收到，已吸收。", controller=True)
    assert payload.endswith(f"\n\n{CONTROLLER_MARKER}\n")
    assert payload.startswith("收到，已吸收。")


def test_build_comment_body_leaves_plain_origin_unmarked() -> None:
    payload = build_comment_body("education codex", controller=False)
    assert payload == "education codex\n"

