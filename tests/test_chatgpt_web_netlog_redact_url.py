from __future__ import annotations

from chatgpt_web_mcp import server as s


def test_netlog_redacts_query_and_ids_by_default(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPT_NETLOG_LINE_MAX_CHARS", "5000")
    monkeypatch.delenv("CHATGPT_NETLOG_REDACT_QUERY", raising=False)
    monkeypatch.delenv("CHATGPT_NETLOG_REDACT_IDS", raising=False)

    url = "https://chatgpt.com/backend-api/conversation/69563bcb-bfa4-8320-a5e6-75454cbc8273?foo=bar"
    out = s._chatgpt_netlog_redact_url(url)
    assert out == "https://chatgpt.com/backend-api/conversation/<uuid>"


def test_netlog_can_keep_query_and_ids(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPT_NETLOG_LINE_MAX_CHARS", "5000")
    monkeypatch.setenv("CHATGPT_NETLOG_REDACT_QUERY", "0")
    monkeypatch.setenv("CHATGPT_NETLOG_REDACT_IDS", "0")

    url = "https://chatgpt.com/backend-api/conversation/69563bcb-bfa4-8320-a5e6-75454cbc8273?foo=bar"
    out = s._chatgpt_netlog_redact_url(url)
    assert out == url


def test_netlog_data_url_is_truncated(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPT_NETLOG_LINE_MAX_CHARS", "5000")
    url = "data:text/plain;base64,SGVsbG8gd29ybGQ="
    out = s._chatgpt_netlog_redact_url(url)
    assert out.startswith("data:")
