"""Tests for OpenCLI executor subprocess wrapper."""

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from chatgptrest.executors.opencli_contracts import (
    OpenCLIExecutionRequest,
    OpenCLIExecutionResult,
    classify_exit_code,
)
from chatgptrest.executors.opencli_executor import OpenCLIExecutor
from chatgptrest.executors.opencli_policy import CommandPolicy, OpenCLIExecutionPolicy


@pytest.fixture
def mock_policy():
    """Create mock policy with test command."""
    policy = MagicMock(spec=OpenCLIExecutionPolicy)
    policy.is_command_allowed.return_value = True
    policy.validate_args.return_value = (True, "")
    policy.get_command_policy.return_value = CommandPolicy(
        capability_id="test_capability",
        command_id="test.command",
        command=["test", "command"],
        output_format="json",
        allowed_args={"limit": {"type": "int", "min": 1, "max": 10}},
        retryable_exit_codes=[69, 75],
        capture_doctor_on_failure=True,
    )
    return policy


@pytest.fixture
def executor(tmp_path, mock_policy):
    """Create executor with temp artifact dir."""
    return OpenCLIExecutor(policy=mock_policy, artifact_dir=tmp_path / "artifacts")


def test_classify_exit_code():
    """Test exit code classification."""
    assert classify_exit_code(0) == ("success", False)
    assert classify_exit_code(2) == ("usage_error", False)
    assert classify_exit_code(66) == ("empty_result", False)
    assert classify_exit_code(69) == ("infra_unavailable", True)
    assert classify_exit_code(75) == ("temporary_failure", True)
    assert classify_exit_code(77) == ("auth_required", False)
    assert classify_exit_code(78) == ("config_error", False)
    assert classify_exit_code(1) == ("execution_error", False)
    assert classify_exit_code(99) == ("execution_error", False)


def test_execution_request_serialization():
    """Test request serialization."""
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="test",
        command_id="test.cmd",
        args={"limit": 5},
        timeout_seconds=30,
    )
    data = request.to_dict()
    assert data["executor_kind"] == "opencli"
    assert data["command_id"] == "test.cmd"
    assert data["args"]["limit"] == 5

    restored = OpenCLIExecutionRequest.from_dict(data)
    assert restored.executor_kind == "opencli"
    assert restored.command_id == "test.cmd"
    assert restored.args["limit"] == 5


def test_execution_result_serialization():
    """Test result serialization."""
    result = OpenCLIExecutionResult(
        ok=True,
        executor_kind="opencli",
        command_id="test.cmd",
        exit_code=0,
        retryable=False,
        error_type="",
        error_message="",
        structured_result={"data": [1, 2, 3]},
        artifacts=["/tmp/test.json"],
    )
    data = result.to_dict()
    assert data["ok"] is True
    assert data["exit_code"] == 0
    assert data["structured_result"]["data"] == [1, 2, 3]

    restored = OpenCLIExecutionResult.from_dict(data)
    assert restored.ok is True
    assert restored.exit_code == 0
    assert restored.structured_result["data"] == [1, 2, 3]


def test_invalid_executor_kind(executor):
    """Test rejection of invalid executor_kind."""
    request = OpenCLIExecutionRequest(
        executor_kind="invalid",
        capability_id="test",
        command_id="test.cmd",
        args={},
    )
    result = executor.execute(request)
    assert not result.ok
    assert result.error_type == "usage_error"
    assert "Invalid executor_kind" in result.error_message


def test_command_not_in_allowlist(executor, mock_policy):
    """Test rejection of non-allowlisted command."""
    mock_policy.is_command_allowed.return_value = False
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="test",
        command_id="forbidden.cmd",
        args={},
    )
    result = executor.execute(request)
    assert not result.ok
    assert result.error_type == "usage_error"
    assert "not in allowlist" in result.error_message


def test_invalid_args(executor, mock_policy):
    """Test rejection of invalid args."""
    mock_policy.validate_args.return_value = (False, "Invalid argument: limit")
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="test",
        command_id="test.cmd",
        args={"limit": 100},
    )
    result = executor.execute(request)
    assert not result.ok
    assert result.error_type == "usage_error"
    assert "Invalid argument" in result.error_message


def test_binary_not_found(executor, mock_policy):
    """Test handling of missing opencli binary."""
    with patch("shutil.which", return_value=None):
        request = OpenCLIExecutionRequest(
            executor_kind="opencli",
            capability_id="test",
            command_id="test.cmd",
            args={},
        )
        result = executor.execute(request)
        assert not result.ok
        assert result.error_type == "config_error"
        assert "binary not found" in result.error_message


