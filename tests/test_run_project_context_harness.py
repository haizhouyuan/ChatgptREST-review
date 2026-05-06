from __future__ import annotations

from pathlib import Path

from ops.run_project_context_harness import build_project_context_harness


def _write_anchor(path: Path, *, name: str, project_id: str, valid: bool) -> None:
    authority_doc = path.parent / f"{project_id}-authority.md"
    authority_doc.write_text("# authority\n", encoding="utf-8")
    if valid:
        frontmatter = (
            f"project: {name}\n"
            f"alias: {project_id}\n"
            f"project_id: {project_id}\n"
            f"planning_base: {path.parent}\n"
            "owner: YHZ / planning\n"
            "last_reviewed_at: 2026-04-09\n"
            "authority_docs:\n"
            f"  - {authority_doc}\n"
            "frozen_facts:\n"
            f"  - {name} remains blocked.\n"
            "style_rules:\n"
            "  - Be concise.\n"
        )
        body = (
            "## 当前权威文档\n\n- authority.md\n\n"
            "## 当前阶段\n\n- Controlled rollout.\n\n"
            "## 当前待推进动作\n\n- Confirm budget.\n"
        )
    else:
        frontmatter = (
            f"project: {name}\n"
            f"alias: {project_id}\n"
            f"planning_base: {path.parent}\n"
            "updated: 2026-04-09\n"
            "authority_docs:\n"
            f"  - {authority_doc}\n"
        )
        body = "## 当前阶段\n\n- Missing contract fields.\n"
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")


def test_build_project_context_harness_filters_selected_projects(tmp_path: Path) -> None:
    first_dir = tmp_path / "alpha"
    second_dir = tmp_path / "beta"
    first_dir.mkdir()
    second_dir.mkdir()
    _write_anchor(first_dir / "_project_context.md", name="Alpha", project_id="alpha", valid=True)
    _write_anchor(second_dir / "_project_context.md", name="Beta", project_id="beta", valid=False)

    payload = build_project_context_harness(
        planning_root=tmp_path,
        project_ids=["alpha"],
        stale_days=30,
    )

    assert payload["ok"] is True
    assert payload["summary"]["anchor_count"] == 1
    assert payload["summary"]["lint_pass_count"] == 1
    assert payload["missing_project_ids"] == []
    assert payload["anchors"][0]["project_id"] == "alpha"


def test_build_project_context_harness_marks_missing_project_id(tmp_path: Path) -> None:
    payload = build_project_context_harness(
        planning_root=tmp_path,
        project_ids=["missing-project"],
        stale_days=30,
    )

    assert payload["ok"] is False
    assert payload["missing_project_ids"] == ["missing-project"]
    assert payload["summary"]["missing_project_id_count"] == 1
