"""Tests for finbot_modules — extracted sub-modules from finbot.py."""
from __future__ import annotations

import pytest
from chatgptrest.finbot_modules._helpers import (
    json_dumps,
    slugify,
    normalize_match_key,
    stable_digest,
    inbox_item_id,
    text_value,
    as_float,
    normalized_claim_text,
    decision_distance,
)
from chatgptrest.finbot_modules.claim_logic import (
    stable_claim_id,
    stable_citation_id,
    support_confidence,
    claim_kind_from_row,
    claim_status_from_row,
    claim_load_bearing,
    claim_relevance_label,
    has_semantic_reversal,
    match_previous_claim,
    annotate_claim_rows,
    build_claim_objects,
)
from chatgptrest.finbot_modules.source_scoring import (
    source_quality_score,
    source_quality_band,
    source_contribution_role,
    source_focus,
    source_information_role,
)
from chatgptrest.finbot_modules.market_truth import (
    infer_market_from_ticker,
)


# ---------------------------------------------------------------------------
# _helpers tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_slugify_basic(self) -> None:
        assert slugify("Hello World!") == "hello-world"

    def test_slugify_empty(self) -> None:
        assert slugify("") == "item"

    def test_text_value_none(self) -> None:
        assert text_value(None) == ""

    def test_text_value_strips(self) -> None:
        assert text_value("  hello  ") == "hello"

    def test_as_float_valid(self) -> None:
        assert as_float("3.14") == 3.14

    def test_as_float_invalid(self) -> None:
        assert as_float("not_a_number") == 0.0

    def test_decision_distance_act(self) -> None:
        assert decision_distance("invest_now") == 0

    def test_decision_distance_watch(self) -> None:
        assert decision_distance("watch") == 2

    def test_decision_distance_archive(self) -> None:
        assert decision_distance("archive") == 4

    def test_normalize_match_key(self) -> None:
        assert normalize_match_key("Hello World!") == "helloworld"

    def test_stable_digest_deterministic(self) -> None:
        d1 = stable_digest({"key": "value"})
        d2 = stable_digest({"key": "value"})
        assert d1 == d2
        assert len(d1) == 12

    def test_inbox_item_id(self) -> None:
        result = inbox_item_id("test", "My Item")
        assert result == "test-my-item"


# ---------------------------------------------------------------------------
# claim_logic tests
# ---------------------------------------------------------------------------

class TestClaimLogic:
    def test_stable_claim_id_deterministic(self) -> None:
        id1 = stable_claim_id(candidate_id="c1", claim="test claim")
        id2 = stable_claim_id(candidate_id="c1", claim="test claim")
        assert id1 == id2
        assert id1.startswith("clm_")

    def test_stable_citation_id(self) -> None:
        cid = stable_citation_id(source_id="s1", source_name="My Source")
        assert cid.startswith("cit_")

    def test_support_confidence_high(self) -> None:
        assert support_confidence("high", "") == "high"
        assert support_confidence("", "anchor") == "high"

    def test_support_confidence_medium(self) -> None:
        assert support_confidence("medium", "") == "medium"

    def test_support_confidence_low(self) -> None:
        assert support_confidence("weak", "supporting") == "low"

    def test_claim_kind_high(self) -> None:
        assert claim_kind_from_row({"importance": "high"}) == "core"

    def test_claim_kind_medium(self) -> None:
        assert claim_kind_from_row({"importance": "medium"}) == "supporting"

    def test_claim_kind_low(self) -> None:
        assert claim_kind_from_row({"importance": "low"}) == "monitor"

    def test_claim_load_bearing(self) -> None:
        assert claim_load_bearing({"importance": "critical"}) is True
        assert claim_load_bearing({"importance": "low"}) is False

    def test_has_semantic_reversal(self) -> None:
        assert has_semantic_reversal("利润增长", "利润下滑") is True
        assert has_semantic_reversal("利润增长", "利润增长") is False

    def test_has_semantic_reversal_empty(self) -> None:
        assert has_semantic_reversal("", "test") is False

    def test_match_previous_claim_exact(self) -> None:
        row = {"claim": "test claim"}
        previous = [{"claim_text": "test claim", "claim_id": "old"}]
        result = match_previous_claim(row, previous)
        assert result.get("claim_id") == "old"

    def test_match_previous_claim_empty(self) -> None:
        row = {"claim": ""}
        result = match_previous_claim(row, [])
        assert result == {}


# ---------------------------------------------------------------------------
# source_scoring tests
# ---------------------------------------------------------------------------

class TestSourceScoring:
    def test_quality_score_empty(self) -> None:
        score = source_quality_score({})
        assert score == 0.0

    def test_quality_score_good(self) -> None:
        record = {
            "accepted_route_count": 15,
            "validated_case_count": 8,
            "supported_claim_count": 20,
            "anchor_claim_count": 10,
            "load_bearing_claim_count": 8,
            "lead_support_count": 6,
            "theme_slugs": ["a", "b", "c", "d"],
        }
        score = source_quality_score(record)
        assert score > 0.5

    def test_quality_band_core(self) -> None:
        assert source_quality_band(0.8) == "core"

    def test_quality_band_useful(self) -> None:
        assert source_quality_band(0.6) == "useful"

    def test_quality_band_monitor(self) -> None:
        assert source_quality_band(0.4) == "monitor"

    def test_quality_band_weak(self) -> None:
        assert source_quality_band(0.1) == "weak"

    def test_contribution_role_primary(self) -> None:
        assert source_contribution_role({"source_type": "primary_research"}) == "anchor"

    def test_contribution_role_broker(self) -> None:
        assert source_contribution_role({"source_type": "broker_report"}) == "corroborating"

    def test_contribution_role_explicit(self) -> None:
        assert source_contribution_role({"contribution_role": "anchor"}) == "anchor"


