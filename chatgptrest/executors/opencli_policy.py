"""OpenCLI execution policy and allowlist management.

Loads and validates opencli command policies from catalog file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "ops" / "policies" / "opencli_execution_catalog_v1.json"


@dataclass
class CommandPolicy:
    """Policy for a single opencli command."""

    capability_id: str
    command_id: str
    command: list[str]
    output_format: str = "json"
    risk_level: str = "low"
    auth_mode: str = "public"
    browser_mode: str = "none"
    allowed_args: dict[str, Any] = field(default_factory=dict)
    retryable_exit_codes: list[int] = field(default_factory=list)
    capture_doctor_on_failure: bool = True


class OpenCLIExecutionPolicy:
    """Manages opencli execution policies and allowlist."""

    def __init__(self, policy_path: str | Path = "") -> None:
        raw_policy_path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
        if not raw_policy_path.is_absolute():
            raw_policy_path = REPO_ROOT / raw_policy_path
        self._policy_path = raw_policy_path.resolve(strict=False)
        self._commands: dict[str, CommandPolicy] = {}
        self._load_policy()

    def _load_policy(self) -> None:
        """Load policy from JSON file."""
        if not self._policy_path.exists():
            logger.warning("OpenCLI policy file not found: %s", self._policy_path)
            return

        try:
            data = json.loads(self._policy_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load OpenCLI policy: %s", exc)
            return

        if not isinstance(data, dict):
            logger.error("Invalid OpenCLI policy format: expected dict")
            return

        commands = data.get("commands", [])
        if not isinstance(commands, list):
            logger.error("Invalid OpenCLI policy: commands must be a list")
            return

        for cmd_data in commands:
            if not isinstance(cmd_data, dict):
                continue

            try:
                policy = CommandPolicy(
                    capability_id=str(cmd_data.get("capability_id", "")),
                    command_id=str(cmd_data.get("command_id", "")),
                    command=list(cmd_data.get("command", [])),
                    output_format=str(cmd_data.get("output_format", "json")),
                    risk_level=str(cmd_data.get("risk_level", "low")),
                    auth_mode=str(cmd_data.get("auth_mode", "public")),
                    browser_mode=str(cmd_data.get("browser_mode", "none")),
                    allowed_args=dict(cmd_data.get("allowed_args") or {}),
                    retryable_exit_codes=list(cmd_data.get("retryable_exit_codes") or []),
                    capture_doctor_on_failure=bool(cmd_data.get("capture_doctor_on_failure", True)),
                )
                self._commands[policy.command_id] = policy
            except Exception as exc:
                logger.error("Failed to parse command policy: %s", exc)
                continue

        logger.info("Loaded %d opencli command policies", len(self._commands))

    def get_command_policy(self, command_id: str) -> CommandPolicy | None:
        """Get policy for a command ID."""
        return self._commands.get(command_id)

    def is_command_allowed(self, command_id: str) -> bool:
        """Check if command is in allowlist."""
        return command_id in self._commands

    def validate_args(self, command_id: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Validate arguments against policy schema.

        Returns:
            (valid, error_message)
        """
        policy = self.get_command_policy(command_id)
        if policy is None:
            return False, f"Command not in allowlist: {command_id}"

        for arg_name, arg_value in args.items():
            if arg_name not in policy.allowed_args:
                return False, f"Argument not allowed: {arg_name}"

            arg_schema = policy.allowed_args[arg_name]
            if not isinstance(arg_schema, dict):
                continue

            arg_type = arg_schema.get("type")
            if arg_type == "int":
                if not isinstance(arg_value, int):
                    return False, f"Argument {arg_name} must be int"
                min_val = arg_schema.get("min")
                max_val = arg_schema.get("max")
                if min_val is not None and arg_value < min_val:
                    return False, f"Argument {arg_name} must be >= {min_val}"
                if max_val is not None and arg_value > max_val:
                    return False, f"Argument {arg_name} must be <= {max_val}"
            elif arg_type == "string":
                if not isinstance(arg_value, str):
                    return False, f"Argument {arg_name} must be string"
                max_len = arg_schema.get("max_length")
                if max_len is not None and len(arg_value) > max_len:
                    return False, f"Argument {arg_name} exceeds max length {max_len}"

        return True, ""

    def list_commands(self) -> list[str]:
        """List all allowed command IDs."""
        return list(self._commands.keys())
