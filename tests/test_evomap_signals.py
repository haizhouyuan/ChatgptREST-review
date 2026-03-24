"""Tests for chatgptrest/evomap/signals.py"""

from __future__ import annotations

import pytest
from chatgptrest.evomap import signals


class TestSignal:
    """Tests for Signal dataclass."""

    def test_signal_default_values(self):
        """Test Signal with default values."""
        sig = signals.Signal()
        assert sig.signal_id == ""
        assert sig.trace_id == ""
        assert sig.signal_type == ""
        assert sig.source == ""
        assert sig.timestamp == ""
        assert sig.domain == ""
        assert sig.data == {}

    def test_signal_with_values(self):
        """Test Signal with all values set."""
        sig = signals.Signal(
            signal_id="sig_123",
            trace_id="trace_456",
            signal_type="route_selected",
            source="advisor",
            timestamp="2024-01-01T00:00:00Z",
            domain="routing",
            data={"key": "value"},
        )
        assert sig.signal_id == "sig_123"
        assert sig.trace_id == "trace_456"
        assert sig.signal_type == "route_selected"
        assert sig.source == "advisor"
        assert sig.timestamp == "2024-01-01T00:00:00Z"
        assert sig.domain == "routing"
        assert sig.data == {"key": "value"}

    def test_signal_to_dict(self):
        """Test Signal.to_dict() serialization."""
        sig = signals.Signal(
            signal_id="sig_123",
            trace_id="trace_456",
            signal_type="gate.passed",
            source="gatekeeper",
            timestamp="2024-01-01T00:00:00Z",
            domain="gate",
            data={"score": 0.95},
        )
        d = sig.to_dict()
        assert d == {
            "signal_id": "sig_123",
            "trace_id": "trace_456",
            "signal_type": "gate.passed",
            "source": "gatekeeper",
            "timestamp": "2024-01-01T00:00:00Z",
            "domain": "gate",
            "data": {"score": 0.95},
        }

    def test_signal_to_dict_empty(self):
        """Test Signal.to_dict() with empty signal."""
        sig = signals.Signal()
        d = sig.to_dict()
        assert d == {
            "signal_id": "",
            "trace_id": "",
            "signal_type": "",
            "source": "",
            "timestamp": "",
            "domain": "",
            "data": {},
        }

    def test_signal_data_mutability(self):
        """Test that Signal data dict can be modified after creation."""
        sig = signals.Signal()
        sig.data["new_key"] = "new_value"
        assert sig.data == {"new_key": "new_value"}

    def test_signal_with_complex_data(self):
        """Test Signal with complex nested data."""
        complex_data = {
            "findings": [
                {"id": "R-001", "severity": "Critical", "file": "main.py", "line": 42},
                {"id": "R-002", "severity": "High", "file": "utils.py", "line": 10},
            ],
            "metadata": {
                "agent": "cc4-rhea",
                "template": "v1_structured",
                "quality_score": 0.85,
            },
        }
        sig = signals.Signal(
            signal_type="report.step_completed",
            source="report",
            domain="report",
            data=complex_data,
        )
        d = sig.to_dict()
        assert len(d["data"]["findings"]) == 2
        assert d["data"]["metadata"]["agent"] == "cc4-rhea"


