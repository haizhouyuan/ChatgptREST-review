from __future__ import annotations

import time

from chatgptrest.core import mihomo_delay


def test_parse_record_ts_parses_expected_format() -> None:
    ts = mihomo_delay.parse_record_ts("2025-12-26T23:55:03+0800")
    assert ts is not None
    assert isinstance(ts, float)


def test_parse_record_ts_invalid_returns_none() -> None:
    assert mihomo_delay.parse_record_ts("") is None
    assert mihomo_delay.parse_record_ts("not-a-ts") is None


def test_consecutive_failures_ignores_interleaved_groups() -> None:
    records = [
        {"group": "G", "selected": "S", "ok": True},
        {"group": "OTHER", "selected": "X", "ok": False},
        {"group": "G", "selected": "S", "ok": False},
        {"group": "G", "selected": "S", "ok": False},
    ]
    assert mihomo_delay.consecutive_failures(records=records, group="G", selected="S") == 2


def test_last_success_record_picks_latest_ok() -> None:
    records = [
        {"group": "G", "selected": "S", "ok": True, "ts": "2025-12-26T23:50:03+0800"},
        {"group": "G", "selected": "S", "ok": False, "ts": "2025-12-26T23:55:03+0800"},
        {"group": "G", "selected": "S", "ok": True, "ts": "2025-12-27T00:00:03+0800"},
    ]
    last_ok = mihomo_delay.last_success_record(records=records, group="G", selected="S")
    assert last_ok is not None
    assert str(last_ok.get("ts")) == "2025-12-27T00:00:03+0800"


def test_recent_health_summary_counts_and_last_ok_age(monkeypatch) -> None:
    records = [
        {"group": "G", "selected": "S", "ok": True, "ts": "2025-12-26T23:55:03+0800"},
        {"group": "G", "selected": "S", "ok": False, "ts": "2025-12-27T00:00:03+0800"},
        {"group": "G", "selected": "S", "ok": False, "ts": "2025-12-27T00:05:03+0800"},
    ]
    last_ok_ts = mihomo_delay.parse_record_ts("2025-12-26T23:55:03+0800")
    assert last_ok_ts is not None
    monkeypatch.setattr(time, "time", lambda: float(last_ok_ts) + 100.0)

    summary = mihomo_delay.recent_health_summary(records=records, group="G", selected="S", max_records=50)
    assert summary["window_n"] == 3
    assert summary["ok_n"] == 1
    assert summary["error_n"] == 2
    assert summary["consecutive_failures"] == 2
    assert summary["last_ok_age_seconds"] == 100.0

