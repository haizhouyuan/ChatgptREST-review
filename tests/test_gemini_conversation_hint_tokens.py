from chatgpt_web_mcp.server import _gemini_conversation_hint_tokens


def test_gemini_conversation_hint_tokens_keeps_chinese_with_many_ascii_tokens() -> None:
    hint = (
        "请你像 reviewer 一样阅读附件，对这轮评测做批判性评审，并给出诊断建议。\n"
        + " ".join(f"/tmp/outline-part{i:02d}.md" for i in range(60))
    )
    tokens = _gemini_conversation_hint_tokens(hint, max_tokens=24)

    assert 0 < len(tokens) <= 24
    assert any("批判性评审" in tok for tok in tokens)
    assert any("outline-part00.md" in tok for tok in tokens)
