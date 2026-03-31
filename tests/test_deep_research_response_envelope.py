from __future__ import annotations

import json

from chatgptrest.worker.worker import (
    _deep_research_export_should_finalize,
    _deep_research_is_ack,
    _extract_answer_from_conversation_export_obj,
)


def _make_response_envelope(*, response: str, prompt_len: int) -> str:
    obj = {
        "task_violates_safety_guidelines": False,
        "user_def_doesnt_want_research": False,
        "response": response,
        "title": "t",
        "prompt": "x" * int(prompt_len),
    }
    return json.dumps(obj, ensure_ascii=False, indent=2)


def test_deep_research_ack_unwraps_long_json_envelope() -> None:
    env = _make_response_envelope(response="好的，我将一次性输出完整最终稿。", prompt_len=5000)
    assert len(env) > 1200
    assert _deep_research_is_ack(env) is True


def test_extract_answer_prefers_report_over_long_envelope_prompt() -> None:
    env = _make_response_envelope(response="好的，我将一次性输出完整最终稿。", prompt_len=5000)
    report = "## D1\n\n" + ("a" * 2500)
    obj = {
        "messages": [
            {"role": "user", "text": "Q1"},
            {"role": "assistant", "text": "明白，我将开始研究。"},
            {"role": "assistant", "text": env},
            {"role": "assistant", "text": report},
        ]
    }
    ans, info = _extract_answer_from_conversation_export_obj(
        obj=obj,
        question="Q1",
        deep_research=True,
        allow_fallback_last_assistant=False,
    )
    assert info.get("answer_source") == "matched_window_longest"
    assert ans is not None
    assert ans.lstrip().startswith("## D1")
    assert not ans.lstrip().startswith("{")


def test_deep_research_export_should_not_finalize_implicit_link_stub() -> None:
    stub = json.dumps(
        {
            "path": "/Deep Research App/implicit_link::connector_openai_deep_research/start",
            "args": {"user_query": "x"},
        },
        ensure_ascii=False,
    )
    assert _deep_research_export_should_finalize(stub) is False
