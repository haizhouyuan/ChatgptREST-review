from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "chatgpt_agent_shell_v0.py"
    spec = importlib.util.spec_from_file_location("chatgpt_agent_shell_v0", str(path))
    assert spec and spec.loader
    module_name = str(spec.name)
    cached = sys.modules.get(module_name)
    if cached is not None and hasattr(cached, "ChatGPTAgentV0"):
        return cached
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def test_needs_followup_auto_rounds_are_bounded_by_max_turns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    submit_calls: list[dict[str, Any]] = []

    def fake_post_submit(  # noqa: ANN001
        self,
        *,
        question: str,
        parent_job_id: str | None,
        turn_id: str,
        turn_no: int,
        input_override: dict[str, Any] | None = None,
        agent_mode: bool | None = None,
    ) -> dict[str, Any]:
        submit_calls.append({"question": question, "turn_no": turn_no, "parent_job_id": parent_job_id})
        return {"job_id": f"job-{len(submit_calls)}"}

    def fake_wait_job(self, job_id: str) -> dict[str, Any]:  # noqa: ANN001
        return {"status": "needs_followup"}

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_post_submit", fake_post_submit)
    monkeypatch.setattr(mod.ChatGPTAgentV0, "_wait_job", fake_wait_job)

    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-followup-max-turns",
        max_turns=2,
        max_retries=0,
        dry_run=False,
        auto_rollback=False,
    )

    out = agent.ask(question="请分析失败原因", followup_prompt="请继续")
    assert out["ok"] is False
    assert out["status"] == "needs_followup"
    assert out["error"] == "needs_followup_exhausted"
    assert len(submit_calls) == 2
    assert [c["turn_no"] for c in submit_calls] == [1, 2]
    assert agent.state.total_turns == 2


def test_needs_followup_then_completed_consumes_next_turn_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    submit_calls: list[dict[str, Any]] = []
    wait_sequence = [
        {"status": "needs_followup"},
        {"status": "completed", "conversation_url": "https://chatgpt.com/c/followup-ok"},
    ]

    def fake_post_submit(  # noqa: ANN001
        self,
        *,
        question: str,
        parent_job_id: str | None,
        turn_id: str,
        turn_no: int,
        input_override: dict[str, Any] | None = None,
        agent_mode: bool | None = None,
    ) -> dict[str, Any]:
        submit_calls.append({"question": question, "turn_no": turn_no, "parent_job_id": parent_job_id})
        return {"job_id": f"job-{len(submit_calls)}"}

    def fake_wait_job(self, job_id: str) -> dict[str, Any]:  # noqa: ANN001
        return wait_sequence.pop(0)

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_post_submit", fake_post_submit)
    monkeypatch.setattr(mod.ChatGPTAgentV0, "_wait_job", fake_wait_job)
    monkeypatch.setattr(mod.ChatGPTAgentV0, "_get_answer", lambda self, job_id: "done")

    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-followup-success",
        max_turns=3,
        max_retries=0,
        dry_run=False,
        auto_rollback=False,
    )

    out = agent.ask(question="请分析失败原因", followup_prompt="请继续")
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["turn"] == 2
    assert out["round"] == 2
    assert out["conversation_url"] == "https://chatgpt.com/c/followup-ok"
    assert [c["turn_no"] for c in submit_calls] == [1, 2]
    assert agent.state.total_turns == 2

