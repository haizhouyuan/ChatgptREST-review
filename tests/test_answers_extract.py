"""Regression tests for _answers.py extraction — verify critical imports are present."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def test_answers_write_answer_file_no_name_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_chatgpt_write_answer_file must not raise NameError (uuid was missing)."""
    monkeypatch.setenv("MCP_ANSWER_DIR", str(tmp_path))
    from chatgpt_web_mcp._answers import _chatgpt_write_answer_file

    result = _chatgpt_write_answer_file(
        answer="hello world",
        answer_format="text",
        tool="test",
        run_id="r1",
        conversation_url=None,
    )
    assert "answer_id" in result
    assert "answer_path" in result
    assert Path(result["answer_path"]).exists()


def test_answers_conversation_id_from_url_no_name_error() -> None:
    """_chatgpt_conversation_id_from_url must not raise NameError (urlparse was missing)."""
    from chatgpt_web_mcp._answers import _chatgpt_conversation_id_from_url

    # ChatGPT thread URL
    cid = _chatgpt_conversation_id_from_url("https://chatgpt.com/c/67bc52cf-2d68-8012-bf1a-c0124dbb5420")
    assert cid == "67bc52cf-2d68-8012-bf1a-c0124dbb5420"

    # No conversation ID in URL
    assert _chatgpt_conversation_id_from_url("https://chatgpt.com/") is None

    # Empty string
    assert _chatgpt_conversation_id_from_url("") is None


def test_answers_write_conversation_export_no_name_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_chatgpt_write_conversation_export_file must not raise NameError (uuid was missing)."""
    monkeypatch.setenv("MCP_CONVERSATION_DIR", str(tmp_path))
    from chatgpt_web_mcp._answers import _chatgpt_write_conversation_export_file

    result = _chatgpt_write_conversation_export_file(
        conversation_json='{"test": true}',
        tool="test",
        run_id="r1",
        conversation_url=None,
        conversation_id=None,
    )
    assert "export_id" in result
    assert "export_path" in result
    assert Path(result["export_path"]).exists()


def test_answers_maybe_offload_uses_imported_helper() -> None:
    """_chatgpt_maybe_offload_answer_result must have _result_has_full_answer_reference."""
    from chatgpt_web_mcp._answers import _chatgpt_maybe_offload_answer_result

    # Short answer — should not be truncated
    result = _chatgpt_maybe_offload_answer_result(
        {"answer": "short"},
        tool="test",
        run_id="r1",
        max_return_chars=1000,
    )
    assert result["answer"] == "short"
    assert result.get("answer_truncated") is False