class TestSignalType:
    """Tests for SignalType constants."""

    def test_signal_type_constants_exist(self):
        """Test all expected signal type constants exist."""
        assert signals.SignalType.ROUTE_SELECTED == "route.selected"
        assert signals.SignalType.FUNNEL_STAGE_COMPLETED == "funnel.stage_completed"
        assert signals.SignalType.REPORT_STEP_COMPLETED == "report.step_completed"
        assert signals.SignalType.GATE_PASSED == "gate.passed"
        assert signals.SignalType.GATE_FAILED == "gate.failed"
        assert signals.SignalType.DISPATCH_COMPLETED == "dispatch.task_completed"
        assert signals.SignalType.DISPATCH_FAILED == "dispatch.task_failed"
        assert signals.SignalType.KB_WRITEBACK == "kb.writeback"
        assert signals.SignalType.SKILL_LEARNED == "skill.learned"
        assert signals.SignalType.TOOL_FAILURE == "tool.failure"
        assert signals.SignalType.TOOL_RECOVERY == "tool.recovery"
        assert signals.SignalType.LLM_CALL_COMPLETED == "llm.call_completed"
        assert signals.SignalType.LLM_CALL_FAILED == "llm.call_failed"
        assert signals.SignalType.LLM_MODEL_SWITCHED == "llm.model_switched"

    def test_normalize_signal_type_maps_legacy_route_name(self):
        assert signals.normalize_signal_type("route_selected") == signals.SignalType.ROUTE_SELECTED
        assert signals.normalize_signal_type(signals.SignalType.ROUTE_SELECTED) == signals.SignalType.ROUTE_SELECTED

    def test_signal_type_values_are_strings(self):
        """Test all SignalType values are strings."""
        for attr in dir(signals.SignalType):
            if not attr.startswith("_"):
                value = getattr(signals.SignalType, attr)
                assert isinstance(value, str), f"{attr} is not a string"
                assert len(value) > 0, f"{attr} is empty"


class TestSignalDomain:
    """Tests for SignalDomain constants."""

    def test_signal_domain_constants_exist(self):
        """Test all expected signal domain constants exist."""
        assert signals.SignalDomain.ROUTING == "routing"
        assert signals.SignalDomain.FUNNEL == "funnel"
        assert signals.SignalDomain.REPORT == "report"
        assert signals.SignalDomain.GATE == "gate"
        assert signals.SignalDomain.DISPATCH == "dispatch"
        assert signals.SignalDomain.KB == "kb"
        assert signals.SignalDomain.SKILL == "skill"
        assert signals.SignalDomain.TOOL == "tool"
        assert signals.SignalDomain.LLM == "llm"

    def test_signal_domain_values_are_strings(self):
        """Test all SignalDomain values are strings."""
        for attr in dir(signals.SignalDomain):
            if not attr.startswith("_"):
                value = getattr(signals.SignalDomain, attr)
                assert isinstance(value, str), f"{attr} is not a string"
                assert len(value) > 0, f"{attr} is empty"


class TestSignalEdgeCases:
    """Edge case tests for signals."""

    def test_signal_with_unicode_data(self):
        """Test Signal with Unicode characters in data."""
        sig = signals.Signal(
            signal_type="route_selected",
            data={"message": "你好世界", "emoji": "🎉"},
        )
        d = sig.to_dict()
        assert d["data"]["message"] == "你好世界"
        assert d["data"]["emoji"] == "🎉"

    def test_signal_with_special_characters(self):
        """Test Signal with special characters."""
        sig = signals.Signal(
            signal_type="gate.passed",
            data={"path": "/tmp/file.txt", "regex": r"\b\w+\b"},
        )
        d = sig.to_dict()
        assert d["data"]["path"] == "/tmp/file.txt"

    def test_signal_with_none_values_in_data(self):
        """Test Signal with None values in data dict."""
        sig = signals.Signal(
            signal_type="dispatch.task_completed",
            data={"value": None, "exists": True},
        )
        d = sig.to_dict()
        assert d["data"]["value"] is None
        assert d["data"]["exists"] is True

    def test_signal_with_numeric_data(self):
        """Test Signal with numeric values in data."""
        sig = signals.Signal(
            signal_type="llm.call_completed",
            data={
                "latency_ms": 1500,
                "tokens": 4500,
                "temperature": 0.7,
                "score": 0.95,
            },
        )
        d = sig.to_dict()
        assert d["data"]["latency_ms"] == 1500
        assert d["data"]["score"] == 0.95

    def test_signal_with_empty_string_values(self):
        """Test Signal with empty string values."""
        sig = signals.Signal(
            signal_id="",
            trace_id="",
            signal_type="",
            source="",
            timestamp="",
            domain="",
            data={},
        )
        d = sig.to_dict()
        # All empty strings should be preserved
        assert d["signal_id"] == ""
        assert d["trace_id"] == ""

    def test_signal_with_large_data(self):
        """Test Signal with large data payload."""
        large_data = {"key": "x" * 10000}
        sig = signals.Signal(
            signal_type="report.step_completed",
            data=large_data,
        )
        d = sig.to_dict()
        assert len(d["data"]["key"]) == 10000
