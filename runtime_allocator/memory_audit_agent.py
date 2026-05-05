"""Memory Audit Agent — read-only extractor of constraints and failure patterns.

This agent reads session history and produces insight cards that go ONLY
to the review queue. It NEVER writes to AuthorityLedger, Graphiti, or any
canonical memory store.

Usage:
    from runtime_allocator.memory_audit_agent import MemoryAuditAgent
    agent = MemoryAuditAgent(store=state_store)
    agent.extract_from_session(session_id="sess_abc", transcript_path="/path/to/log")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from runtime_allocator.schemas.memory_audit import (
    AgentFailurePattern,
    MemoryDeltaCandidate,
    PushbackCategory,
    ReviewState,
    TargetMemoryLayer,
    UserConstraintCard,
)
from runtime_allocator.runtime_state import RuntimeStateStore


# Regex patterns for extracting pushback signals
_PUSHBACK_PATTERNS = [
    (
        PushbackCategory.OUTPUT_PREFERENCE,
        re.compile(
            r"(?:don't|do not|never|stop).*(?:output|generate|produce|write)",
            re.IGNORECASE,
        ),
    ),
    (
        PushbackCategory.AUTHORITY_BOUNDARY,
        re.compile(
            r"(?:you (?:are not|cannot)|outside (?:your|my)|not your (?:role|job)|unauthorized)",
            re.IGNORECASE,
        ),
    ),
    (
        PushbackCategory.MODEL_LANE_POLICY,
        re.compile(
            r"(?:wrong model|use .* instead|not .* enough quality|too expensive)",
            re.IGNORECASE,
        ),
    ),
]

_FAILURE_PATTERNS = [
    ("schema_validation_error", re.compile(r"schema.*invalid|validation.*failed", re.IGNORECASE)),
    ("timeout_error", re.compile(r"timeout|timed out", re.IGNORECASE)),
    ("rate_limit_error", re.compile(r"429|rate limit|too many requests", re.IGNORECASE)),
    ("auth_error", re.compile(r"401|unauthorized|invalid api key", re.IGNORECASE)),
]


class MemoryAuditAgent:
    """Read-only session auditor. Outputs go to review queue only."""

    def __init__(self, store: Optional[RuntimeStateStore] = None, review_queue_path: Optional[Path] = None):
        self.store = store
        self.review_queue_path = review_queue_path or Path.home() / ".paperclip" / "memory_review_queue.jsonl"
        self.review_queue_path.parent.mkdir(parents=True, exist_ok=True)

    def extract_from_session(
        self,
        session_id: str,
        transcript_path: Path | str,
    ) -> dict:
        """Extract constraints, failures, and delta candidates from a session.

        Returns a dict of extracted cards. Writes them to the review queue.
        """
        transcript_path = Path(transcript_path)
        if not transcript_path.exists():
            return {"constraints": [], "failures": [], "deltas": []}

        text = transcript_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        constraints = self._extract_constraints(session_id, transcript_path, lines)
        failures = self._extract_failures(session_id, transcript_path, lines)
        deltas = self._extract_delta_candidates(session_id, transcript_path, lines)

        result = {
            "constraints": [c.model_dump() for c in constraints],
            "failures": [f.model_dump() for f in failures],
            "deltas": [d.model_dump() for d in deltas],
        }

        self._write_to_review_queue(result)
        return result

    def _extract_constraints(
        self,
        session_id: str,
        source_path: Path,
        lines: list[str],
    ) -> list[UserConstraintCard]:
        """Extract user pushback / constraint signals."""
        constraints = []
        for i, line in enumerate(lines, start=1):
            for category, pattern in _PUSHBACK_PATTERNS:
                if pattern.search(line):
                    constraints.append(
                        UserConstraintCard(
                            source_path=str(source_path),
                            source_line_or_span=f"L{i}",
                            session_id=session_id,
                            confidence=0.7,
                            category=category,
                            constraint_text=line.strip()[:200],
                            review_state=ReviewState.PENDING,
                        )
                    )
        return constraints

    def _extract_failures(
        self,
        session_id: str,
        source_path: Path,
        lines: list[str],
    ) -> list[AgentFailurePattern]:
        """Extract recurring failure patterns from error signals."""
        failures = []
        for i, line in enumerate(lines, start=1):
            for pattern_name, pattern in _FAILURE_PATTERNS:
                if pattern.search(line):
                    failures.append(
                        AgentFailurePattern(
                            source_path=str(source_path),
                            source_line_or_span=f"L{i}",
                            session_id=session_id,
                            confidence=0.6,
                            pattern_name=pattern_name,
                            description=line.strip()[:200],
                            review_state=ReviewState.PENDING,
                        )
                    )
        return failures

    def _extract_delta_candidates(
        self,
        session_id: str,
        source_path: Path,
        lines: list[str],
    ) -> list[MemoryDeltaCandidate]:
        """Extract potential memory writes from explicit memory requests."""
        deltas = []
        memory_request_re = re.compile(
            r"(?:remember|memorize|store this|save to memory).*?[:=]\s*(.+)",
            re.IGNORECASE,
        )
        for i, line in enumerate(lines, start=1):
            match = memory_request_re.search(line)
            if match:
                value = match.group(1).strip()[:500]
                deltas.append(
                    MemoryDeltaCandidate(
                        source_path=str(source_path),
                        source_line_or_span=f"L{i}",
                        session_id=session_id,
                        confidence=0.5,
                        target_layer=TargetMemoryLayer.WORKING,
                        key=f"auto_extracted_{session_id}_{i}",
                        value=value,
                        review_state=ReviewState.PENDING,
                    )
                )
        return deltas

    def _write_to_review_queue(self, result: dict):
        """Append extracted cards to JSONL review queue."""
        with open(self.review_queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def read_review_queue(self, limit: int = 100) -> list[dict]:
        """Read back review queue entries (for inspection / testing)."""
        if not self.review_queue_path.exists():
            return []
        lines = self.review_queue_path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def clear_review_queue(self):
        """Clear the review queue. Use only in tests."""
        if self.review_queue_path.exists():
            self.review_queue_path.write_text("")
