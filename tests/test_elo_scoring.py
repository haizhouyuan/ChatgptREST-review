"""Tests for finbot_modules.elo_scoring."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from chatgptrest.finbot_modules.elo_scoring import (
    DEFAULT_RATING,
    batch_elo_update,
    blended_quality_score,
    elo_confidence_label,
    elo_trend_label,
    elo_update,
    expected_score,
    load_elo_ledger,
    normalize_elo,
    save_elo_ledger,
    update_source_elo,
)


class TestExpectedScore:
    def test_equal_ratings(self):
        assert abs(expected_score(1500, 1500) - 0.5) < 0.001

    def test_higher_rated_expects_more(self):
        assert expected_score(1700, 1500) > 0.7

    def test_lower_rated_expects_less(self):
        assert expected_score(1300, 1500) < 0.3


class TestEloUpdate:
    def test_validated_increases_rating(self):
        new = elo_update(1500, "validated")
        assert new > 1500

    def test_contradicted_decreases_rating(self):
        new = elo_update(1500, "contradicted")
        assert new < 1500

    def test_neutral_near_default_stays_stable(self):
        new = elo_update(1500, "neutral")
        assert abs(new - 1500) < 1.0

    def test_unknown_outcome_treated_as_neutral(self):
        new = elo_update(1500, "unknown_value")
        assert abs(new - 1500) < 1.0

    def test_custom_k_factor(self):
        small_k = elo_update(1500, "validated", k=16)
        large_k = elo_update(1500, "validated", k=64)
        assert large_k > small_k

    def test_rating_clamp(self):
        # Repeated contradictions shouldn't go negative
        rating = 600.0
        for _ in range(100):
            rating = elo_update(rating, "contradicted")
        assert rating >= 500.0


class TestBatchEloUpdate:
    def test_multiple_validated(self):
        result = batch_elo_update(1500, ["validated", "validated", "validated"])
        assert result > 1500 + 30  # Should increase significantly

    def test_mixed_outcomes(self):
        result = batch_elo_update(1500, ["validated", "contradicted"])
        # Should be near starting value
        assert abs(result - 1500) < 30

    def test_empty_outcomes(self):
        result = batch_elo_update(1500, [])
        assert result == 1500


class TestNormalizeElo:
    def test_floor(self):
        assert normalize_elo(1000) == 0.0
        assert normalize_elo(500) == 0.0

    def test_ceiling(self):
        assert normalize_elo(2000) == 1.0
        assert normalize_elo(2500) == 1.0

    def test_midpoint(self):
        assert abs(normalize_elo(1500) - 0.5) < 0.001


class TestBlendedQualityScore:
    def test_default_weights(self):
        # 60% of 80 + 40% of normalized 1500 (0.5 * 100 = 50)
        result = blended_quality_score(80.0, 1500.0)
        expected = 0.6 * 80 + 0.4 * 50  # 48 + 20 = 68
        assert abs(result - expected) < 0.1

    def test_high_elo_boost(self):
        low_elo = blended_quality_score(50.0, 1200.0)
        high_elo = blended_quality_score(50.0, 1800.0)
        assert high_elo > low_elo


class TestTrendLabel:
    def test_new(self):
        assert elo_trend_label(1500, None) == "new"

    def test_improving(self):
        assert elo_trend_label(1550, 1500) == "improving"

    def test_declining(self):
        assert elo_trend_label(1450, 1500) == "declining"

    def test_stable(self):
        assert elo_trend_label(1510, 1500) == "stable"


class TestConfidenceLabel:
    def test_high(self):
        assert elo_confidence_label(1700) == "high_confidence"

    def test_moderate(self):
        assert elo_confidence_label(1600) == "moderate_confidence"

    def test_low(self):
        assert elo_confidence_label(1450) == "low_confidence"

    def test_skeptical(self):
        assert elo_confidence_label(1300) == "skeptical"

    def test_unreliable(self):
        assert elo_confidence_label(1100) == "unreliable"


class TestLedgerPersistence:
    def test_save_and_load(self, tmp_path):
        ledger_path = tmp_path / "elo_ledger.json"
        ledger = {"src1": {"rating": 1550, "updated_at": 1.0}}
        save_elo_ledger(ledger_path, ledger)
        loaded = load_elo_ledger(ledger_path)
        assert loaded["src1"]["rating"] == 1550

    def test_load_missing_file(self, tmp_path):
        result = load_elo_ledger(tmp_path / "nonexistent.json")
        assert result == {}

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not json")
        result = load_elo_ledger(path)
        assert result == {}


class TestUpdateSourceElo:
    def test_new_source(self):
        ledger = {}
        entry = update_source_elo(ledger, "src1", ["validated"])
        assert entry["rating"] > DEFAULT_RATING
        # First update: previous is DEFAULT_RATING, delta is small from single validated
        assert entry["trend_label"] in {"stable", "improving"}
        assert "src1" in ledger

    def test_existing_source(self):
        ledger = {"src1": {"rating": 1500, "outcome_history": []}}
        entry = update_source_elo(ledger, "src1", ["contradicted", "contradicted"])
        assert entry["rating"] < 1500
        assert entry["previous_rating"] == 1500

    def test_outcome_history_limited(self):
        ledger = {}
        outcomes = ["validated"] * 60
        entry = update_source_elo(ledger, "src1", outcomes)
        assert len(entry["outcome_history"]) <= 50
