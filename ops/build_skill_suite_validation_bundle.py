#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "skill_suite_validation_bundles"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return slug.strip("._") or "item"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, role: str, alias: str | None = None) -> dict[str, Any]:
    return {
        "alias": alias or path.name,
        "role": role,
        "source_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def materialize_file(source: Path, destination: Path, *, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    if mode in {"auto", "hardlink"}:
        try:
            os.link(source, destination)
            return
        except OSError:
            if mode == "hardlink":
                raise
    if mode == "symlink":
        destination.symlink_to(source)
        return
    shutil.copy2(source, destination)


def inventory_directory(source_dir: Path, dest_dir: Path, *, mode: str, role: str, alias_prefix: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        relative = source.relative_to(source_dir)
        destination = dest_dir / relative
        materialize_file(source, destination, mode=mode)
        record = file_record(source, role=role, alias=f"{alias_prefix}/{relative.as_posix()}")
        record["materialized_path"] = str(destination)
        record["relative_path"] = relative.as_posix()
        records.append(record)
    return records


def inventory_file(source: Path, dest_dir: Path, *, mode: str, role: str, alias: str) -> dict[str, Any]:
    destination = dest_dir / slugify(source.name)
    materialize_file(source, destination, mode=mode)
    record = file_record(source, role=role, alias=alias)
    record["materialized_path"] = str(destination)
    record["relative_path"] = destination.name
    return record


def run_capture(command: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update({str(key): str(value) for key, value in env.items()})
    completed = subprocess.run(
        command,
        cwd=cwd or str(REPO_ROOT),
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "cwd": cwd or str(REPO_ROOT),
        "env_overrides": env or {},
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def git_snapshot() -> dict[str, Any]:
    head = run_capture(["git", "rev-parse", "HEAD"])
    status = run_capture(["git", "status", "--short"])
    return {
        "head": head["stdout"].strip(),
        "head_exit_code": head["exit_code"],
        "dirty": bool(status["stdout"].strip()),
        "status_stdout": status["stdout"],
        "status_exit_code": status["exit_code"],
    }


def extract_json_values(payload: Any, path_expression: str) -> list[Any]:
    parts = [part for part in path_expression.split(".") if part]
    current = [payload]
    for part in parts:
        next_values: list[Any] = []
        for item in current:
            if part == "*":
                if isinstance(item, list):
                    next_values.extend(item)
                elif isinstance(item, dict):
                    next_values.extend(item.values())
                continue
            if isinstance(item, dict) and part in item:
                next_values.append(item[part])
                continue
            if isinstance(item, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(item):
                    next_values.append(item[index])
        current = next_values
    return current


def evaluate_check(payload: Any, check: dict[str, Any]) -> dict[str, Any]:
    values = extract_json_values(payload, str(check["path"]))
    op = str(check["op"])
    expected = check.get("value")
    passed = False
    actual: Any = values
    if op == "eq":
        actual = values[0] if len(values) == 1 else values
        passed = actual == expected
    elif op == "contains":
        actual = values
        passed = expected in values
    elif op == "contains_all":
        actual = values
        passed = all(item in values for item in list(expected or []))
    elif op == "in":
        actual = values[0] if len(values) == 1 else values
        passed = actual in list(expected or [])
    elif op == "ge":
        actual = values[0] if values else None
        passed = actual is not None and actual >= expected
    elif op == "le":
        actual = values[0] if values else None
        passed = actual is not None and actual <= expected
    else:
        raise ValueError(f"Unsupported check op: {op}")
    return {
        "id": check["id"],
        "source_alias": check["source_alias"],
        "path": check["path"],
        "op": op,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def bundle_case(case: dict[str, Any], *, bundle_root: Path, mode: str) -> dict[str, Any]:
    case_id = str(case["case_id"])
    case_root = bundle_root / "cases" / slugify(case_id)
    input_root = case_root / "inputs"
    evidence_root = case_root / "evidence"
    inputs: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    alias_payloads: dict[str, Any] = {}
    missing_paths: list[str] = []

    for item in case.get("inputs", []):
        source = Path(item["path"]).expanduser()
        alias = str(item.get("alias") or source.name)
        if not source.exists():
            missing_paths.append(str(source))
            continue
        record = inventory_file(source, input_root / slugify(alias), mode=mode, role="input", alias=alias)
        record["classification"] = item.get("classification", case.get("classification", "unspecified"))
        inputs.append(record)

    for item in case.get("artifacts", []):
        source = Path(item["path"]).expanduser()
        alias = str(item.get("alias") or source.name)
        role = str(item.get("role") or "artifact")
        if not source.exists():
            missing_paths.append(str(source))
            continue
        if item.get("type", "file") == "dir":
            records = inventory_directory(
                source,
                evidence_root / slugify(alias),
                mode=mode,
                role=role,
                alias_prefix=alias,
            )
            artifacts.extend(records)
        else:
            record = inventory_file(source, evidence_root / slugify(alias), mode=mode, role=role, alias=alias)
            artifacts.append(record)
            if str(source).endswith(".json"):
                alias_payloads[alias] = read_json(source)

    check_results: list[dict[str, Any]] = []
    for check in case.get("checks", []):
        alias = str(check["source_alias"])
        payload = alias_payloads.get(alias)
        if payload is None:
            check_results.append(
                {
                    "id": check["id"],
                    "source_alias": alias,
                    "path": check["path"],
                    "op": check["op"],
                    "expected": check.get("value"),
                    "actual": None,
                    "passed": False,
                    "error": "source_alias_missing_or_not_json",
                }
            )
            continue
        check_results.append(evaluate_check(payload, check))

    required_files = [str(path) for path in case.get("required_files", [])]
    required_results = []
    for relative in required_files:
        target = Path(relative)
        passed = any(record.get("relative_path") == target.name or record["alias"].endswith(relative) for record in artifacts)
        required_results.append({"path": relative, "passed": passed})

    expected_outcome = str(case.get("expected_outcome", "pass"))
    checks_ok = all(result["passed"] for result in check_results) and all(result["passed"] for result in required_results) and not missing_paths
    if expected_outcome == "fail":
        verdict_matches_expectation = not checks_ok
    elif expected_outcome == "warn":
        verdict_matches_expectation = not missing_paths
    else:
        verdict_matches_expectation = checks_ok

    case_manifest = {
        "case_id": case_id,
        "suite": case.get("suite", ""),
        "variant": case.get("variant", ""),
        "classification": case.get("classification", "unspecified"),
        "expected_outcome": expected_outcome,
        "inputs": inputs,
        "artifacts": artifacts,
        "missing_paths": missing_paths,
        "checks": check_results,
        "required_files": required_results,
        "checks_ok": checks_ok,
        "verdict_matches_expectation": verdict_matches_expectation,
        "notes": case.get("notes", ""),
    }
    write_json(case_root / "case_manifest.json", case_manifest)
    return case_manifest


def collect_tool_versions(config: dict[str, Any], *, bundle_root: Path) -> list[dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    for item in config.get("captures", []):
        capture_id = str(item["id"])
        result = run_capture(
            list(item["command"]),
            cwd=item.get("cwd"),
            env=item.get("env"),
        )
        write_text(bundle_root / "captures" / f"{slugify(capture_id)}.stdout.txt", result["stdout"])
        write_text(bundle_root / "captures" / f"{slugify(capture_id)}.stderr.txt", result["stderr"])
        summary = {
            "id": capture_id,
            "exit_code": result["exit_code"],
            "command": result["command"],
            "cwd": result["cwd"],
            "env_overrides": result["env_overrides"],
            "stdout_path": str(bundle_root / "captures" / f"{slugify(capture_id)}.stdout.txt"),
            "stderr_path": str(bundle_root / "captures" / f"{slugify(capture_id)}.stderr.txt"),
        }
        write_json(bundle_root / "captures" / f"{slugify(capture_id)}.json", summary)
        captures.append(summary)
    return captures


def collect_runner_inventory(config: dict[str, Any], *, bundle_root: Path, mode: str) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for item in config.get("runner_files", []):
        path = Path(item["path"]).expanduser()
        alias = str(item.get("alias") or path.name)
        if not path.exists():
            inventory.append({"alias": alias, "source_path": str(path), "missing": True})
            continue
        record = inventory_file(path, bundle_root / "runners" / slugify(alias), mode=mode, role="runner", alias=alias)
        inventory.append(record)
    return inventory


def build_bundle(*, config_path: str | Path, output_dir: str | Path, mode: str = "auto") -> dict[str, Any]:
    config = read_json(Path(config_path))
    bundle_root = Path(output_dir)
    bundle_root.mkdir(parents=True, exist_ok=True)

    git_state = git_snapshot()
    write_text(bundle_root / "git_status.txt", git_state["status_stdout"])

    runner_inventory = collect_runner_inventory(config, bundle_root=bundle_root, mode=mode)
    captures = collect_tool_versions(config, bundle_root=bundle_root)

    case_results = [bundle_case(case, bundle_root=bundle_root, mode=mode) for case in config.get("cases", [])]

    summary = {
        "validation_id": config["validation_id"],
        "generated_at": utc_now(),
        "bundle_root": str(bundle_root),
        "case_count": len(case_results),
        "cases_checks_ok": sum(1 for case in case_results if case["checks_ok"]),
        "cases_matching_expectation": sum(1 for case in case_results if case["verdict_matches_expectation"]),
        "cases_with_missing_paths": sum(1 for case in case_results if case["missing_paths"]),
    }

    manifest = {
        "validation_id": config["validation_id"],
        "generated_at": utc_now(),
        "bundle_root": str(bundle_root),
        "mode": mode,
        "repo": {
            "root": str(REPO_ROOT),
            "git_head": git_state["head"],
            "git_dirty": git_state["dirty"],
        },
        "environment": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": platform.node(),
        },
        "governance": config.get("governance", {}),
        "rubric": config.get("rubric", {}),
        "runner_inventory": runner_inventory,
        "captures": captures,
        "summary": summary,
        "cases": [
            {
                "case_id": case["case_id"],
                "suite": case["suite"],
                "variant": case["variant"],
                "expected_outcome": case["expected_outcome"],
                "checks_ok": case["checks_ok"],
                "verdict_matches_expectation": case["verdict_matches_expectation"],
                "missing_paths": case["missing_paths"],
            }
            for case in case_results
        ],
    }
    write_json(bundle_root / "MANIFEST.json", manifest)
    write_json(bundle_root / "case_matrix.json", {"cases": case_results})
    write_json(bundle_root / "tool_versions.json", {"captures": captures, "runner_inventory": runner_inventory})
    write_json(bundle_root / "summary.json", summary)
    write_text(
        bundle_root / "README.md",
        "\n".join(
            [
                f"# {config['validation_id']}",
                "",
                f"- generated_at: `{manifest['generated_at']}`",
                f"- git_head: `{manifest['repo']['git_head']}`",
                f"- git_dirty: `{manifest['repo']['git_dirty']}`",
                f"- case_count: `{summary['case_count']}`",
                f"- cases_checks_ok: `{summary['cases_checks_ok']}`",
                f"- cases_matching_expectation: `{summary['cases_matching_expectation']}`",
                "",
                "## Governance",
                "",
                json.dumps(config.get("governance", {}), ensure_ascii=False, indent=2),
                "",
                "## Rubric",
                "",
                json.dumps(config.get("rubric", {}), ensure_ascii=False, indent=2),
                "",
            ]
        )
        + "\n",
    )
    return {
        "ok": True,
        "bundle_root": str(bundle_root),
        "manifest_path": str(bundle_root / "MANIFEST.json"),
        "summary_path": str(bundle_root / "summary.json"),
        "case_matrix_path": str(bundle_root / "case_matrix.json"),
    }


def default_output_dir(validation_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUTPUT_ROOT / f"{stamp}_{slugify(validation_id)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable evidence bundle for skill suite validation runs.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--mode", choices=["auto", "hardlink", "copy", "symlink"], default="auto")
    args = parser.parse_args()

    config = read_json(Path(args.config))
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(config["validation_id"])
    result = build_bundle(config_path=args.config, output_dir=output_dir, mode=args.mode)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
