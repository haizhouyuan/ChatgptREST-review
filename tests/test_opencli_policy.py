"""Tests for OpenCLI execution policy."""

import json
from pathlib import Path

import pytest

from chatgptrest.executors.opencli_policy import CommandPolicy, OpenCLIExecutionPolicy


@pytest.fixture
def policy_file(tmp_path):
    """Create temporary policy file."""
    policy_data = {
        "authority": {
            "version": "test.v1",
            "owner": "test",
        },
        "commands": [
            {
                "capability_id": "test_capability",
                "command_id": "test.command",
                "command": ["test", "command"],
                "output_format": "json",
                "risk_level": "low",
                "auth_mode": "public",
                "browser_mode": "none",
                "allowed_args": {
                    "limit": {"type": "int", "min": 1, "max": 10},
                    "name": {"type": "string", "max_length": 50},
                },
                "retryable_exit_codes": [69, 75],
                "capture_doctor_on_failure": True,
            },
            {
                "capability_id": "another_capability",
                "command_id": "another.command",
                "command": ["another", "command"],
                "output_format": "json",
                "allowed_args": {},
                "retryable_exit_codes": [],
                "capture_doctor_on_failure": False,
            },
        ],
    }
    policy_path = tmp_path / "test_policy.json"
    policy_path.write_text(json.dumps(policy_data), encoding="utf-8")
    return policy_path


def test_load_policy(policy_file):
    """Test loading policy from file."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)
    assert len(policy.list_commands()) == 2
    assert "test.command" in policy.list_commands()
    assert "another.command" in policy.list_commands()


def test_get_command_policy(policy_file):
    """Test retrieving command policy."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)
    cmd_policy = policy.get_command_policy("test.command")
    assert cmd_policy is not None
    assert cmd_policy.capability_id == "test_capability"
    assert cmd_policy.command == ["test", "command"]
    assert cmd_policy.risk_level == "low"
    assert cmd_policy.retryable_exit_codes == [69, 75]


def test_is_command_allowed(policy_file):
    """Test command allowlist check."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)
    assert policy.is_command_allowed("test.command")
    assert policy.is_command_allowed("another.command")
    assert not policy.is_command_allowed("forbidden.command")


def test_validate_args_success(policy_file):
    """Test successful argument validation."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)

    # Valid int arg
    valid, msg = policy.validate_args("test.command", {"limit": 5})
    assert valid
    assert msg == ""

    # Valid string arg
    valid, msg = policy.validate_args("test.command", {"name": "test"})
    assert valid
    assert msg == ""

    # Multiple valid args
    valid, msg = policy.validate_args("test.command", {"limit": 5, "name": "test"})
    assert valid
    assert msg == ""


def test_validate_args_not_allowed(policy_file):
    """Test rejection of non-allowed arguments."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)
    valid, msg = policy.validate_args("test.command", {"forbidden": "value"})
    assert not valid
    assert "not allowed" in msg


def test_validate_args_int_type(policy_file):
    """Test int type validation."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)

    # Wrong type
    valid, msg = policy.validate_args("test.command", {"limit": "not_an_int"})
    assert not valid
    assert "must be int" in msg

    # Below min
    valid, msg = policy.validate_args("test.command", {"limit": 0})
    assert not valid
    assert ">=" in msg

    # Above max
    valid, msg = policy.validate_args("test.command", {"limit": 100})
    assert not valid
    assert "<=" in msg


def test_validate_args_string_type(policy_file):
    """Test string type validation."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)

    # Wrong type
    valid, msg = policy.validate_args("test.command", {"name": 123})
    assert not valid
    assert "must be string" in msg

    # Exceeds max length
    valid, msg = policy.validate_args("test.command", {"name": "x" * 100})
    assert not valid
    assert "max length" in msg


def test_validate_args_command_not_found(policy_file):
    """Test validation for non-existent command."""
    policy = OpenCLIExecutionPolicy(policy_path=policy_file)
    valid, msg = policy.validate_args("nonexistent.command", {})
    assert not valid
    assert "not in allowlist" in msg


def test_load_missing_policy_file(tmp_path):
    """Test handling of missing policy file."""
    policy = OpenCLIExecutionPolicy(policy_path=tmp_path / "nonexistent.json")
    assert len(policy.list_commands()) == 0


def test_load_invalid_json(tmp_path):
    """Test handling of invalid JSON."""
    policy_path = tmp_path / "invalid.json"
    policy_path.write_text("not valid json", encoding="utf-8")
    policy = OpenCLIExecutionPolicy(policy_path=policy_path)
    assert len(policy.list_commands()) == 0


def test_load_invalid_format(tmp_path):
    """Test handling of invalid policy format."""
    policy_path = tmp_path / "invalid_format.json"
    policy_path.write_text('["not", "a", "dict"]', encoding="utf-8")
    policy = OpenCLIExecutionPolicy(policy_path=policy_path)
    assert len(policy.list_commands()) == 0


def test_command_policy_defaults():
    """Test CommandPolicy default values."""
    policy = CommandPolicy(
        capability_id="test",
        command_id="test.cmd",
        command=["test"],
    )
    assert policy.output_format == "json"
    assert policy.risk_level == "low"
    assert policy.auth_mode == "public"
    assert policy.browser_mode == "none"
    assert policy.allowed_args == {}
    assert policy.retryable_exit_codes == []
    assert policy.capture_doctor_on_failure is True
