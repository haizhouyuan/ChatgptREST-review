"""OpenCLI subprocess executor.

Wraps opencli binary as subprocess for controlled execution.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from chatgptrest.executors.opencli_contracts import (
    OpenCLIExecutionRequest,
    OpenCLIExecutionResult,
    classify_exit_code,
)
from chatgptrest.executors.opencli_policy import OpenCLIExecutionPolicy

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "opencli"


class OpenCLIExecutor:
    """Subprocess-based opencli executor."""

    def __init__(
        self,
        policy: OpenCLIExecutionPolicy | None = None,
        artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
        max_retries: int = 1,
    ) -> None:
        self._policy = policy or OpenCLIExecutionPolicy()
        artifact_root = Path(artifact_dir)
        if not artifact_root.is_absolute():
            artifact_root = REPO_ROOT / artifact_root
        self._artifact_dir = artifact_root.resolve(strict=False)
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = max_retries

    def _find_opencli_binary(self) -> str | None:
        """Find opencli binary in PATH."""
        return shutil.which("opencli")

    def _capture_doctor(self) -> str:
        """Capture opencli doctor output."""
        binary = self._find_opencli_binary()
        if not binary:
            return "opencli binary not found"

        try:
            result = subprocess.run(
                [binary, "doctor", "--no-live"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.stdout or result.stderr or "doctor produced no output"
        except Exception as exc:
            return f"doctor failed: {exc}"

    def execute(self, request: OpenCLIExecutionRequest) -> OpenCLIExecutionResult:
        """Execute opencli command via subprocess with controlled retry.

        Returns:
            OpenCLIExecutionResult with ok=True on success, ok=False on failure
        """
        retry_count = 0
        last_result = None

        while retry_count <= self._max_retries:
            result = self._execute_once(request, attempt=retry_count + 1)
            last_result = result

            # Success - return immediately
            if result.ok:
                return result

            # Not retryable - return immediately
            if not result.retryable:
                return result

            # Retryable but no more retries left
            if retry_count >= self._max_retries:
                return result

            # Retry
            logger.info(
                "OpenCLI execution failed with retryable error %s, retrying (%d/%d)",
                result.error_type,
                retry_count + 1,
                self._max_retries,
            )
            retry_count += 1
            time.sleep(1)  # Brief delay before retry

        return last_result or OpenCLIExecutionResult(
            ok=False,
            executor_kind="opencli",
            command_id=request.command_id,
            exit_code=1,
            retryable=False,
            error_type="execution_error",
            error_message="No result after retries",
        )

    def _execute_once(self, request: OpenCLIExecutionRequest, attempt: int = 1) -> OpenCLIExecutionResult:
        """Execute opencli command once (single attempt).

        Returns:
            OpenCLIExecutionResult with ok=True on success, ok=False on failure
        """
        start_time = time.time()
        command_id = request.command_id

        # Validate request
        if request.executor_kind != "opencli":
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=2,
                retryable=False,
                error_type="usage_error",
                error_message=f"Invalid executor_kind: {request.executor_kind}",
            )

        # Check allowlist
        if not self._policy.is_command_allowed(command_id):
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=2,
                retryable=False,
                error_type="usage_error",
                error_message=f"Command not in allowlist: {command_id}",
            )

        # Validate args
        valid, error_msg = self._policy.validate_args(command_id, request.args)
        if not valid:
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=2,
                retryable=False,
                error_type="usage_error",
                error_message=error_msg,
            )

        # Find binary
        binary = self._find_opencli_binary()
        if not binary:
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=78,
                retryable=False,
                error_type="config_error",
                error_message="opencli binary not found in PATH",
            )

        # Get command policy
        policy = self._policy.get_command_policy(command_id)
        if policy is None:
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=2,
                retryable=False,
                error_type="usage_error",
                error_message=f"No policy found for command: {command_id}",
            )

        if str(request.capability_id or "").strip() != str(policy.capability_id or "").strip():
            return OpenCLIExecutionResult(
                ok=False,
                executor_kind="opencli",
                command_id=command_id,
                exit_code=2,
                retryable=False,
                error_type="usage_error",
                error_message=(
                    f"Capability mismatch for command {command_id}: "
                    f"expected {policy.capability_id}, got {request.capability_id}"
                ),
            )

        # Build command
        cmd = [binary, *policy.command]
        if str(policy.output_format or "").strip().lower() == "json":
            cmd.extend(["-f", "json"])
        for arg_name, arg_value in request.args.items():
            cmd.extend([f"--{arg_name}", str(arg_value)])

        # Create artifact directory for this execution
        exec_id = f"{command_id}_{int(time.time() * 1000)}_attempt{attempt}"
        exec_dir = self._artifact_dir / exec_id
        exec_dir.mkdir(parents=True, exist_ok=True)

        # Save request
        request_path = exec_dir / "request.json"
        request_path.write_text(json.dumps(request.to_dict(), indent=2), encoding="utf-8")

        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
            exit_code = int(result.returncode)
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            exit_code = 75
            stdout = ""
            stderr = "Command timed out"
        except Exception as exc:
            exit_code = 1
            stdout = ""
            stderr = str(exc)

        elapsed = time.time() - start_time

        # Save stdout/stderr
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")

        # Parse structured result
        structured_result: dict[str, Any] = {}
        if exit_code == 0 and stdout:
            try:
                structured_result = json.loads(stdout)
            except Exception as exc:
                logger.warning("Failed to parse opencli JSON output: %s", exc)
                exit_code = 1
                stderr = f"JSON parse failed: {exc}"

        # Classify exit code
        error_type, retryable_by_default = classify_exit_code(exit_code)
        retryable_codes = {int(code) for code in policy.retryable_exit_codes}
        retryable = retryable_by_default and (exit_code in retryable_codes if retryable_codes else True)
        ok = exit_code == 0

        # Capture doctor on failure
        doctor_output = ""
        if not ok and policy.capture_doctor_on_failure:
            doctor_output = self._capture_doctor()
            doctor_path = exec_dir / "doctor.txt"
            doctor_path.write_text(doctor_output, encoding="utf-8")

        # Build diagnostics
        diagnostics = {
            "command": cmd,
            "exit_code": exit_code,
            "error_type": error_type,
            "retryable": retryable,
            "elapsed_seconds": elapsed,
            "exec_dir": str(exec_dir),
            "doctor_captured": bool(doctor_output),
            "attempt": attempt,
        }

        # Save diagnostics
        diagnostics_path = exec_dir / "diagnostics.json"
        diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

        # Build result
        result_obj = OpenCLIExecutionResult(
            ok=ok,
            executor_kind="opencli",
            command_id=command_id,
            exit_code=exit_code,
            retryable=retryable,
            error_type=error_type if not ok else "",
            error_message=stderr if not ok else "",
            structured_result=structured_result,
            artifacts=[
                str(request_path),
                str(stdout_path),
                str(stderr_path),
                str(diagnostics_path),
            ],
            diagnostics=diagnostics,
            timing={"elapsed_seconds": elapsed},
        )

        if doctor_output:
            result_obj.artifacts.append(str(exec_dir / "doctor.txt"))

        # Save result
        result_path = exec_dir / "result.json"
        result_path.write_text(json.dumps(result_obj.to_dict(), indent=2), encoding="utf-8")
        result_obj.artifacts.append(str(result_path))

        # Generate answer.md
        answer_path = exec_dir / "answer.md"
        if ok:
            answer_content = f"# OpenCLI Execution Result\n\n**Command**: `{command_id}`\n**Status**: ✅ Success\n**Attempt**: {attempt}\n\n## Structured Result\n\n```json\n{json.dumps(structured_result, indent=2)}\n```\n"
        else:
            answer_content = f"# OpenCLI Execution Result\n\n**Command**: `{command_id}`\n**Status**: ❌ Failed\n**Error Type**: `{error_type}`\n**Retryable**: {retryable}\n**Attempt**: {attempt}\n\n## Error Message\n\n```\n{stderr}\n```\n"
            if doctor_output:
                answer_content += f"\n## Doctor Output\n\n```\n{doctor_output}\n```\n"

        answer_path.write_text(answer_content, encoding="utf-8")
        result_obj.artifacts.append(str(answer_path))

        return result_obj
