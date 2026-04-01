"""OpenCLI execution contracts and data structures.

Defines request/response contracts for opencli subprocess execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class OpenCLIExecutionRequest:
    """Request object for opencli execution.

    This is explicitly passed via task_intake.context.execution_request
    and triggers the opencli narrow lane in routes_agent_v3.py.
    """

    executor_kind: str  # Must be "opencli"
    capability_id: str  # e.g., "public_web_read"
    command_id: str  # e.g., "hackernews.top"
    args: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenCLIExecutionRequest:
        return cls(
            executor_kind=str(data.get("executor_kind", "")),
            capability_id=str(data.get("capability_id", "")),
            command_id=str(data.get("command_id", "")),
            args=dict(data.get("args") or {}),
            timeout_seconds=int(data.get("timeout_seconds", 30)),
        )


@dataclass
class OpenCLIExecutionResult:
    """Result object from opencli execution.

    Unified result structure for both success and failure cases.
    """

    ok: bool
    executor_kind: str  # Always "opencli"
    command_id: str
    exit_code: int
    retryable: bool
    error_type: str  # Empty on success
    error_message: str  # Empty on success
    structured_result: Any = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)  # File paths
    diagnostics: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenCLIExecutionResult:
        return cls(
            ok=bool(data.get("ok", False)),
            executor_kind=str(data.get("executor_kind", "opencli")),
            command_id=str(data.get("command_id", "")),
            exit_code=int(data.get("exit_code", 1)),
            retryable=bool(data.get("retryable", False)),
            error_type=str(data.get("error_type", "")),
            error_message=str(data.get("error_message", "")),
            structured_result=data.get("structured_result", {}),
            artifacts=list(data.get("artifacts") or []),
            diagnostics=dict(data.get("diagnostics") or {}),
            timing=dict(data.get("timing") or {}),
        )


# Exit code to error type mapping
EXIT_CODE_MAPPING: dict[int, tuple[str, bool]] = {
    0: ("success", False),
    2: ("usage_error", False),
    66: ("empty_result", False),
    69: ("infra_unavailable", True),  # Retryable
    75: ("temporary_failure", True),  # Retryable
    77: ("auth_required", False),
    78: ("config_error", False),
    1: ("execution_error", False),
}


def classify_exit_code(exit_code: int) -> tuple[str, bool]:
    """Classify exit code into error type and retryable flag.

    Returns:
        (error_type, retryable)
    """
    return EXIT_CODE_MAPPING.get(exit_code, ("execution_error", False))
