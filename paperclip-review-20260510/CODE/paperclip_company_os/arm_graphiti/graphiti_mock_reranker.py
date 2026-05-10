#!/usr/bin/env python3
"""Mock cross-encoder client for Graphiti that produces deterministic scores without API calls."""

from graphiti_core.cross_encoder.client import CrossEncoderClient


class MockRerankerClient(CrossEncoderClient):
    """Mock reranker that returns deterministic scores based on string overlap."""

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        """Rank passages by simple word overlap with query."""
        query_words = set(query.lower().split())
        scored = []
        for passage in passages:
            passage_words = set(passage.lower().split())
            overlap = len(query_words & passage_words)
            score = min(overlap / max(len(query_words), 1), 1.0)
            scored.append((passage, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
