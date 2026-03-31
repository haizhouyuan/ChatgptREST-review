#!/usr/bin/env python3
"""Operator smoke test for OpenCLIExecutor.

Tests subprocess wrapper without touching advisor_agent_turn.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatgptrest.executors.opencli_contracts import OpenCLIExecutionRequest
from chatgptrest.executors.opencli_executor import OpenCLIExecutor
from chatgptrest.executors.opencli_policy import OpenCLIExecutionPolicy


def main() -> int:
    """Run smoke test."""
    print("=== OpenCLI Executor Smoke Test ===\n")

    # Load policy
    policy = OpenCLIExecutionPolicy()
    print(f"Loaded policy with {len(policy.list_commands())} commands")
    print(f"Allowed commands: {policy.list_commands()}\n")

    # Create executor
    executor = OpenCLIExecutor(policy=policy)

    # Test 1: hackernews.top
    print("Test 1: hackernews.top with limit=5")
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="public_web_read",
        command_id="hackernews.top",
        args={"limit": 5},
        timeout_seconds=30,
    )

    result = executor.execute(request)
    print(f"  Result: ok={result.ok}, exit_code={result.exit_code}")
    print(f"  Error type: {result.error_type}")
    print(f"  Retryable: {result.retryable}")
    print(f"  Artifacts: {len(result.artifacts)} files")
    structured = result.structured_result
    if isinstance(structured, dict):
        print(f"  Structured result keys: {list(structured.keys())}")
    elif isinstance(structured, list):
        print(f"  Structured result shape: list[{len(structured)}]")
    else:
        print(f"  Structured result type: {type(structured).__name__}")
    print(f"  Timing: {result.timing.get('elapsed_seconds', 0):.2f}s\n")

    if not result.ok:
        print(f"  Error message: {result.error_message}")
        print(f"  Diagnostics: {result.diagnostics}\n")
        return 1

    # Test 2: Invalid command
    print("Test 2: Invalid command (not in allowlist)")
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="invalid",
        command_id="invalid.command",
        args={},
        timeout_seconds=30,
    )

    result = executor.execute(request)
    print(f"  Result: ok={result.ok}, exit_code={result.exit_code}")
    print(f"  Error type: {result.error_type}")
    print(f"  Expected: usage_error")
    assert result.error_type == "usage_error", "Should reject invalid command"
    print("  ✅ Correctly rejected\n")

    # Test 3: Invalid args
    print("Test 3: Invalid args (limit out of range)")
    request = OpenCLIExecutionRequest(
        executor_kind="opencli",
        capability_id="public_web_read",
        command_id="hackernews.top",
        args={"limit": 100},  # Max is 20
        timeout_seconds=30,
    )

    result = executor.execute(request)
    print(f"  Result: ok={result.ok}, exit_code={result.exit_code}")
    print(f"  Error type: {result.error_type}")
    print(f"  Expected: usage_error")
    assert result.error_type == "usage_error", "Should reject invalid args"
    print("  ✅ Correctly rejected\n")

    print("=== Smoke Test Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
