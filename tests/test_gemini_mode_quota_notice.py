import datetime

from chatgpt_web_mcp.server import _gemini_parse_usage_limit_reset_at, _gemini_quota_notice_from_text


def _tz8() -> datetime.tzinfo:
    return datetime.timezone(datetime.timedelta(hours=8))


def test_gemini_usage_limit_reset_at_parses_month_day_time() -> None:
    now = datetime.datetime(2026, 1, 1, 14, 0, tzinfo=_tz8())
    text = "已达到思考模式的用量限额。用量限额将于 1月1日 15:39 重置。在此之前，系统将使用其他模型回答问题。"
    reset_at = _gemini_parse_usage_limit_reset_at(text, now=now)

    assert reset_at == datetime.datetime(2026, 1, 1, 15, 39, tzinfo=_tz8()).timestamp()


def test_gemini_usage_limit_reset_at_rolls_year_when_past() -> None:
    now = datetime.datetime(2026, 12, 31, 23, 50, tzinfo=_tz8())
    text = "用量限额将于 1月1日 00:10 重置"
    reset_at = _gemini_parse_usage_limit_reset_at(text, now=now)

    assert reset_at == datetime.datetime(2027, 1, 1, 0, 10, tzinfo=_tz8()).timestamp()


def test_gemini_quota_notice_from_text_includes_retry_after_and_not_before() -> None:
    now = datetime.datetime(2026, 1, 1, 14, 0, tzinfo=_tz8())
    text = "已达到思考模式的用量限额。用量限额将于 1月1日 15:39 重置。在此之前，系统将使用其他模型回答问题。"
    info = _gemini_quota_notice_from_text(text, now=now)

    assert info is not None
    assert info["reset_at"] == datetime.datetime(2026, 1, 1, 15, 39, tzinfo=_tz8()).timestamp()
    assert info["retry_after_seconds"] > 0
    assert info["not_before"] == info["reset_at"]

