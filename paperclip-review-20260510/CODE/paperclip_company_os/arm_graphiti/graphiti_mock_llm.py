#!/usr/bin/env python3
"""Mock LLM client for Graphiti that produces deterministic extractions without API calls.

This allows the evaluation pipeline to run without an OpenAI API key.
Results reflect structural correctness of the pipeline, not extraction quality.
"""

import json
from typing import Any

from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.prompts.models import Message
from pydantic import BaseModel


class MockLLMClient(LLMClient):
    """Mock LLM client that returns minimal deterministic responses for Graphiti evaluation."""

    def __init__(self, config: LLMConfig | None = None, cache: bool = False):
        super().__init__(config=config, cache=cache)

    def _get_provider_type(self) -> str:
        return "mock"

    async def generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size: ModelSize = ModelSize.medium,
        group_id: str | None = None,
        prompt_name: str | None = None,
    ) -> dict[str, Any]:
        """Override to unpack tuple and return just the dict (like OpenAIClient)."""
        response, _input_tokens, _output_tokens = await self._generate_response(
            messages, response_model, max_tokens or self.max_tokens, model_size
        )
        return response

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 16384,
        model_size: ModelSize = ModelSize.medium,
    ) -> tuple[dict[str, Any], int, int]:
        """Return a minimal deterministic response based on prompt content."""
        prompt_text = " ".join(m.content for m in messages if m.content)

        result: dict[str, Any]

        # Graphiti node extraction expects ExtractedEntities
        if response_model and "ExtractedEntities" in str(response_model):
            result = {"extracted_entities": []}
        # Graphiti edge extraction expects ExtractedEdges
        elif response_model and "ExtractedEdges" in str(response_model):
            result = {"edges": []}
        # Graphiti episode summary
        elif "summary" in prompt_text.lower() or "saga" in prompt_text.lower():
            result = {"summary": "Mock episode summary for evaluation pipeline."}
        # Graphiti search/retrieval
        elif "search" in prompt_text.lower() or "query" in prompt_text.lower():
            result = {"results": []}
        # Graphiti deduplication / community building
        elif "dedup" in prompt_text.lower() or "community" in prompt_text.lower() or "group" in prompt_text.lower():
            result = {"communities": [], "merged_nodes": []}
        # Temporal reasoning
        elif "valid" in prompt_text.lower() or "invalid" in prompt_text.lower() or "time" in prompt_text.lower():
            result = {"valid_at": "2024-01-01T00:00:00Z", "invalid_at": None}
        else:
            result = {"content": "Mock response for evaluation pipeline."}

        # If a response model is expected, try to fit result into it
        if response_model:
            try:
                validated = response_model(**result)
                return validated.model_dump(), 100, 50
            except Exception:
                # Try with empty/default fields
                try:
                    empty = self._build_empty_response(response_model)
                    return empty, 100, 50
                except Exception:
                    return result, 100, 50

        return result, 100, 50

    def _build_empty_response(self, response_model: type[BaseModel]) -> dict[str, Any]:
        """Build a minimal valid response for a given Pydantic model."""
        empty: dict[str, Any] = {}
        for name, field in response_model.model_fields.items():
            annotation = field.annotation
            # Check if it's a list type
            if hasattr(annotation, '__origin__') and annotation.__origin__ is list:
                empty[name] = []
            elif hasattr(annotation, '__args__') and list in annotation.__args__:
                empty[name] = []
            elif annotation is str:
                empty[name] = ""
            elif annotation is int:
                empty[name] = 0
            elif annotation is float:
                empty[name] = 0.0
            elif annotation is bool:
                empty[name] = False
            else:
                empty[name] = None
        return empty