def test_successful_execution(executor, mock_policy, tmp_path):
    """Test successful command execution."""
    mock_result = subprocess.CompletedProcess(
        args=["opencli", "test", "command", "-f", "json"],
        returncode=0,
        stdout='{"status": "ok", "data": [1, 2, 3]}',
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        with patch("subprocess.run", return_value=mock_result):
            request = OpenCLIExecutionRequest(
                executor_kind="opencli",
                capability_id="test_capability",
                command_id="test.command",
                args={"limit": 5},
            )
            result = executor.execute(request)

    assert result.ok
    assert result.exit_code == 0
    assert result.error_type == ""
    assert result.structured_result["status"] == "ok"
    assert result.structured_result["data"] == [1, 2, 3]
    assert len(result.artifacts) >= 5  # request, stdout, stderr, diagnostics, result, answer


def test_command_timeout(executor, mock_policy):
    """Test timeout handling."""
    from subprocess import TimeoutExpired

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        with patch("subprocess.run", side_effect=TimeoutExpired("opencli", 30)):
            request = OpenCLIExecutionRequest(
                executor_kind="opencli",
                capability_id="test_capability",
                command_id="test.command",
                args={},
                timeout_seconds=30,
            )
            result = executor.execute(request)

    assert not result.ok
    assert result.exit_code == 75
    assert result.error_type == "temporary_failure"
    assert result.retryable


def test_json_parse_failure(executor, mock_policy):
    """Test handling of invalid JSON output."""
    mock_result = subprocess.CompletedProcess(
        args=["opencli", "test", "command", "-f", "json"],
        returncode=0,
        stdout="not valid json",
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        with patch("subprocess.run", return_value=mock_result):
            request = OpenCLIExecutionRequest(
                executor_kind="opencli",
                capability_id="test_capability",
                command_id="test.command",
                args={},
            )
            result = executor.execute(request)

    assert not result.ok
    assert result.exit_code == 1
    assert "JSON parse failed" in result.error_message


def test_retryable_exit_codes(executor, mock_policy):
    """Test retryable exit code classification."""
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="test_capability",
        command_id="test.command",
        args={},
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        # Test exit code 69 (infra_unavailable)
        mock_result = subprocess.CompletedProcess(
            args=["opencli", "test", "command", "-f", "json"],
            returncode=69,
            stdout="",
            stderr="Service unavailable",
        )
        with patch("subprocess.run", return_value=mock_result):
            result = executor.execute(request)
        assert not result.ok
        assert result.error_type == "infra_unavailable"
        assert result.retryable

        # Test exit code 75 (temporary_failure)
        mock_result = subprocess.CompletedProcess(
            args=["opencli", "test", "command", "-f", "json"],
            returncode=75,
            stdout="",
            stderr="Temporary failure",
        )
        with patch("subprocess.run", return_value=mock_result):
            result = executor.execute(request)
        assert not result.ok
        assert result.error_type == "temporary_failure"
        assert result.retryable


def test_artifact_generation(executor, mock_policy, tmp_path):
    """Test that all required artifacts are generated."""
    mock_result = subprocess.CompletedProcess(
        args=["opencli", "test", "command", "-f", "json"],
        returncode=0,
        stdout='{"status": "ok"}',
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        with patch("subprocess.run", return_value=mock_result):
            request = OpenCLIExecutionRequest(
                executor_kind="opencli",
                capability_id="test_capability",
                command_id="test.command",
                args={},
            )
            result = executor.execute(request)

    # Check all required artifacts exist
    for artifact_path in result.artifacts:
        assert Path(artifact_path).exists(), f"Artifact missing: {artifact_path}"

    # Check specific artifacts
    artifact_names = [Path(p).name for p in result.artifacts]
    assert "request.json" in artifact_names
    assert "stdout.txt" in artifact_names
    assert "stderr.txt" in artifact_names
    assert "diagnostics.json" in artifact_names
    assert "result.json" in artifact_names
    assert "answer.md" in artifact_names


def test_doctor_capture_on_failure(executor, mock_policy):
    """Test doctor capture on failure."""
    mock_result = subprocess.CompletedProcess(
        args=["opencli", "test", "command", "-f", "json"],
        returncode=1,
        stdout="",
        stderr="Command failed",
    )

    mock_doctor = subprocess.CompletedProcess(
        args=["opencli", "doctor", "--no-live"],
        returncode=0,
        stdout="Doctor output: all systems nominal",
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        with patch("subprocess.run") as mock_run:
            # First call is the actual command, second is doctor
            mock_run.side_effect = [mock_result, mock_doctor]
            request = OpenCLIExecutionRequest(
                executor_kind="opencli",
                capability_id="test_capability",
                command_id="test.command",
                args={},
            )
            result = executor.execute(request)

    assert not result.ok
    assert result.diagnostics["doctor_captured"]
    artifact_names = [Path(p).name for p in result.artifacts]
    assert "doctor.txt" in artifact_names


def test_capability_mismatch_rejected(executor, mock_policy):
    """Test that capability_id must match the allowlisted command."""
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="wrong_capability",
        command_id="test.command",
        args={},
    )

    with patch("shutil.which", return_value="/usr/bin/opencli"):
        result = executor.execute(request)

    assert not result.ok
    assert result.error_type == "usage_error"
    assert "Capability mismatch" in result.error_message
