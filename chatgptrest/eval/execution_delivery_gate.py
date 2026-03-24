"""Scoped execution-delivery gate for the public /v3 agent facade."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3


@dataclass
class ExecutionDeliveryCheck:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class ExecutionDeliveryGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ExecutionDeliveryCheck]
    scope_boundary: str = (
        "scoped public-facade execution delivery proof only; "
        "not external provider replay, not OpenClaw dynamic replay, not heavy execution approval"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": self.scope_boundary,
        }


def run_execution_delivery_gate() -> ExecutionDeliveryGateReport:
    checks = [
        _controller_delivery_check(),
        _direct_job_delivery_check(),
        _consult_delivery_check(),
        _deferred_stream_check(),
        _persisted_session_check(),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ExecutionDeliveryGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_execution_delivery_gate_markdown(report: ExecutionDeliveryGateReport) -> str:
    lines = [
        "# Execution Delivery Gate Report",
        "",
        f"- overall_passed: {str(report.overall_passed).lower()}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        f"- scope_boundary: {report.scope_boundary}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{k}={v}" for k, v in check.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_execution_delivery_gate_report(
    report: ExecutionDeliveryGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_execution_delivery_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _controller_delivery_check() -> ExecutionDeliveryCheck:
    class _FakeController:
        def __init__(self, _state: object) -> None:
            pass

        def ask(self, **kwargs):
            return {
                "run_id": "run-123",
                "job_id": "job-123",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "WAITING_EXTERNAL",
                "answer": "",
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "final_job_id": "job-123",
                    "delivery": {
                        "status": "completed",
                        "answer": "final answer",
                        "conversation_url": "https://chatgpt.com/c/run-123",
                    },
                    "next_action": {"type": "followup"},
                },
                "artifacts": [{"kind": "conversation_url", "uri": "https://chatgpt.com/c/run-123"}],
            }

    with _agent_client(controller_cls=_FakeController) as client:
        response = client.post(
            "/v3/agent/turn",
            json={"message": "review this repo", "goal_hint": "code_review", "timeout_seconds": 30},
            headers=_auth_headers(),
        )
        body = _decode_json(response)
        status_response = client.get(f"/v3/agent/session/{body.get('session_id')}", headers=_auth_headers())
        status_body = _decode_json(status_response)

    details = {
        "http_status": int(response.status_code),
        "response_status": str(body.get("status") or ""),
        "response_route": str(_mapping(body.get("provenance")).get("route") or ""),
        "provenance_job_id": str(_mapping(body.get("provenance")).get("job_id") or ""),
        "session_status": str(status_body.get("status") or ""),
        "session_job_id": str(status_body.get("job_id") or ""),
        "last_answer": str(status_body.get("last_answer") or ""),
    }
    return _build_check(
        name="controller_wait_to_terminal_delivery",
        details=details,
        expectations={
            "http_status": 200,
            "response_status": "completed",
            "response_route": "quick_ask",
            "provenance_job_id": "job-123",
            "session_status": "completed",
            "session_job_id": "job-123",
            "last_answer": "final answer",
        },
    )


def _direct_job_delivery_check() -> ExecutionDeliveryCheck:
    captured: dict[str, Any] = {}

    def _submit_direct_job(**kwargs):
        captured.update(kwargs)
        return "job-img-1"

    def _wait_for_job_completion(**kwargs):
        return {
            "job_id": str(kwargs.get("job_id") or "job-img-1"),
            "job_status": "completed",
            "agent_status": "completed",
            "answer": "# Generated images\n\n![image 1](images/cat.png)",
            "conversation_url": "https://gemini.google.com/app/abc",
        }

    class _ShouldNotBeUsed:
        def __init__(self, _state: object) -> None:
            raise AssertionError("ControllerEngine should not be used for direct image delivery")

    with _agent_client(
        controller_cls=_ShouldNotBeUsed,
        submit_direct_job=_submit_direct_job,
        wait_for_job_completion=_wait_for_job_completion,
    ) as client:
        response = client.post(
            "/v3/agent/turn",
            json={
                "message": "draw a cat",
                "goal_hint": "image",
                "attachments": ["/tmp/ref.png"],
                "timeout_seconds": 30,
            },
            headers=_auth_headers(),
        )
        body = _decode_json(response)

    details = {
        "http_status": int(response.status_code),
        "response_status": str(body.get("status") or ""),
        "provenance_job_id": str(_mapping(body.get("provenance")).get("job_id") or ""),
        "direct_kind": str(captured.get("kind") or ""),
        "file_paths": list(_mapping(captured.get("input_obj")).get("file_paths") or []),
    }
    return _build_check(
        name="direct_image_job_delivery",
        details=details,
        expectations={
            "http_status": 200,
            "response_status": "completed",
            "provenance_job_id": "job-img-1",
            "direct_kind": "gemini_web.generate_image",
            "file_paths": ["/tmp/ref.png"],
        },
    )


def _consult_delivery_check() -> ExecutionDeliveryCheck:
    def _submit_consultation(**kwargs):
        return {
            "consultation_id": "cons-1",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
        }

    def _consultation_snapshot(**kwargs):
        return {
            "consultation_id": str(kwargs.get("consultation_id") or "cons-1"),
            "status": "completed",
            "agent_status": "completed",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
            "answer": "## chatgpt_pro\n\nAnswer A\n\n---\n\n## gemini_deepthink\n\nAnswer B",
        }

    def _wait_for_consultation_completion(**kwargs):
        return _consultation_snapshot(**kwargs)

    with _agent_client(
        submit_consultation=_submit_consultation,
        wait_for_consultation_completion=_wait_for_consultation_completion,
        consultation_snapshot=_consultation_snapshot,
    ) as client:
        response = client.post(
            "/v3/agent/turn",
            json={"message": "double review this plan", "goal_hint": "dual_review", "timeout_seconds": 30},
            headers=_auth_headers(),
        )
        body = _decode_json(response)
        status_response = client.get(f"/v3/agent/session/{body.get('session_id')}", headers=_auth_headers())
        status_body = _decode_json(status_response)

    details = {
        "http_status": int(response.status_code),
        "response_status": str(body.get("status") or ""),
        "consultation_id": str(_mapping(body.get("provenance")).get("consultation_id") or ""),
        "session_status": str(status_body.get("status") or ""),
    }
    return _build_check(
        name="consult_delivery_completion",
        details=details,
        expectations={
            "http_status": 200,
            "response_status": "completed",
            "consultation_id": "cons-1",
            "session_status": "completed",
        },
    )


def _deferred_stream_check() -> ExecutionDeliveryCheck:
    class _FakeController:
        def __init__(self, _state: object) -> None:
            pass

        def ask(self, **kwargs):
            return {
                "run_id": "run-stream-1",
                "job_id": "job-stream-1",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": "answer 1",
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "answer 1"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    with _agent_client(controller_cls=_FakeController) as client:
        response = client.post(
            "/v3/agent/turn",
            json={"message": "review this repo for regression risk", "delivery_mode": "deferred"},
            headers=_auth_headers(),
        )
        body = _decode_json(response)
        with client.stream("GET", body.get("stream_url") or "", headers=_auth_headers()) as stream_response:
            events = _collect_sse(stream_response)

    done_event = next((payload for event_name, payload in events if event_name == "done"), {})
    session_payload = _mapping(_mapping(done_event).get("session"))
    details = {
        "http_status": int(response.status_code),
        "accepted": bool(body.get("accepted") or False),
        "delivery_mode": str(_mapping(body.get("delivery")).get("mode") or ""),
        "done_status": str(session_payload.get("status") or ""),
        "done_has_stream_url": bool(session_payload.get("stream_url")),
        "num_events": len(events),
    }
    return _build_check(
        name="deferred_stream_terminal_done",
        details=details,
        expectations={
            "http_status": 202,
            "accepted": True,
            "delivery_mode": "deferred",
            "done_status": "completed",
            "done_has_stream_url": True,
        },
    )


def _persisted_session_check() -> ExecutionDeliveryCheck:
    class _FakeController:
        def __init__(self, _state: object) -> None:
            pass

        def ask(self, **kwargs):
            return {
                "run_id": "run-persist-1",
                "job_id": "job-persist-1",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": "persisted answer",
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "persisted answer"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    with tempfile.TemporaryDirectory(prefix="phase18-agent-sessions-") as session_dir:
        with _agent_client(controller_cls=_FakeController, session_dir=session_dir) as client_a:
            first = client_a.post(
                "/v3/agent/turn",
                json={"message": "persist this session", "goal_hint": "code_review"},
                headers=_auth_headers(),
            )
            first_body = _decode_json(first)
        with _agent_client(controller_cls=_FakeController, session_dir=session_dir) as client_b:
            status_response = client_b.get(
                f"/v3/agent/session/{first_body.get('session_id')}",
                headers=_auth_headers(),
            )
            status_body = _decode_json(status_response)

    details = {
        "create_http_status": int(first.status_code),
        "rehydrate_http_status": int(status_response.status_code),
        "response_status": str(first_body.get("status") or ""),
        "rehydrated_status": str(status_body.get("status") or ""),
        "same_session_id": str(first_body.get("session_id") or "") == str(status_body.get("session_id") or ""),
    }
    return _build_check(
        name="persisted_session_rehydration",
        details=details,
        expectations={
            "create_http_status": 200,
            "rehydrate_http_status": 200,
            "response_status": "completed",
            "rehydrated_status": "completed",
            "same_session_id": True,
        },
    )


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> ExecutionDeliveryCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return ExecutionDeliveryCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _auth_headers() -> dict[str, str]:
    return {"X-Api-Key": "test-openmind-key"}


def _decode_json(response) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _collect_sse(response) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    current_event: str | None = None
    current_data: str | None = None
    for raw_line in response.iter_lines():
        line = raw_line.strip()
        if not line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()
    if current_event is not None and current_data is not None:
        events.append((current_event, json.loads(current_data)))
    return events


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


class _agent_client:
    def __init__(
        self,
        *,
        controller_cls: type[object] | None = None,
        submit_direct_job=None,
        wait_for_job_completion=None,
        submit_consultation=None,
        wait_for_consultation_completion=None,
        consultation_snapshot=None,
        session_dir: str | None = None,
    ) -> None:
        self._controller_cls = controller_cls
        self._submit_direct_job = submit_direct_job
        self._wait_for_job_completion = wait_for_job_completion
        self._submit_consultation = submit_consultation
        self._wait_for_consultation_completion = wait_for_consultation_completion
        self._consultation_snapshot = consultation_snapshot
        self._session_dir = session_dir
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._stack: ExitStack | None = None
        self._client: TestClient | None = None

    def __enter__(self) -> TestClient:
        self._stack = ExitStack()
        session_dir = self._session_dir
        if session_dir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="phase18-agent-sessions-")
            session_dir = self._tmpdir.name
        self._stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "OPENMIND_API_KEY": "test-openmind-key",
                    "OPENMIND_AUTH_MODE": "strict",
                    "CHATGPTREST_AGENT_SESSION_DIR": session_dir,
                },
                clear=False,
            )
        )
        self._stack.enter_context(patch.object(routes_agent_v3, "_advisor_runtime", lambda: {}))
        self._stack.enter_context(patch.object(routes_agent_v3, "_emit_runtime_event", lambda *args, **kwargs: None))
        self._stack.enter_context(patch.object(routes_agent_v3, "_cancel_job", lambda **kwargs: None))
        if self._controller_cls is not None:
            self._stack.enter_context(patch.object(routes_agent_v3, "ControllerEngine", self._controller_cls))
        if self._submit_direct_job is not None:
            self._stack.enter_context(patch.object(routes_agent_v3, "_submit_direct_job", self._submit_direct_job))
        if self._wait_for_job_completion is not None:
            self._stack.enter_context(
                patch.object(routes_agent_v3, "_wait_for_job_completion", self._wait_for_job_completion)
            )
        if self._submit_consultation is not None:
            self._stack.enter_context(
                patch.object(routes_agent_v3, "_submit_consultation", self._submit_consultation)
            )
        if self._wait_for_consultation_completion is not None:
            self._stack.enter_context(
                patch.object(
                    routes_agent_v3,
                    "_wait_for_consultation_completion",
                    self._wait_for_consultation_completion,
                )
            )
        if self._consultation_snapshot is not None:
            self._stack.enter_context(
                patch.object(
                    routes_agent_v3,
                    "_consultation_snapshot",
                    self._consultation_snapshot,
                )
            )

        app = FastAPI()
        app.include_router(routes_agent_v3.make_v3_agent_router())
        self._client = TestClient(app, raise_server_exceptions=False)
        return self._client

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            self._client.close()
        if self._stack is not None:
            self._stack.close()
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
