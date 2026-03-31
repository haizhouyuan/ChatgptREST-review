from __future__ import annotations

from chatgptrest.worker.worker import _should_downgrade_when_export_missing_reply


def test_export_missing_reply_downgrades_on_empty_answer() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="", min_chars_required=0)
    assert should is True
    assert info.get("reason") == "empty_answer"


def test_export_missing_reply_downgrades_when_answer_below_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 100, min_chars_required=0)
    assert should is True
    assert info.get("reason") == "answer_below_threshold"
    assert int(info.get("threshold") or 0) >= 200


def test_export_missing_reply_does_not_downgrade_for_substantial_answer() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 250, min_chars_required=0)
    assert should is False
    assert info.get("reason") == "answer_sufficient"


def test_export_missing_reply_respects_min_chars_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 500, min_chars_required=800)
    assert should is True
    assert info.get("threshold") == 800


def test_export_missing_reply_accepts_answer_above_min_chars_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 1000, min_chars_required=800)
    assert should is False
    assert info.get("threshold") == 800

