#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "MANIFEST.json",
    "README.md",
    "summary.json",
    "case_matrix.json",
    "tool_versions.json",
    "git_status.txt",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bundle(*, bundle_dir: str | Path) -> dict[str, Any]:
    root = Path(bundle_dir)
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    if missing:
        return {
            "ok": False,
            "bundle_dir": str(root),
            "missing_files": missing,
            "checks": {"required_files_ok": False},
        }

    manifest = read_json(root / "MANIFEST.json")
    case_matrix = read_json(root / "case_matrix.json")
    checks = {
        "required_files_ok": True,
        "case_count_matches_manifest_ok": len(case_matrix.get("cases", [])) == int(manifest["summary"]["case_count"]),
        "cases_matching_expectation_matches_manifest_ok": sum(
            1 for case in case_matrix.get("cases", []) if case.get("verdict_matches_expectation")
        )
        == int(manifest["summary"]["cases_matching_expectation"]),
    }

    hash_failures: list[dict[str, str]] = []
    for case in case_matrix.get("cases", []):
        for group in ("inputs", "artifacts"):
            for record in case.get(group, []):
                materialized = Path(record["materialized_path"])
                if not materialized.exists():
                    hash_failures.append({"alias": record["alias"], "reason": "materialized_missing"})
                    continue
                if sha256_file(materialized) != record["sha256"]:
                    hash_failures.append({"alias": record["alias"], "reason": "sha_mismatch"})
    checks["materialized_hashes_ok"] = not hash_failures

    return {
        "ok": all(checks.values()),
        "bundle_dir": str(root),
        "missing_files": [],
        "checks": checks,
        "hash_failures": hash_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a skill suite evidence bundle for internal consistency.")
    parser.add_argument("--bundle-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(validate_bundle(bundle_dir=args.bundle_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
