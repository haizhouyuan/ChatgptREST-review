from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
import urllib.error

from chatgptrest.kernel.memory_manager import (
    MemoryManager,
    MemoryRecord,
    MemorySource,
    MemoryTier,
)


class MockLLMConnector:
    """Deterministic async LLM stub with scripted replies and failures."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._script: deque[dict[str, Any]] = deque()

    def queue_text(self, text: str, *, delay_seconds: float = 0.0) -> None:
        self._script.append(
            {"kind": "text", "text": str(text), "delay_seconds": float(delay_seconds)}
        )

    def queue_error(self, exc: Exception, *, delay_seconds: float = 0.0) -> None:
        self._script.append(
            {"kind": "error", "error": exc, "delay_seconds": float(delay_seconds)}
        )

    async def run(self, prompt: str, system_msg: str = "") -> str:
        self.calls.append({"prompt": prompt, "system_msg": system_msg})
        if not self._script:
            raise AssertionError("MockLLMConnector was called without a queued response")
        item = self._script.popleft()
        if item["delay_seconds"] > 0:
            await asyncio.sleep(item["delay_seconds"])
        if item["kind"] == "error":
            raise item["error"]
        return item["text"]

    async def __call__(self, prompt: str, system_msg: str = "") -> str:
        return await self.run(prompt, system_msg=system_msg)


class InMemoryAdvisorClient:
    """Scriptable advisor API stand-in with urllib-compatible dispatch."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._script: deque[dict[str, Any]] = deque()

    def queue_result(self, result: dict[str, Any], *, status_code: int = 200) -> None:
        self._script.append(
            {"kind": "result", "result": dict(result), "status_code": int(status_code)}
        )

    def queue_http_error(
        self,
        status_code: int,
        body: dict[str, Any] | str = "",
        *,
        reason: str = "advisor unavailable",
    ) -> None:
        if isinstance(body, dict):
            body_text = json.dumps(body, ensure_ascii=False)
        else:
            body_text = str(body)
        self._script.append(
            {
                "kind": "http_error",
                "status_code": int(status_code),
                "body": body_text,
                "reason": reason,
            }
        )

    def queue_error(self, exc: Exception) -> None:
        self._script.append({"kind": "error", "error": exc})

    def _next(self) -> dict[str, Any]:
        if not self._script:
            raise AssertionError("InMemoryAdvisorClient was called without a queued response")
        return self._script.popleft()

    def urlopen(self, req, timeout: int = 0):  # pragma: no cover - exercised via tests
        payload = {}
        if getattr(req, "data", None):
            payload = json.loads(req.data.decode("utf-8"))
        call = {
            "url": req.full_url,
            "headers": dict(req.header_items()),
            "payload": payload,
            "timeout": timeout,
            "method": getattr(req, "method", "POST"),
        }
        self.calls.append(call)

        item = self._next()
        if item["kind"] == "error":
            raise item["error"]
        if item["kind"] == "http_error":
            raise urllib.error.HTTPError(
                req.full_url,
                item["status_code"],
                item["reason"],
                hdrs=None,
                fp=BytesIO(item["body"].encode("utf-8")),
            )
        return _FakeAdvisorResponse(item["result"])


class _FakeAdvisorResponse:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = json.dumps(result, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> _FakeAdvisorResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._result


class FeishuGatewaySimulator:
    """Thin harness around FeishuWSGateway for deterministic business-flow tests."""

    def __init__(self, monkeypatch, gateway: Any, advisor_client: InMemoryAdvisorClient) -> None:
        self._gateway = gateway
        self._advisor_client = advisor_client
        self.sent_replies: list[dict[str, str]] = []
        monkeypatch.setattr("urllib.request.urlopen", advisor_client.urlopen)
        monkeypatch.setattr(
            gateway,
            "_send_reply",
            lambda chat_id, text: self.sent_replies.append(
                {"chat_id": str(chat_id), "text": str(text)}
            ),
        )

    @property
    def reply_texts(self) -> list[str]:
        return [item["text"] for item in self.sent_replies]

    def dispatch(
        self, *, chat_id: str, message_id: str, text: str, user_id: str
    ) -> None:
        self._gateway._process_and_reply(chat_id, message_id, text, user_id)


@dataclass
class MemoryManagerFixture:
    """Convenience wrapper for high-signal memory tests."""

    db_path: Path

    def __post_init__(self) -> None:
        self.manager = MemoryManager(db_path=str(self.db_path))

    def stage_and_promote(
        self,
        *,
        target: MemoryTier,
        category: str,
        key: str,
        value: dict[str, Any],
        confidence: float = 0.8,
        agent: str = "test-agent",
        session_id: str = "",
        account_id: str = "",
        thread_id: str = "",
        reason: str = "fixture promotion",
    ) -> str:
        return self.manager.stage_and_promote(
            MemoryRecord(
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                source=MemorySource(
                    type="system",
                    agent=agent,
                    session_id=session_id,
                    account_id=account_id,
                    thread_id=thread_id,
                ).to_dict(),
            ),
            target,
            reason=reason,
        )

    def episodic(self, **kwargs: Any):
        return self.manager.get_episodic(**kwargs)

    def semantic(self, **kwargs: Any):
        return self.manager.get_semantic(**kwargs)

    def close(self) -> None:
        self.manager.close()
