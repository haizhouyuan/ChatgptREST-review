from __future__ import annotations

from chatgpt_web_mcp import server as s


def test_parse_thought_for_seconds_english() -> None:
    assert s._chatgpt_parse_thought_for_seconds("Thought for 2m 22s") == 142
    assert s._chatgpt_parse_thought_for_seconds("Thought for 3s") == 3
    assert s._chatgpt_parse_thought_for_seconds("Thought for 1h 2m 3s") == 3723
    assert s._chatgpt_parse_thought_for_seconds("Thought for 30 秒") == 30


def test_parse_thought_for_seconds_zh() -> None:
    assert s._chatgpt_parse_thought_for_seconds("思考了 2分22秒") == 142
    assert s._chatgpt_parse_thought_for_seconds("思考用时 3 秒") == 3
    assert s._chatgpt_parse_thought_for_seconds("耗时1小时2分钟3秒") == 3723
    assert s._chatgpt_parse_thought_for_seconds("思考了 1m 20s") == 80


def test_parse_thought_for_seconds_empty_or_zero() -> None:
    assert s._chatgpt_parse_thought_for_seconds("") is None
    assert s._chatgpt_parse_thought_for_seconds("Thought for 0s") is None
    assert s._chatgpt_parse_thought_for_seconds("思考了") is None
