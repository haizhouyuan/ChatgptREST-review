import json

from chatgptrest.worker.worker import (
    _deep_research_export_should_finalize,
    _should_reconcile_export_answer,
)


def test_deep_research_export_should_finalize_ack_like_text() -> None:
    text = (
        "明白，我将开始对中国卫通（601698.SH）进行深度调研，聚焦其在低轨卫星通信、卫星互联网、星座运营等方面的商业航天相关性。\n\n"
        "稍后将为你交付完整结构化报告，包括合规检查、证据链、催化日历与风险清单。你可以继续与我交流其他内容。"
    )
    assert _deep_research_export_should_finalize(text) is False


def test_deep_research_export_should_finalize_waiting_phrase() -> None:
    text = "请稍等，我完成后将一次性输出完整报告。"
    assert _deep_research_export_should_finalize(text) is False


def test_deep_research_export_should_finalize_long_report_like_text() -> None:
    text = "## 合规检查表\n\n|项目|结论|\n|---|---|\n|是否 ST/*ST|Pass|\n\n## 证据链表\n\n..."
    assert _deep_research_export_should_finalize(text) is True


def test_should_reconcile_export_answer_blocks_deep_research_implicit_link() -> None:
    payload = json.dumps(
        {
            "path": "/Deep Research App/implicit_link::connector_openai_deep_research/start",
            "args": {"user_query": "test"},
        },
        ensure_ascii=False,
    )
    ok, info = _should_reconcile_export_answer(candidate=payload, deep_research=True)
    assert ok is False
    assert info.get("reason") == "deep_research_not_final"


def test_should_reconcile_export_answer_blocks_connector_stub() -> None:
    payload = json.dumps(
        {
            "path": "/Adobe Acrobat/open_file",
            "args": {"name": "x.zip"},
        },
        ensure_ascii=False,
    )
    ok, info = _should_reconcile_export_answer(candidate=payload, deep_research=False)
    assert ok is False
    assert info.get("reason") == "connector_tool_call_stub"


def test_should_reconcile_export_answer_allows_normal_markdown_report() -> None:
    text = "## 调研结论\n\n1. 方案 A\n2. 方案 B\n"
    ok, info = _should_reconcile_export_answer(candidate=text, deep_research=True)
    assert ok is True
    assert info.get("reason") == "ok"


def test_should_reconcile_export_answer_blocks_meta_commentary() -> None:
    text = (
        "I'll start by mapping the code paths and checking the current control surfaces "
        "before I provide the concrete recommendations."
    )
    ok, info = _should_reconcile_export_answer(candidate=text, deep_research=False)
    assert ok is False
    assert info.get("reason") == "answer_quality_suspect_meta_commentary"
    assert info.get("answer_quality") == "suspect_meta_commentary"


def test_should_reconcile_export_answer_blocks_shallow_review_verdict() -> None:
    question = (
        "Review the current ChatgptREST review mirror for source commit d84fe718e1478c59324e753a3637ed87b304d1fc.\n"
        "Three local markdown files are attached and must be treated as required reading.\n"
        "For each finding, cite the problematic path.\n"
    )
    text = (
        "### Findings\n\n"
        "#### 1. Public Agent as the sole general northbound entry\n"
        "**Path**: Public Agent Control Plane (Blueprint)\n"
        "- **Verdict**: This is a sound decision and a realistic approach.\n\n"
        "### Verdict\n\n"
        "The proposed next-step architecture appears fundamentally solid."
    )
    ok, info = _should_reconcile_export_answer(candidate=text, deep_research=False, question=question)
    assert ok is False
    assert info.get("reason") == "answer_quality_suspect_review_shallow_verdict"
    assert info.get("answer_quality") == "suspect_review_shallow_verdict"
