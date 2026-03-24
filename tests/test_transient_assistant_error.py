from __future__ import annotations


from chatgptrest.executors import chatgpt_web_mcp as m


def test_message_stream_error_is_transient() -> None:
    assert m._looks_like_transient_assistant_error("Error in message stream")

