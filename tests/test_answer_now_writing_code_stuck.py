from __future__ import annotations

from pathlib import Path

from chatgptrest.executors import chatgpt_web_mcp as m


def test_detects_answer_now_writing_code_stuck_from_debug_text(tmp_path, monkeypatch) -> None:
    chatgptmcp_root = tmp_path / "chatgptMCP"
    (chatgptmcp_root / "artifacts").mkdir(parents=True)
    marker_file = chatgptmcp_root / "artifacts" / "marker.txt"
    marker_file.write_text("Pro thinking • Writing code\nAnswer now\n", encoding="utf-8")

    monkeypatch.setenv("CHATGPTREST_CHATGPTMCP_ROOT", str(chatgptmcp_root))
    text = m._read_chatgptmcp_debug_text(debug_artifacts={"text": "artifacts/marker.txt"})
    assert text is not None
    assert m._looks_like_answer_now_writing_code_stuck(text)


def test_detects_pro_thinking_skipping_from_debug_text(tmp_path, monkeypatch) -> None:
    chatgptmcp_root = tmp_path / "chatgptMCP"
    (chatgptmcp_root / "artifacts").mkdir(parents=True)
    marker_file = chatgptmcp_root / "artifacts" / "marker.txt"
    marker_file.write_text("ChatGPT said:\nPro thinking • Skipping\nStop\nUpdate\n", encoding="utf-8")

    monkeypatch.setenv("CHATGPTREST_CHATGPTMCP_ROOT", str(chatgptmcp_root))
    text = m._read_chatgptmcp_debug_text(debug_artifacts={"text": "artifacts/marker.txt"})
    assert text is not None
    assert m._looks_like_pro_thinking_skipping(text)


def test_debug_artifact_path_traversal_is_rejected(tmp_path, monkeypatch) -> None:
    chatgptmcp_root = tmp_path / "chatgptMCP"
    (chatgptmcp_root / "artifacts").mkdir(parents=True)
    (tmp_path / "escape.txt").write_text("Answer now\nWriting code\n", encoding="utf-8")

    monkeypatch.setenv("CHATGPTREST_CHATGPTMCP_ROOT", str(chatgptmcp_root))
    assert m._read_chatgptmcp_debug_text(debug_artifacts={"text": "../escape.txt"}) is None
