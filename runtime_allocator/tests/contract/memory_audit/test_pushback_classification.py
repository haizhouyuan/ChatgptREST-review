"""Contract: Pushback signals are classified into correct categories."""

import tempfile
from pathlib import Path

import pytest

from runtime_allocator.memory_audit_agent import MemoryAuditAgent
from runtime_allocator.schemas.memory_audit import PushbackCategory


class TestPushbackClassification:
    def test_output_preference_detected(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("User: don't output JSON, just give me plain text\n")
            f.write("Agent: OK, here is plain text\n")
            path = f.name

        result = agent.extract_from_session("sess_001", path)
        constraints = result["constraints"]
        assert len(constraints) >= 1
        assert constraints[0]["category"] == PushbackCategory.OUTPUT_PREFERENCE.value
        Path(path).unlink()

    def test_authority_boundary_detected(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("User: this is outside your role, stop doing it\n")
            path = f.name

        result = agent.extract_from_session("sess_002", path)
        constraints = result["constraints"]
        assert len(constraints) >= 1
        assert constraints[0]["category"] == PushbackCategory.AUTHORITY_BOUNDARY.value
        Path(path).unlink()

    def test_model_lane_policy_detected(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("User: use a better model instead, this is not enough quality\n")
            path = f.name

        result = agent.extract_from_session("sess_003", path)
        constraints = result["constraints"]
        assert len(constraints) >= 1
        assert constraints[0]["category"] == PushbackCategory.MODEL_LANE_POLICY.value
        Path(path).unlink()
