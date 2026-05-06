from __future__ import annotations

import json

from chatgptrest.worker.worker import _looks_like_tool_payload_answer


def test_tool_payload_answer_detects_search_query_json() -> None:
    text = json.dumps(
        {
            "search_query": [{"q": "OpenClaw kb-core docs", "recency": 3650}],
            "response_length": "short",
        },
        ensure_ascii=False,
    )
    ok, info = _looks_like_tool_payload_answer(text)
    assert ok is True
    assert info.get("reason") == "search_query_payload"
    assert "search_query" in list(info.get("keys") or [])


def test_tool_payload_answer_ignores_plain_text() -> None:
    ok, info = _looks_like_tool_payload_answer("## 正文\n\n这是最终报告内容。")
    assert ok is False
    assert info == {}


def test_tool_payload_answer_ignores_partial_json_shape() -> None:
    text = json.dumps({"search_query": [{"q": "x"}]}, ensure_ascii=False)
    ok, info = _looks_like_tool_payload_answer(text)
    assert ok is False
    assert info == {}
