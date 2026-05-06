from __future__ import annotations

import asyncio
from typing import Any

import pytest

from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def test_gemini_generate_image_calls_driver_tool() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {
                "status": "completed",
                "images": [
                    {"path": "/tmp/fake.png", "mime_type": "image/png", "bytes": 1, "width": 1, "height": 1},
                ],
                "conversation_url": "https://gemini.google.com/app/abc123def456",
            }

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.generate_image",
            input={"prompt": "a cat", "conversation_url": "https://gemini.google.com/app/abc123def456"},
            params={"timeout_seconds": 60},
        )
    )
    assert res.status == "completed"
    assert res.answer_format == "markdown"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_generate_image"
    assert calls[0]["tool_args"]["prompt"] == "a cat"
    assert calls[0]["tool_args"]["conversation_url"] == "https://gemini.google.com/app/abc123def456"
    assert calls[0]["tool_args"]["idempotency_key"] == "chatgptrest:job:gemini_web_generate_image"


def test_gemini_generate_image_in_progress_is_cooldown() -> None:
    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "gemini_web_generate_image"
            assert tool_args["prompt"] == "a cat"
            return {
                "status": "in_progress",
                "images": [],
                "conversation_url": "https://gemini.google.com/app/abc123def456",
                "error_type": "TimeoutError",
                "error": "still running",
            }

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.generate_image",
            input={"prompt": "a cat"},
            params={"timeout_seconds": 60},
        )
    )
    assert res.status == "cooldown"
    assert isinstance(res.meta, dict)
    assert res.meta.get("retry_after_seconds") == 30
    assert res.meta.get("conversation_url") == "https://gemini.google.com/app/abc123def456"


def test_gemini_generate_image_uploads_file_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded = [
        {
            "src_path": "/tmp/ref.png",
            "drive_name": "job_01_ref.png",
            "drive_id": "abc123",
            "drive_url": "https://drive.google.com/open?id=abc123",
            "upload_completed": True,
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        assert file_paths == ["/tmp/ref.png"]
        return list(uploaded)

    monkeypatch.setattr("chatgptrest.executors.gemini_web_mcp._upload_files_to_gdrive", _fake_upload)

    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "images": [], "conversation_url": "https://gemini.google.com/app/abc123def456"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.generate_image",
            input={"prompt": "a cat", "file_paths": ["/tmp/ref.png"]},
            params={"timeout_seconds": 60},
        )
    )
    assert res.status == "completed"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_generate_image"
    assert calls[0]["tool_args"]["drive_files"] == ["https://drive.google.com/open?id=abc123"]
