import json

from chatgpt_web_mcp.server import (
    _chatgpt_dom_risk_observation_from_snapshot,
    _chatgpt_netlog_extract_model_route_fields_obj,
)


def test_dom_risk_observation_unusual_activity(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPT_DOM_RISK_OBSERVATION_MAX_CHARS", "120")
    obs = _chatgpt_dom_risk_observation_from_snapshot(
        phase="wait_timeout",
        title="ChatGPT",
        url="https://chatgpt.com/",
        body=(
            "Extended thinking\n"
            "Unusual activity detected\n"
            "You've sent a large number of messages in a short time, so we're doing a quick check "
            "to keep ChatGPT safe and reliable. You should get access to GPT-5 Pro again soon."
        ),
    )
    assert isinstance(obs, dict)
    assert "unusual_activity" in (obs.get("signals") or [])
    assert obs.get("matched") == "unusual_activity"
    assert obs.get("phase") == "wait_timeout"
    assert obs.get("title") == "ChatGPT"
    assert obs.get("url") == "https://chatgpt.com/"

    snippet = obs.get("snippet") or ""
    assert isinstance(snippet, str)
    assert 0 < len(snippet) <= 120


def test_dom_risk_observation_none() -> None:
    obs = _chatgpt_dom_risk_observation_from_snapshot(
        phase="ask_answer_ready",
        title="ChatGPT",
        url="https://chatgpt.com/c/xxx",
        body="All good.",
    )
    assert obs is None


def test_netlog_extract_model_route_fields_obj_sanitizes_messages() -> None:
    obj = {
        "action": "next",
        "conversation_id": "00000000-0000-0000-0000-000000000000",
        "model": "gpt-5-2-pro",
        "reasoning_effort": "extended",
        "messages": [
            {
                "id": "msg_1",
                "content": {"parts": ["SECRET_PROMPT_SHOULD_NOT_APPEAR"]},
            }
        ],
    }
    out = _chatgpt_netlog_extract_model_route_fields_obj(obj=obj)
    assert isinstance(out, dict)
    assert out.get("action") == "next"
    assert out.get("model") == "gpt-5-2-pro"
    assert out.get("messages_count") == 1
    assert "messages" not in out
    assert "SECRET_PROMPT_SHOULD_NOT_APPEAR" not in json.dumps(out, ensure_ascii=False)