# ---------------------------------------------------------------------------
# market_truth tests
# ---------------------------------------------------------------------------

class TestMarketTruth:
    def test_infer_cn_with_suffix(self) -> None:
        assert infer_market_from_ticker("002025.SZ") == "CN"

    def test_infer_cn_bare(self) -> None:
        assert infer_market_from_ticker("600519") == "CN"

    def test_infer_hk(self) -> None:
        assert infer_market_from_ticker("00700.HK") == "HK"

    def test_infer_us(self) -> None:
        assert infer_market_from_ticker("NVDA") == "US"

    def test_infer_unknown(self) -> None:
        assert infer_market_from_ticker("unknown123") == ""


# ---------------------------------------------------------------------------
# WP5: peer_snapshot tests
# ---------------------------------------------------------------------------

class TestPeerSnapshot:
    def test_extract_valuation_driver_revenue(self) -> None:
        from chatgptrest.finbot_modules.peer_snapshot import extract_valuation_driver_from_narrative
        narrative = "The company shows strong revenue growth and increasing market share"
        driver = extract_valuation_driver_from_narrative(narrative)
        assert "revenue_growth" in driver

    def test_extract_valuation_driver_empty(self) -> None:
        from chatgptrest.finbot_modules.peer_snapshot import extract_valuation_driver_from_narrative
        assert extract_valuation_driver_from_narrative(None) == ""
        assert extract_valuation_driver_from_narrative("") == ""

    def test_build_peer_snapshot_basic(self) -> None:
        from chatgptrest.finbot_modules.peer_snapshot import build_peer_snapshot
        result = build_peer_snapshot(
            candidate_id="test-001",
            leader_expression="Strong revenue growth expected",
            valuation_frame={"target_price": 100, "market_truth": {"price": 80}},
        )
        assert result["candidate_id"] == "test-001"
        assert result["generated_at"] > 0
        assert "valuation_driver" in result
        assert "peers" in result
        assert result["peers"] == []  # No API keys, so empty

    def test_build_peer_snapshot_reverse_dcf_hint(self) -> None:
        from chatgptrest.finbot_modules.peer_snapshot import build_peer_snapshot
        # Test with upside > 50%
        result = build_peer_snapshot(
            candidate_id="test-002",
            leader_expression="Revenue growth",
            valuation_frame={"target_price": 150, "market_truth": {"price": 80}},
        )
        assert "reverse_dcf_hint" in result
        assert "50%" in result["reverse_dcf_hint"] or "upside" in result["reverse_dcf_hint"].lower()


# ---------------------------------------------------------------------------
# WP6: transcript_provider tests
# ---------------------------------------------------------------------------

class TestTranscriptProvider:
    def test_build_transcript_packet_disabled(self) -> None:
        from chatgptrest.finbot_modules.transcript_provider import build_transcript_packet
        result = build_transcript_packet(candidate_id="AAPL")
        assert result["candidate_id"] == "AAPL"
        assert result["provider"] == "disabled"
        assert result["available"] is False
        assert "disabled_reason" in result
        assert result["items"] == []

    def test_build_transcript_packet_uses_candidate_as_symbol(self) -> None:
        from chatgptrest.finbot_modules.transcript_provider import build_transcript_packet
        result = build_transcript_packet(candidate_id="MSFT")
        assert result["candidate_id"] == "MSFT"


# ---------------------------------------------------------------------------
# WP7: primary_data_enrich tests
# ---------------------------------------------------------------------------

class TestPrimaryDataEnrich:
    def test_build_primary_data_packet_basic(self) -> None:
        from chatgptrest.finbot_modules.primary_data_enrich import build_primary_data_packet
        result = build_primary_data_packet(candidate_id="test-001")
        assert result["candidate_id"] == "test-001"
        assert result["generated_at"] > 0
        assert "primary_sources_found" in result
        assert "enriched_claim_bindings" in result
        assert "enriched_counterevidence" in result
        assert "promotion_enrichment" in result

    def test_build_primary_data_packet_with_bindings(self) -> None:
        from chatgptrest.finbot_modules.primary_data_enrich import build_primary_data_packet
        mock_bindings = [{"source_id": "source1", "claim_id": "claim1"}]
        result = build_primary_data_packet(
            candidate_id="test-002",
            claim_evidence_bindings=mock_bindings,
        )
        assert result["enriched_claim_bindings"] is not None

    def test_build_primary_data_packet_promotion_recommendation(self) -> None:
        from chatgptrest.finbot_modules.primary_data_enrich import build_primary_data_packet
        result = build_primary_data_packet(candidate_id="test-003")
        # Without primary sources, recommendation should be "no_primary_data"
        assert result["promotion_enrichment"]["promotion_recommendation"] == "no_primary_data"
