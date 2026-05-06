from __future__ import annotations

import asyncio

from chatgptrest.executors.coding_plan import CodingPlanExecutor
from chatgptrest.kernel.llm_connector import LLMResponse


def test_coding_plan_executor_defaults_to_planning(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_ask(prompt: str, *, system_msg: str = "", provider: str = "", preset: str = "", timeout=None):
        captured["prompt"] = prompt
        captured["system_msg"] = system_msg
        captured["provider"] = provider
        captured["preset"] = preset
        captured["timeout"] = timeout
        return LLMResponse(text="ok", provider="coding_plan/MiniMax-M2.5", preset=preset or "planning")

    executor = CodingPlanExecutor()
    monkeypatch.setattr(executor, "_connector", type("Stub", (), {"ask": staticmethod(_fake_ask)})())

    result = asyncio.run(
        executor.run(
            job_id="job-1",
            kind="coding_plan.ask",
            input={"question": "summarize the thesis"},
            params={},
        )
    )

    assert result.status == "completed"
    assert captured["provider"] == "coding_plan"
    assert captured["preset"] == "planning"
    assert result.meta["provider"] == "coding_plan/MiniMax-M2.5"


def test_coding_plan_executor_surfaces_error_status(monkeypatch) -> None:
    def _fake_ask(prompt: str, *, system_msg: str = "", provider: str = "", preset: str = "", timeout=None):
        return LLMResponse(status="cooldown", error="rate limit", provider=provider, preset=preset)

    executor = CodingPlanExecutor()
    monkeypatch.setattr(executor, "_connector", type("Stub", (), {"ask": staticmethod(_fake_ask)})())

    result = asyncio.run(
        executor.run(
            job_id="job-2",
            kind="coding_plan.ask",
            input={"question": "ping"},
            params={"preset": "review"},
        )
    )

    assert result.status == "error"
    assert result.meta["status"] == "cooldown"
    assert result.meta["preset"] == "review"
