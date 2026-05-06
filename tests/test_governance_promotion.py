"""Tests for chatgptrest.governance.promotion."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chatgptrest.governance.promotion import (
    PromotionDecision,
    PromotionGate,
    batch_promote,
    promote_artifact,
)


def _make_art(
    artifact_id: str = "art-1",
    quality_score: float = 0.9,
    quarantine_weight: float = 1.0,
    stability: str = "candidate",
    age_days: int = 14,
) -> MagicMock:
    art = MagicMock()
    art.artifact_id = artifact_id
    art.quality_score = quality_score
    art.quarantine_weight = quarantine_weight
    art.stability = stability
    art.created_at = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return art


# ---------------------------------------------------------------------------
# PromotionGate
# ---------------------------------------------------------------------------

class TestPromotionGate:
    def test_eligible(self) -> None:
        gate = PromotionGate()
        d = gate.check(_make_art())
        assert d.eligible is True

    def test_not_candidate(self) -> None:
        gate = PromotionGate()
        d = gate.check(_make_art(stability="draft"))
        assert d.eligible is False
        assert "not candidate" in d.reason

    def test_low_quality(self) -> None:
        gate = PromotionGate()
        d = gate.check(_make_art(quality_score=0.5))
        assert d.eligible is False
        assert "quality" in d.reason

    def test_low_quarantine(self) -> None:
        gate = PromotionGate()
        d = gate.check(_make_art(quarantine_weight=0.3))
        assert d.eligible is False
        assert "quarantine" in d.reason

    def test_too_young(self) -> None:
        gate = PromotionGate(min_candidate_days=30)
        d = gate.check(_make_art(age_days=7))
        assert d.eligible is False
        assert "age" in d.reason

    def test_custom_threshold(self) -> None:
        gate = PromotionGate(quality_threshold=0.5)
        d = gate.check(_make_art(quality_score=0.6))
        assert d.eligible is True


# ---------------------------------------------------------------------------
# promote_artifact
# ---------------------------------------------------------------------------

class TestPromoteArtifact:
    def test_dry_run_no_transition(self) -> None:
        reg = MagicMock()
        reg.get.return_value = _make_art()
        d = promote_artifact(reg, "art-1", dry_run=True)
        assert d.eligible is True
        assert d.promoted is False
        reg.transition_stability.assert_not_called()

    def test_apply_transitions(self) -> None:
        reg = MagicMock()
        reg.get.return_value = _make_art()
        d = promote_artifact(reg, "art-1", dry_run=False)
        assert d.eligible is True
        assert d.promoted is True
        reg.transition_stability.assert_called_once_with("art-1", "approved")

    def test_not_found(self) -> None:
        reg = MagicMock()
        reg.get.return_value = None
        d = promote_artifact(reg, "missing", dry_run=True)
        assert "not found" in d.reason

    def test_audit_trail(self, tmp_path: Path) -> None:
        reg = MagicMock()
        reg.get.return_value = _make_art()
        audit = tmp_path / "audit.jsonl"
        promote_artifact(reg, "art-1", dry_run=True, audit_path=audit)
        assert audit.exists()
        rec = json.loads(audit.read_text().strip())
        assert rec["op"] == "promotion"


# ---------------------------------------------------------------------------
# batch_promote
# ---------------------------------------------------------------------------

class TestBatchPromote:
    def test_scans_and_reports(self) -> None:
        reg = MagicMock()
        arts = [_make_art(artifact_id="a1"), _make_art(artifact_id="a2", stability="draft")]
        reg.search.return_value = arts
        reg.get.side_effect = lambda aid: next(a for a in arts if a.artifact_id == aid)

        result = batch_promote(reg, dry_run=True)
        assert result["eligible"] == 1
        assert result["ineligible"] == 1

    def test_applies_promotions(self) -> None:
        reg = MagicMock()
        art = _make_art()
        reg.search.return_value = [art]
        reg.get.return_value = art

        result = batch_promote(reg, dry_run=False)
        assert result["promoted"] == 1
        reg.transition_stability.assert_called_once()
