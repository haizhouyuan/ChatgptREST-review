from __future__ import annotations

from pathlib import Path

from chatgptrest.governance.authority_anchor import inspect_authority_anchor_path


def _write_anchor(path: Path, *, frontmatter: str, body: str) -> Path:
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return path


def test_inspect_authority_anchor_path_passes_for_complete_anchor(tmp_path: Path) -> None:
    authority_doc = tmp_path / "authority.md"
    authority_doc.write_text("# authority\n", encoding="utf-8")
    anchor_path = _write_anchor(
        tmp_path / "_project_context.md",
        frontmatter=(
            "project: Alpha\n"
            "alias: alpha\n"
            "project_id: alpha\n"
            f"planning_base: {tmp_path}\n"
            "owner: YHZ / planning\n"
            "last_reviewed_at: 2026-04-09\n"
            "authority_docs:\n"
            f"  - {authority_doc}\n"
            "frozen_facts:\n"
            "  - Alpha remains blocked.\n"
            "style_rules:\n"
            "  - Be concise.\n"
        ),
        body=(
            "## 当前权威文档\n\n- authority.md\n\n"
            "## 当前阶段\n\n- Alpha is in controlled rollout.\n\n"
            "## 当前待推进动作\n\n- Confirm budget.\n"
        ),
    )

    result = inspect_authority_anchor_path(anchor_path, stale_days=30)

    assert result["ok"] is True
    assert result["lint_status"] == "pass"
    assert result["required_frontmatter"]["last_reviewed_at"] is True
    assert result["required_sections"]["action_section"] is True
    assert result["errors"] == []


def test_inspect_authority_anchor_path_fails_when_required_fields_are_missing(tmp_path: Path) -> None:
    authority_doc = tmp_path / "authority.md"
    authority_doc.write_text("# authority\n", encoding="utf-8")
    anchor_path = _write_anchor(
        tmp_path / "_project_context.md",
        frontmatter=(
            "project: Beta\n"
            "alias: beta\n"
            f"planning_base: {tmp_path}\n"
            "updated: 2026-04-09\n"
            "authority_docs:\n"
            f"  - {authority_doc}\n"
            "frozen_facts:\n"
            "  - Beta remains blocked.\n"
        ),
        body=(
            "## 当前权威文档\n\n- authority.md\n\n"
            "## 当前阶段\n\n- Beta is blocked.\n"
        ),
    )

    result = inspect_authority_anchor_path(anchor_path, stale_days=30)

    assert result["ok"] is False
    assert result["lint_status"] == "fail"
    assert "missing_project_id_field" in result["errors"]
    assert "missing_owner_field" in result["errors"]
    assert "missing_last_reviewed_at_field" in result["errors"]
    assert "missing_style_rules" in result["errors"]
    assert "missing_action_section" in result["errors"]

