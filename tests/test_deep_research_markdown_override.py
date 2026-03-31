from __future__ import annotations

from chatgptrest.worker.worker import _deep_research_should_override_answer_with_export


def test_deep_research_override_prefers_export_with_markdown_structure() -> None:
    current = "合规检查表\n\n项目 结论\n是否 ST Pass\n证据链表\n1) xxx\n2) yyy\n"
    export = (
        "## 合规检查表\n\n"
        "- 是否 ST/*ST：Pass\n\n"
        "## 证据链表\n\n"
        "|编号|来源|\n|---|---|\n|[S1]|https://example.com/a|\n"
    )
    ok, info = _deep_research_should_override_answer_with_export(
        current_answer=current,
        export_answer=export,
        export_dom_fallback=False,
    )
    assert ok is True
    assert int(info.get("export_score") or 0) > int(info.get("current_score") or 0)


def test_deep_research_override_skips_dom_fallback_export() -> None:
    ok, info = _deep_research_should_override_answer_with_export(
        current_answer="x",
        export_answer="## Title\n- a\n",
        export_dom_fallback=True,
    )
    assert ok is False
    assert info.get("reason") == "export_dom_fallback"


def test_deep_research_override_does_not_churn_on_similar_structure() -> None:
    current = "## Title\n\n- a\n- b\n"
    export = "## Title\n\n- a\n- b\n- c\n"
    ok, info = _deep_research_should_override_answer_with_export(
        current_answer=current,
        export_answer=export,
        export_dom_fallback=False,
    )
    assert ok is False
    assert info.get("reason") == "no_override"


def test_deep_research_override_skips_internal_markup_export_when_current_is_clean() -> None:
    current = "## Title\n\n- Clean answer with [example.com](https://example.com)\n"
    export = "## Title\n\n- Same answer with internal token citeturn1view0\n"
    ok, info = _deep_research_should_override_answer_with_export(
        current_answer=current,
        export_answer=export,
        export_dom_fallback=False,
    )
    assert ok is False
    assert info.get("reason") == "export_contains_internal_markup"
