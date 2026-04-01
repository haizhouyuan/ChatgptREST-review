from chatgpt_web_mcp.providers.gemini import ask as gemini_ask
from chatgpt_web_mcp.providers.gemini import core as gemini_core


def test_gemini_star_import_exports_non_deep_research_classifier() -> None:
    fn = getattr(gemini_ask, "_classify_non_deep_research_answer", None)
    assert callable(fn)
    assert fn("这是一个正常回答。") in {"completed", "in_progress"}


def test_gemini_parse_app_mentions_supports_youtube() -> None:
    tokens = gemini_core._gemini_parse_app_mentions("请用 @YouTube 找到相关视频并总结要点")
    assert ("mention", "youtube") in tokens
    assert gemini_core._GEMINI_APP_MENTION_FALLBACKS.get("youtube") == "@YouTube"
    assert gemini_core._GEMINI_APP_MENU_LABEL_RES["youtube"].search("YouTube")
