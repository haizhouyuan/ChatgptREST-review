from __future__ import annotations

import asyncio

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


_CONV_URL = "https://chatgpt.com/c/69896ee7-e764-83a3-81ea-7476193e4590"


class _BaseDummyCaller:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.ask_calls = 0
        self.wait_calls = 0
        self.self_checks = 0

    def _blocked_status(self) -> dict:
        return {"blocked": False}

    def _ask(self) -> dict:
        raise NotImplementedError

    def _wait(self) -> dict:
        raise NotImplementedError

    def _self_check(self) -> dict:
        raise NotImplementedError

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append(tool_name)
        if tool_name == "chatgpt_web_blocked_status":
            return self._blocked_status()
        if tool_name == "chatgpt_web_ask":
            self.ask_calls += 1
            return self._ask()
        if tool_name == "chatgpt_web_wait":
            self.wait_calls += 1
            return self._wait()
        if tool_name == "chatgpt_web_self_check":
            self.self_checks += 1
            return self._self_check()
        raise AssertionError(f"unexpected tool: {tool_name} args={tool_args}")


class _WaitRecoveryCaller(_BaseDummyCaller):
    def _ask(self) -> dict:
        return {"status": "in_progress", "answer": "", "conversation_url": _CONV_URL}

    def _wait(self) -> dict:
        if self.wait_calls == 1:
            raise RuntimeError("Target page, context or browser has been closed")
        return {"status": "completed", "answer": "done", "conversation_url": _CONV_URL}

    def _self_check(self) -> dict:
        return {"ok": True, "status": "completed", "conversation_url": _CONV_URL, "blocked_state": {"blocked_until": 0}}


class _WaitSelfCheckFailureCaller(_BaseDummyCaller):
    def _ask(self) -> dict:
        return {"status": "in_progress", "answer": "", "conversation_url": _CONV_URL}

    def _wait(self) -> dict:
        raise RuntimeError("Target page, context or browser has been closed")

    def _self_check(self) -> dict:
        return {
            "ok": False,
            "status": "error",
            "error_type": "RuntimeError",
            "error": "Target page, context or browser has been closed",
            "blocked_state": {"blocked_until": 0},
        }


class _WaitManualFollowupCaller(_BaseDummyCaller):
    def _ask(self) -> dict:
        return {"status": "in_progress", "answer": "", "conversation_url": _CONV_URL}

    def _wait(self) -> dict:
        raise RuntimeError("Target page, context or browser has been closed")

    def _self_check(self) -> dict:
        return {
            "ok": False,
            "status": "error",
            "error_type": "VerificationRequired",
            "error": "driver blocked: verification_pending",
            "blocked_state": {"reason": "verification_pending", "blocked_until": 0},
        }


class _SendRecoveryCaller(_BaseDummyCaller):
    def _ask(self) -> dict:
        if self.ask_calls == 1:
            return {
                "status": "error",
                "error_type": "TargetClosedError",
                "error": "Target page, context or browser has been closed",
            }
        return {"status": "in_progress", "answer": "", "conversation_url": _CONV_URL}

    def _wait(self) -> dict:
        return {"status": "completed", "answer": "done", "conversation_url": _CONV_URL}

    def _self_check(self) -> dict:
        return {"ok": True, "status": "completed", "conversation_url": _CONV_URL, "blocked_state": {"blocked_until": 0}}


def _run_with(dummy: _BaseDummyCaller):
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = dummy  # type: ignore[assignment]
    return asyncio.run(
        ex.run(
            job_id="job-chatgpt-transient-recovery",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "send_timeout_seconds": 30, "wait_timeout_seconds": 30, "max_wait_seconds": 60, "min_chars": 0},
        )
    )


def test_chatgpt_wait_transient_error_recovers_after_self_check() -> None:
    dummy = _WaitRecoveryCaller()
    res = _run_with(dummy)
    assert res.status == "completed"
    assert dummy.wait_calls == 2
    assert dummy.self_checks == 1


def test_chatgpt_wait_transient_error_requeues_when_self_check_fails() -> None:
    dummy = _WaitSelfCheckFailureCaller()
    res = _run_with(dummy)
    assert res.status == "in_progress"
    assert (res.meta or {}).get("error_type") == "InfraError"
    assert (res.meta or {}).get("wait_transient_failures") == 1
    recovery = (res.meta or {}).get("transient_runtime_recovery") or {}
    assert recovery.get("action") == "requeue_wait"
    assert ((recovery.get("self_check") or {}).get("ok")) is False


def test_chatgpt_wait_transient_error_escalates_manual_followup_from_self_check() -> None:
    dummy = _WaitManualFollowupCaller()
    res = _run_with(dummy)
    assert res.status == "needs_followup"
    assert (res.meta or {}).get("error_type") == "VerificationRequired"
    recovery = (res.meta or {}).get("transient_runtime_recovery") or {}
    assert recovery.get("action") == "manual_followup"


def test_chatgpt_send_transient_driver_error_retries_after_self_check() -> None:
    dummy = _SendRecoveryCaller()
    res = _run_with(dummy)
    assert res.status == "completed"
    assert dummy.ask_calls == 2
    assert dummy.self_checks == 1
