#!/usr/bin/env python3
"""Mock embedder client for Graphiti that produces deterministic embeddings without API calls."""

import hashlib

from graphiti_core.embedder.client import EmbedderClient


class MockEmbedderClient(EmbedderClient):
    """Mock embedder that returns deterministic pseudo-random embeddings."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    async def create(self, input_data: str | list[str]) -> list[float]:
        """Return a deterministic embedding based on input hash."""
        if isinstance(input_data, list):
            input_data = " ".join(input_data)
        seed = int(hashlib.md5(input_data.encode()).hexdigest(), 16)
        # Deterministic pseudo-random floats in [-1, 1]
        embedding = []
        for i in range(self.dimensions):
            val = ((seed + i * 9301 + 49297) % 233280) / 233280.0
            embedding.append(val * 2 - 1)
        return embedding

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Return deterministic embeddings for a batch."""
        return [await self.create(text) for text in input_data_list]
