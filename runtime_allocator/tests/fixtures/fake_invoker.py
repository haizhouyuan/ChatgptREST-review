"""Fake invoker for integration testing execute_with_fallback()."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FakeInvokeResult:
    content: str = ""
    error: Optional[str] = None
    error_class: Optional[str] = None
    latency_ms: float = 100.0
    model: str = "fake-model"


class FakeInvoker:
    """Simulate LLM provider responses for testing.

    Configure per-provider behavior before calling execute_with_fallback().
    """

    def __init__(self):
        self._behaviors: dict[str, dict] = {}
        self.calls: list[dict] = []

    def set_behavior(
        self,
        provider_id: str,
        *,
        success: bool = True,
        content: str = '{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}',
        error: Optional[str] = None,
        error_class: Optional[str] = None,
        latency_ms: float = 100.0,
        bad_json: bool = False,
        schema_invalid: bool = False,
    ):
        """Set how a provider should respond."""
        self._behaviors[provider_id] = {
            "success": success,
            "content": content,
            "error": error,
            "error_class": error_class,
            "latency_ms": latency_ms,
            "bad_json": bad_json,
            "schema_invalid": schema_invalid,
        }

    def invoke(
        self,
        provider_id: str,
        messages: list[dict],
        model: str = "",
        profiles: Optional[dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
        timeout: float = 120.0,
    ) -> FakeInvokeResult:
        """Simulate an LLM invocation."""
        self.calls.append({
            "provider_id": provider_id,
            "model": model,
            "messages": messages,
            "temperature": temperature,
        })

        behavior = self._behaviors.get(provider_id, {"success": True, "content": "hello", "latency_ms": 100.0})

        time.sleep(0.001)  # Tiny realistic delay

        if behavior.get("bad_json"):
            return FakeInvokeResult(
                content="not json at all",
                latency_ms=behavior.get("latency_ms", 100.0),
                model=model,
            )

        if behavior.get("schema_invalid"):
            return FakeInvokeResult(
                content='{"product_id": "A", "decision": "invalid", "confidence": 0.9}',
                latency_ms=behavior.get("latency_ms", 100.0),
                model=model,
            )

        if not behavior.get("success", True):
            return FakeInvokeResult(
                content="",
                error=behavior.get("error", "unknown error"),
                error_class=behavior.get("error_class", "FakeError"),
                latency_ms=behavior.get("latency_ms", 100.0),
                model=model,
            )

        return FakeInvokeResult(
            content=behavior.get("content", "hello"),
            latency_ms=behavior.get("latency_ms", 100.0),
            model=model,
        )
