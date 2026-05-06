"""Change obligations — determine doc/test obligations for changed files."""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def compute_change_obligations(changed_files: list[str] | None = None) -> list[dict[str, Any]]:
    """Compute change obligations for changed files.

    Args:
        changed_files: List of changed file paths

    Returns:
        List of obligations:
        [
            {
                "pattern": "chatgptrest/mcp/",
                "plane": "public_agent",
                "must_update": ["AGENTS.md"],
                "baseline_tests": ["tests/test_mcp_server_entrypoints.py"],
                "dynamic_test_strategy": "gitnexus_impact",
                "reason": "...",
                "matched_files": ["chatgptrest/mcp/agent_mcp.py"],
            },
            ...
        ]
    """
    if not changed_files:
        return []

    registry_path = REPO_ROOT / "ops" / "registries" / "change_obligations.yaml"
    if not registry_path.exists():
        return []

    with open(registry_path) as f:
        data = yaml.safe_load(f)

    obligations_data = data.get("obligations", [])
    results: list[dict[str, Any]] = []

    normalized_changed_files = [_normalize_path(path) for path in changed_files]

    for obligation in obligations_data:
        pattern = obligation.get("pattern", "")
        matched = []

        for file_path in normalized_changed_files:
            # Match pattern (supports glob-like patterns)
            if _matches_pattern(file_path, pattern):
                matched.append(file_path)

        if matched:
            must_update = [_normalize_path(path) for path in obligation.get("must_update", [])]
            baseline_tests = [_normalize_path(path) for path in obligation.get("baseline_tests", [])]
            results.append({
                "pattern": pattern,
                "plane": obligation.get("plane", ""),
                "must_update": must_update,
                "baseline_tests": baseline_tests,
                "dynamic_test_strategy": obligation.get("dynamic_test_strategy", "none"),
                "reason": obligation.get("reason", ""),
                "matched_files": matched,
                "missing_updates": [path for path in must_update if path not in normalized_changed_files],
            })

    return results


def _matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if file_path matches pattern.

    Supports:
    - Exact match: "chatgptrest/mcp/agent_mcp.py"
    - Directory prefix: "chatgptrest/mcp/"
    - Glob patterns: "chatgptrest/mcp/*.py"
    """
    # Exact match
    if file_path == pattern:
        return True

    # Directory prefix
    if pattern.endswith("/") and file_path.startswith(pattern):
        return True

    # Glob pattern
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(file_path, pattern)

    # Substring match (for directory patterns without trailing /)
    if pattern in file_path:
        return True

    return False


def _normalize_path(path: str) -> str:
    return Path(str(path)).as_posix().lstrip("./")


def validate_obligations(obligations: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate that obligation paths exist on disk.

    Args:
        obligations: List of obligations from compute_change_obligations()

    Returns:
        {
            "ok": bool,
            "missing_docs": [...],
            "missing_tests": [...],
        }
    """
    missing_docs = []
    missing_tests = []
    missing_updates = []
    required_docs: list[str] = []
    required_tests: list[str] = []

    for obligation in obligations:
        for doc_path in obligation.get("must_update", []):
            if doc_path not in required_docs:
                required_docs.append(doc_path)
            full_path = REPO_ROOT / doc_path
            if not full_path.exists():
                missing_docs.append(doc_path)

        for test_path in obligation.get("baseline_tests", []):
            if test_path not in required_tests:
                required_tests.append(test_path)
            full_path = REPO_ROOT / test_path
            if not full_path.exists():
                missing_tests.append(test_path)

        for doc_path in obligation.get("missing_updates", []):
            if doc_path not in missing_updates:
                missing_updates.append(doc_path)

    return {
        "ok": not missing_docs and not missing_tests and not missing_updates,
        "required_docs": required_docs,
        "required_tests": required_tests,
        "missing_docs": missing_docs,
        "missing_tests": missing_tests,
        "missing_updates": missing_updates,
    }
