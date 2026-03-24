from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.worker.worker import (
    _deep_research_export_should_finalize,
    _deep_research_is_ack,
    _extract_answer_from_conversation_export,
    _should_prefer_conversation_answer,
)


def _write_export(path: Path, messages: list[dict]) -> None:
    payload = {"export_kind": "dom_messages", "messages": messages}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_mapping_export(path: Path, *, conversation_id: str, nodes: list[tuple[str, str]]) -> None:
    root = "client-created-root"
    mapping: dict[str, dict] = {root: {"id": root, "message": None, "parent": None, "children": []}}
    parent = root
    current = root
    for i, (role, text) in enumerate(nodes, start=1):
        node_id = f"node-{i}"
        msg = {
            "id": node_id,
            "author": {"role": role, "name": None, "metadata": {}},
            "create_time": None,
            "update_time": None,
            "content": {"content_type": "text", "parts": [text]},
            "status": "finished_successfully",
            "end_turn": True,
            "weight": 1.0,
            "metadata": {},
            "recipient": "all",
            "channel": None,
        }
        mapping[node_id] = {"id": node_id, "message": msg, "parent": parent, "children": []}
        mapping[parent]["children"].append(node_id)
        parent = node_id
        current = node_id
    payload = {
        "title": "t",
        "create_time": 123.0,
        "update_time": 456.0,
        "mapping": mapping,
        "current_node": current,
        "conversation_id": conversation_id,
        "id": conversation_id,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_extract_answer_matches_user_question(tmp_path: Path) -> None:
    q = "深圳明天大概多少度？给我一句话就行。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": q},
            {"role": "assistant", "text": "大概二十多度，注意早晚温差。"},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    assert ans == "大概二十多度，注意早晚温差。"


def test_extract_answer_prefers_longest_candidate_in_matched_window(tmp_path: Path) -> None:
    q = "请读取我上传的 zip，并按要求输出。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": q},
            {"role": "assistant", "text": '{\n  "path": "/mnt/data/input.zip"\n}'},
            {"role": "assistant", "text": "文件当前不可访问，请重试上传或检查格式。"},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    # Current behavior: pick the longest candidate, which is the JSON path string.
    assert ans == '{\n  "path": "/mnt/data/input.zip"\n}'


def test_extract_answer_matches_when_question_is_substring(tmp_path: Path) -> None:
    q = "请基于附件逐页复审：按 1-20 页逐页列出保留/微调/重做，并给出具体修改指令（每页一行）。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": "Attached: gemini_deck_v1.pdf\n\n" + q},
            {"role": "assistant", "text": "OK"},
        ],
    )
    ans = _extract_answer_from_conversation_export(
        export_path=export_path,
        question=q,
        allow_fallback_last_assistant=False,
    )
    assert ans == "OK"


def test_extract_answer_from_mapping_export(tmp_path: Path) -> None:
    q = "请用一句话解释什么是 Pydantic。"
    export_path = tmp_path / "conversation.json"
    _write_mapping_export(
        export_path,
        conversation_id="12345678-1234-1234-1234-1234567890ab",
        nodes=[
            ("user", q),
            ("assistant", "Pydantic 是一个基于类型注解做数据校验与序列化的 Python 库。"),
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    assert ans == "Pydantic 是一个基于类型注解做数据校验与序列化的 Python 库。"


def test_extract_answer_picks_reply_after_best_match(tmp_path: Path) -> None:
    q = "我想把 maint_daemon 做成常驻维护工程师：请给出模块划分与落盘结构。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "a"},
            {"role": "user", "text": q + "\n"},
            {"role": "assistant", "text": "b"},
            {"role": "user", "text": "other"},
            {"role": "assistant", "text": "c"},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    assert ans == "b"


def test_extract_answer_returns_none_when_reply_missing(tmp_path: Path) -> None:
    q = "请给我一句话总结。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "a"},
            {"role": "user", "text": q},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    assert ans is None


def test_extract_answer_deep_research_prefers_longest_candidate(tmp_path: Path) -> None:
    q = "请做 Deep Research：给我一个可执行的方案。"
    ack = "我将立即开展深入研究，报告准备好后我会一次性发给你。"
    report = "## 调研报告\n\n" + ("内容。" * 1500)
    tail = "如需我继续补充细节，请告诉我。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": q},
            {"role": "assistant", "text": ack},
            {"role": "assistant", "text": report},
            {"role": "assistant", "text": tail},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q, deep_research=True)
    assert ans == report


