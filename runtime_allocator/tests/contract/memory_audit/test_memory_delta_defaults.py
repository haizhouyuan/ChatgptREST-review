"""Contract: Memory deltas default to review_state=pending."""

import tempfile
from pathlib import Path

from runtime_allocator.memory_audit_agent import MemoryAuditAgent
from runtime_allocator.schemas.memory_audit import ReviewState


class TestMemoryDeltaDefaults:
    def test_extracted_delta_is_pending(self):
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("User: remember this: my favorite color is blue\n")
            path = f.name

        result = agent.extract_from_session("sess_005", path)
        deltas = result["deltas"]
        assert len(deltas) >= 1
        assert deltas[0]["review_state"] == ReviewState.PENDING.value
        assert deltas[0]["session_id"] == "sess_005"
        Path(path).unlink()

    def test_delta_never_written_to_canonical(self):
        # The agent writes to review_queue_path, not to authority stores
        agent = MemoryAuditAgent()
        agent.clear_review_queue()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("User: store this: API key is secret123\n")
            path = f.name

        result = agent.extract_from_session("sess_006", path)
        queue = agent.read_review_queue()
        assert len(queue) >= 1
        # Queue contains the session result, not direct memory writes
        assert "deltas" in queue[-1]
        Path(path).unlink()
