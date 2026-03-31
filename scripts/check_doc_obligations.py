#!/usr/bin/env python3
"""Check doc obligations for changed files.

Reads change_obligations.yaml and reports:
- required docs/tests for the changed scope
- missing doc updates (required docs not present in the changed file set)
- missing on-disk doc/test paths in the registry

Usage:
    python scripts/check_doc_obligations.py --diff HEAD~1..HEAD
    python scripts/check_doc_obligations.py --changed-files file1.py file2.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.repo_cognition.obligations import (  # noqa: E402
    compute_change_obligations,
    validate_obligations,
)


def get_changed_files_from_diff(diff_spec: str) -> list[str]:
    """Get changed files from git diff."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", diff_spec],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        )
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception as exc:
        print(f"Error getting changed files: {exc}", file=sys.stderr)
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check doc obligations for changed files")
    parser.add_argument("--diff", help="Git diff spec (e.g., HEAD~1..HEAD, origin/master..HEAD)")
    parser.add_argument("--changed-files", nargs="*", help="Changed file paths")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    # Get changed files
    if args.diff:
        changed_files = get_changed_files_from_diff(args.diff)
    elif args.changed_files:
        changed_files = args.changed_files
    else:
        # Default: unstaged + staged changes
        changed_files = get_changed_files_from_diff("HEAD")

    if not changed_files:
        if args.json:
            print(json.dumps({"ok": True, "obligations": [], "note": "No changed files"}))
        else:
            print("No changed files found.")
        return 0

    # Compute obligations
    obligations = compute_change_obligations(changed_files)

    if not obligations:
        if args.json:
            print(json.dumps({"ok": True, "obligations": [], "note": "No obligations"}))
        else:
            print("No doc/test obligations for changed files.")
        return 0

    # Validate obligations
    validation = validate_obligations(obligations)

    # Prepare output
    result = {
        "ok": validation["ok"],
        "obligations": obligations,
        "validation": validation,
        "changed_files": changed_files,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if validation["ok"] else 1
    else:
        print(f"Changed files: {len(changed_files)}")
        print(f"Obligations: {len(obligations)}")
        print()

        for obligation in obligations:
            print(f"Pattern: {obligation['pattern']} ({obligation['plane']})")
            print(f"  Reason: {obligation['reason']}")
            print(f"  Matched files: {', '.join(obligation['matched_files'])}")

            if obligation['must_update']:
                print(f"  Must update docs:")
                for doc in obligation['must_update']:
                    exists = (REPO_ROOT / doc).exists()
                    included = doc not in obligation.get("missing_updates", [])
                    mark = "✅" if exists and included else "❌"
                    suffix = "" if included else " (not updated in this change set)"
                    print(f"    {mark} {doc}")
                    if suffix:
                        print(f"       {suffix}")

            if obligation['baseline_tests']:
                print(f"  Baseline tests:")
                for test in obligation['baseline_tests']:
                    exists = (REPO_ROOT / test).exists()
                    mark = "✅" if exists else "❌"
                    print(f"    {mark} {test}")

            if obligation['dynamic_test_strategy'] != "none":
                print(f"  Dynamic test strategy: {obligation['dynamic_test_strategy']}")

            print()

        if not validation["ok"]:
            print("⚠️  VALIDATION FAILED")
            if validation["missing_docs"]:
                print(f"  Missing docs: {', '.join(validation['missing_docs'])}")
            if validation["missing_tests"]:
                print(f"  Missing tests: {', '.join(validation['missing_tests'])}")
            if validation["missing_updates"]:
                print(f"  Missing doc updates: {', '.join(validation['missing_updates'])}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
