"""Negative tests for validator_rules_v1_2.

All fixtures in fixtures/validator_rules_v1_2/negative/ should fail
the validator with at least one issue.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.rules_v1_2 import validate_record, validate_records


ROOT = Path(__file__).resolve().parents[1]
NEGATIVE_FIXTURES = ROOT / "fixtures/validator_rules_v1_2/negative"
NOW = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc)


def load_fixture(name: str) -> dict:
    return json.loads((NEGATIVE_FIXTURES / name).read_text(encoding="utf-8"))


def codes_for(name: str) -> set[str]:
    issues = validate_record(load_fixture(name), now=NOW)
    return {issue.code for issue in issues}


def test_negative_pseudo_evidence_from_blocked_fetch():
    codes = codes_for("negative_01_pseudo_evidence_from_blocked_fetch.json")
    assert "EV_BLOCKED_EVIDENCE_PSEUDO" in codes, f"expected EV_BLOCKED_EVIDENCE_PSEUDO in {codes}"


def test_negative_kol_evidence_item():
    codes = codes_for("negative_02_kol_evidence_item.json")
    assert "KOL_CLAIM_NOT_EVIDENCE_ITEM" in codes, f"expected KOL_CLAIM_NOT_EVIDENCE_ITEM in {codes}"


def test_negative_evidence_missing_sha256():
    codes = codes_for("negative_03_evidence_missing_sha256.json")
    assert "EV_MISSING_RAW_OR_SHA" in codes, f"expected EV_MISSING_RAW_OR_SHA in {codes}"


def test_negative_d_only_deep_review():
    codes = codes_for("negative_04_d_only_deep_review.json")
    assert "D_ONLY_DEEP_REVIEW_FORBIDDEN" in codes, f"expected D_ONLY_DEEP_REVIEW_FORBIDDEN in {codes}"


def test_negative_bad_window_label():
    codes = codes_for("negative_05_bad_window_label.json")
    assert "BAD_WINDOW_LABEL" in codes, f"expected BAD_WINDOW_LABEL in {codes}"


def test_negative_bad_signal_window_state():
    codes = codes_for("negative_06_bad_signal_window_state.json")
    assert "BAD_SIGNAL_WINDOW_STATE" in codes, f"expected BAD_SIGNAL_WINDOW_STATE in {codes}"


def test_negative_forbidden_trading_language():
    codes = codes_for("negative_07_forbidden_trading_language.json")
    assert "FORBIDDEN_TRADING_LANGUAGE" in codes, f"expected FORBIDDEN_TRADING_LANGUAGE in {codes}"


def test_negative_future_dated_evidence():
    codes = codes_for("negative_08_future_dated_evidence.json")
    assert "FUTURE_DATED_EVIDENCE" in codes, f"expected FUTURE_DATED_EVIDENCE in {codes}"


def test_negative_source_namespace_mismatch():
    codes = codes_for("negative_09_source_namespace_mismatch.json")
    assert "SOURCE_NAMESPACE_MISMATCH" in codes, f"expected SOURCE_NAMESPACE_MISMATCH in {codes}"


def test_negative_claim_missing_source_trace():
    codes = codes_for("negative_10_claim_missing_source_trace.json")
    assert "CLAIM_MISSING_SOURCE_TRACE" in codes, f"expected CLAIM_MISSING_SOURCE_TRACE in {codes}"


def test_negative_kol_claim_without_evidence_gap():
    codes = codes_for("negative_11_kol_claim_without_evidence_gap.json")
    assert "KOL_CLAIM_WITHOUT_EVIDENCE_GAP" in codes, f"expected KOL_CLAIM_WITHOUT_EVIDENCE_GAP in {codes}"


def test_negative_signal_window_buy_signal():
    codes = codes_for("negative_12_signal_window_buy_signal.json")
    assert "SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN" in codes, f"expected SIGNAL_WINDOW_BUY_SIGNAL_FORBIDDEN in {codes}"


def test_negative_backtest_pit_missing():
    codes = codes_for("negative_13_backtest_pit_missing.json")
    assert "BACKTEST_PIT_MISSING" in codes, f"expected BACKTEST_PIT_MISSING in {codes}"


def test_all_negative_fixtures_fail():
    """Sweep — every fixture in the negative directory must fail."""
    passes = []
    for fixture_path in sorted(NEGATIVE_FIXTURES.glob("*.json")):
        records = json.loads(fixture_path.read_text(encoding="utf-8"))
        if isinstance(records, dict):
            records = [records]
        result = validate_records(records, now=NOW)
        if result["status"] == "pass":
            passes.append(fixture_path.name)
    assert not passes, f"These negative fixtures unexpectedly passed: {passes}"
