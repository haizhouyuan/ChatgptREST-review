from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.minimal_gatekeeper import validate_record, validate_records


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/no_fake_evidence"
NOW = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def codes_for(name: str) -> set[str]:
    issues = validate_record(load_fixture(name), now=NOW)
    return {issue.code for issue in issues}


def test_valid_evidence_item_passes_minimal_gatekeeper():
    result = validate_records([load_fixture("valid_evidence_item.json")], now=NOW)
    assert result["status"] == "pass"
    assert result["issue_count"] == 0


def test_kol_content_item_is_allowed_as_content_not_evidence():
    result = validate_records([load_fixture("kol_content_item_valid.json")], now=NOW)
    assert result["status"] == "pass"


def test_kol_as_evidence_item_is_blocked():
    assert "KOL_AS_EVIDENCE" in codes_for("kol_as_evidence_item.json")


def test_blocked_fetch_as_evidence_item_is_blocked():
    codes = codes_for("blocked_fetch_as_evidence_item.json")
    assert "BLOCKED_FETCH_AS_EVIDENCE" in codes
    assert "EV_MISSING_REQUIRED" in codes


def test_missing_sha256_is_blocked():
    assert "EV_MISSING_REQUIRED" in codes_for("missing_sha_evidence_item.json")


def test_forbidden_trading_language_is_blocked():
    assert "FORBIDDEN_TRADING_LANGUAGE" in codes_for("forbidden_trading_language_alert.json")


def test_future_dated_evidence_is_blocked():
    assert "FUTURE_DATED_EVIDENCE" in codes_for("future_dated_evidence_item.json")


def test_source_namespace_mismatch_is_blocked():
    assert "ID_NAMESPACE_MISMATCH" in codes_for("source_namespace_mismatch.json")