def test_deep_research_ack_is_not_final() -> None:
    ack_cn = (
        "明白，我将开始对中国卫通（601698.SH）进行深度调研。"
        "稍后将为你交付完整结构化报告。你可以继续与我交流其他内容。"
    )
    assert _deep_research_is_ack(ack_cn)
    assert not _deep_research_export_should_finalize(ack_cn)

    report = "## 调研报告\n\n" + ("内容。" * 800)
    assert not _deep_research_is_ack(report)
    assert _deep_research_export_should_finalize(report)

def test_extract_answer_falls_back_to_last_assistant(tmp_path: Path) -> None:
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": "x"},
            {"role": "assistant", "text": "a"},
            {"role": "user", "text": "y"},
            {"role": "assistant", "text": "b"},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question="nope")
    assert ans == "b"

def test_extract_answer_no_match_returns_none_when_fallback_disabled(tmp_path: Path) -> None:
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": "x"},
            {"role": "assistant", "text": "a"},
        ],
    )
    ans = _extract_answer_from_conversation_export(
        export_path=export_path,
        question="nope",
        allow_fallback_last_assistant=False,
    )
    assert ans is None


def test_extract_answer_normalizes_dom_copy_code_block(tmp_path: Path) -> None:
    q = "请只输出 JSON。"
    export_path = tmp_path / "conversation.json"
    _write_export(
        export_path,
        [
            {"role": "user", "text": q},
            {"role": "assistant", "text": 'json\nCopy code\n{"a": 1}'},
        ],
    )
    ans = _extract_answer_from_conversation_export(export_path=export_path, question=q)
    assert ans == '```json\n{"a": 1}\n```'


def test_extract_answer_ignores_assistant_tool_call_turns_in_mapping_export(tmp_path: Path) -> None:
    q = "请给出 OpenClaw 集成建议。"
    export_path = tmp_path / "conversation.json"
    root = "client-created-root"
    q_node = "node-user"
    tool_call_node = "node-assistant-tool-call"
    tool_result_node = "node-tool-result"
    thoughts_node = "node-assistant-thoughts"

    mapping = {
        root: {"id": root, "message": None, "parent": None, "children": [q_node]},
        q_node: {
            "id": q_node,
            "parent": root,
            "children": [tool_call_node],
            "message": {
                "id": q_node,
                "author": {"role": "user", "name": None, "metadata": {}},
                "content": {"content_type": "text", "parts": [q]},
                "status": "finished_successfully",
                "end_turn": True,
                "metadata": {},
                "recipient": "all",
            },
        },
        tool_call_node: {
            "id": tool_call_node,
            "parent": q_node,
            "children": [tool_result_node],
            "message": {
                "id": tool_call_node,
                "author": {"role": "assistant", "name": None, "metadata": {}},
                "content": {
                    "content_type": "code",
                    "text": '{"open":[{"ref_id":"https://example.com"}],"response_length":"short"}',
                },
                "status": "finished_successfully",
                "end_turn": False,
                "metadata": {},
                "recipient": "web.run",
            },
        },
        tool_result_node: {
            "id": tool_result_node,
            "parent": tool_call_node,
            "children": [thoughts_node],
            "message": {
                "id": tool_result_node,
                "author": {"role": "tool", "name": "web.run", "metadata": {}},
                "content": {"content_type": "text", "parts": [""]},
                "status": "finished_successfully",
                "end_turn": None,
                "metadata": {},
                "recipient": "all",
            },
        },
        thoughts_node: {
            "id": thoughts_node,
            "parent": tool_result_node,
            "children": [],
            "message": {
                "id": thoughts_node,
                "author": {"role": "assistant", "name": None, "metadata": {}},
                "content": {"content_type": "thoughts", "thoughts": [{"summary": "thinking", "content": "..."}]},
                "status": "finished_successfully",
                "end_turn": False,
                "metadata": {},
                "recipient": "all",
            },
        },
    }
    payload = {
        "mapping": mapping,
        "current_node": thoughts_node,
        "conversation_id": "conv-1",
        "id": "conv-1",
    }
    export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ans = _extract_answer_from_conversation_export(
        export_path=export_path,
        question=q,
        allow_fallback_last_assistant=False,
    )
    assert ans is None


def test_should_prefer_conversation_answer() -> None:
    assert _should_prefer_conversation_answer(candidate="hello" + (" world" * 60), current="hello")
    assert not _should_prefer_conversation_answer(candidate="hello", current="hello" + (" world" * 60))
    assert _should_prefer_conversation_answer(candidate="abc def ghi" + (" x" * 200), current="abc*")


def test_should_not_prefer_conversation_answer_with_internal_markup_when_current_is_clean() -> None:
    clean = "## Report\n\n- Clean markdown with [example.com](https://example.com)\n"
    candidate = "## Report\n\n- Dirty export with internal token citeturn1view0\n"
    assert not _should_prefer_conversation_answer(candidate=candidate, current=clean)
