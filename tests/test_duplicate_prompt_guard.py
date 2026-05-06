from chatgpt_web_mcp.server import _is_duplicate_user_prompt


def test_is_duplicate_user_prompt_exact_match() -> None:
    assert _is_duplicate_user_prompt(question="hello", last_user_text="hello") is True


def test_is_duplicate_user_prompt_whitespace_normalized() -> None:
    assert _is_duplicate_user_prompt(question="a  b\nc", last_user_text="a b c") is True


def test_is_duplicate_user_prompt_different() -> None:
    assert _is_duplicate_user_prompt(question="hello", last_user_text="hello!") is False


def test_is_duplicate_user_prompt_missing() -> None:
    assert _is_duplicate_user_prompt(question="", last_user_text="hello") is False
    assert _is_duplicate_user_prompt(question="hello", last_user_text="") is False

