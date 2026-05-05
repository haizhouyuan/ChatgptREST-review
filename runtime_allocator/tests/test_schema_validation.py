"""D5: Schema validation tests — malformed output triggers fallback."""

from __future__ import annotations

import pytest

from runtime_allocator.schemas import CommerceDecisionOutput
from runtime_allocator.skill_agent import _try_validate_schema


class TestTryValidateSchema:
    def test_valid_json_passes(self):
        raw = '{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}'
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert ok
        assert obj.decision == "approve"
        assert err is None

    def test_invalid_decision_fails(self):
        raw = '{"product_id": "A", "decision": "invalid", "confidence": 0.9}'
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert not ok
        assert "decision" in err.lower() or "validation" in err.lower()

    def test_missing_required_fails(self):
        raw = '{"product_id": "A", "decision": "approve", "confidence": 0.9}'  # missing rationale
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        # rationale is required (no default)
        assert not ok
        assert "rationale" in err.lower()

    def test_bad_json_fails(self):
        raw = "not json at all"
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert not ok
        assert "json" in err.lower()

    def test_confidence_out_of_range_fails(self):
        raw = '{"product_id": "A", "decision": "approve", "confidence": 2.0}'
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert not ok
        assert "confidence" in err.lower()

    def test_evidence_refs_parsed(self):
        raw = (
            '{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.95,'
            ' "evidence_refs": [{"source_id": "src1", "relevance": "strong"}]}'
        )
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert ok
        assert len(obj.evidence_refs) == 1
        assert obj.evidence_refs[0].source_id == "src1"


class TestSchemaAssumptionGaps:
    def test_assumptions_field_present(self):
        raw = (
            '{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9,'
            ' "assumptions": ["price stable"], "data_gaps": ["no competitor data"]}'
        )
        ok, obj, err = _try_validate_schema(raw, CommerceDecisionOutput)
        assert ok
        assert obj.assumptions == ["price stable"]
        assert obj.data_gaps == ["no competitor data"]
