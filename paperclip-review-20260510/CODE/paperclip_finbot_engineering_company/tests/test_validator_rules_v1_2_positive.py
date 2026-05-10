"""Positive tests for validator_rules_v1_2.

All fixtures in fixtures/validator_rules_v1_2/positive/ should pass
the validator with zero issues.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.rules_v1_2 import validate_record, validate_records


ROOT = Path(__file__).resolve().parents[1]
POSITIVE_FIXTURES = ROOT / "fixtures/validator_rules_v1_2/positive"
NOW = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc)


def load_fixture(name: str) -> dict:
    return json.loads((POSITIVE_FIXTURES / name).read_text(encoding="utf-8"))


def codes_for(name: str) -> set[str]:
    issues = validate_record(load_fixture(name), now=NOW)
    return {issue.code for issue in issues}


def test_positive_valid_evidence_item():
    result = validate_records([load_fixture("positive_01_valid_evidence_item.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_positive_blocked_fetch_attempt():
    result = validate_records([load_fixture("positive_02_valid_blocked_fetch_attempt.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_positive_kol_content_item():
    result = validate_records([load_fixture("positive_03_valid_kol_content_item.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_positive_kol_claim_with_evidence_gap():
    result = validate_records([load_fixture("positive_04_valid_kol_claim_with_gap.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_positive_research_review_signal_window():
    result = validate_records([load_fixture("positive_05_valid_research_review_signal_window.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_positive_not_backtest_safe_signal_rule():
    result = validate_records([load_fixture("positive_06_valid_not_backtest_safe_signal_rule.json")], now=NOW)
    assert result["status"] == "pass", f"expected pass but got: {result['issues']}"
    assert result["issue_count"] == 0


def test_all_positive_fixtures_pass():
    """Sweep — every fixture in the positive directory must pass."""
    failures = []
    for fixture_path in sorted(POSITIVE_FIXTURES.glob("*.json")):
        raw = fixture_path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            records = []
        result = validate_records(records, now=NOW)
        if result["status"] != "pass":
            failures.append((fixture_path.name, result["issues"]))
    assert not failures, f"Failures: {failures}"
