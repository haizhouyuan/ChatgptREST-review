"""Contract: Source span (path + line) is retained on all extracted cards."""

import tempfile
from pathlib import Path

from runtime_allocator.memory_audit_agent import MemoryAuditAgent


class TestSourceSpanRetention:
    def test_constraint_has_source_span(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Line 1: hello\n")
            f.write("Line 2: User: don't generate code for me\n")
            path = f.name

        result = agent.extract_from_session("sess_007", path)
        constraints = result["constraints"]
        assert len(constraints) >= 1
        assert constraints[0]["source_path"] == path
        assert constraints[0]["source_line_or_span"] == "L2"
        Path(path).unlink()

    def test_failure_has_source_span(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Line 1: ok\n")
            f.write("Line 2: Error: schema validation failed\n")
            path = f.name

        result = agent.extract_from_session("sess_008", path)
        failures = result["failures"]
        assert len(failures) >= 1
        assert failures[0]["source_path"] == path
        assert failures[0]["source_line_or_span"] == "L2"
        Path(path).unlink()
