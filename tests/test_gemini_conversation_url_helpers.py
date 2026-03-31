from __future__ import annotations

from chatgpt_web_mcp.server import (
    _gemini_build_conversation_url,
    _gemini_conversation_id_from_jslog,
    _gemini_conversation_id_from_url,
    _gemini_is_base_app_url,
)


def test_gemini_conversation_id_from_url_parses_thread_url() -> None:
    assert _gemini_conversation_id_from_url("https://gemini.google.com/app/88b014d5748a30d0") == "88b014d5748a30d0"


def test_gemini_conversation_id_from_url_ignores_homepage_url() -> None:
    assert _gemini_conversation_id_from_url("https://gemini.google.com/app") is None
    assert _gemini_is_base_app_url("https://gemini.google.com/app") is True


def test_gemini_conversation_id_from_jslog_extracts_id() -> None:
    jslog = (
        "186014;track:generic_click;BardVeMetadataKey:[null,null,null,null,null,null,null,"
        '["c_d53c54d7d12cebfc",null,0,5]];mutable:true'
    )
    assert _gemini_conversation_id_from_jslog(jslog) == "d53c54d7d12cebfc"


def test_gemini_build_conversation_url_preserves_query_params() -> None:
    url = _gemini_build_conversation_url(
        base_url="https://gemini.google.com/app?authuser=1",
        conversation_id="88b014d5748a30d0",
    )
    assert url == "https://gemini.google.com/app/88b014d5748a30d0?authuser=1"

