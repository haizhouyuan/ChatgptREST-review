from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
DOC_ROOT = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"

sys.path.insert(0, str(ROOT))
from tools.validate_finbot_capability_platform import (  # noqa: E402
    PASS_STATUS,
    validate_alerts,
    validate_matrix,
    validate_memos,
    validate_negative_fixtures,
    validate_payload,
    validate_valuation,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_readiness_matrix_does_not_fake_guarded_connectors():
    matrix = read_json(DOC_ROOT / "02_data_source_readiness_matrix.json")
    errors = validate_matrix(matrix)
    assert errors == []
    by_name = {row["name"]: row for row in matrix["sources"]}
    for name in ["Readwise", "Zotero", "Alpaca watch-only", "Daloopa", "Quartr", "Binance risk context"]:
        assert by_name[name]["status"] == "candidate_to_enable"


def test_endpoint_only_cannot_be_workflow_verified():
    matrix = {
        "sources": [
            {
                "name": "Alpaca watch-only",
                "status": "workflow_verified",
                "proof_level": "endpoint_alive_only",
            }
        ]
    }
    errors = validate_matrix(matrix)
    assert any("endpoint" in err or "guarded" in err.lower() for err in errors)


def test_valuation_range_is_research_estimate_only():
    payload = read_json(DOC_ROOT / "08_valuation_range_research_prototype.json")
    assert validate_valuation(payload) == []
    bad = {"entries": [{"case_id": "x", "range_type": "target_price", "target_price": 12}]}
    assert validate_valuation(bad)


def test_alerts_are_human_review_only():
    payload = read_json(DOC_ROOT / "09_alert_monitoring_prototype.json")
    assert validate_alerts(payload) == []
    bad = {"alerts": [{"alert_id": "bad", "alert_scope": "production_watchlist", "alert_type": "buy_signal"}]}
    assert validate_alerts(bad)


def test_decision_memo_rejects_buy_sell_hold():
    payload = read_json(DOC_ROOT / "10_decision_memo_prototype.json")
    assert validate_memos(payload) == []
    assert validate_payload({"decision_status": "buy", "recommendation": "buy"})


def test_negative_fixtures_fail_as_expected():
    errors, results = validate_negative_fixtures()
    assert errors == []
    assert results
    assert all(row["failed_as_expected"] for row in results)


def test_final_validation_status_when_present():
    final_path = DOC_ROOT / "14_final_validation.json"
    if final_path.exists():
        final = read_json(final_path)
        assert final["status"] in {PASS_STATUS, "PENDING_LIVE_READBACK", "PRE_LIVE_PASS_PENDING_LIVE", "failed"}
