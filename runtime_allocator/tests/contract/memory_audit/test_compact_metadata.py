"""Contract: Compact metadata must not be treated as authority."""

import tempfile
from pathlib import Path

from runtime_allocator.memory_audit_agent import MemoryAuditAgent


class TestCompactMetadataNotAuthority:
    def test_system_compact_line_not_extracted(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("[system] Context compacted: 12 messages summarized\n")
            f.write("User: What is the weather?\n")
            path = f.name

        result = agent.extract_from_session("sess_004", path)
        # Compact metadata should not produce constraints or deltas
        assert result["constraints"] == []
        assert result["deltas"] == []
        Path(path).unlink()
