#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "ops" / "next_stage_release_gate_pack_manifest_v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "next_stage_release_gate_pack"


def _now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "next-stage-release-gate-pack-v1":
        raise ValueError(f"unexpected schema_version in {path}: {data.get('schema_version')!r}")
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError(f"{path} must contain a non-empty gates list")
    return data


def _expand(value: Any, placeholders: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format(**placeholders)
    if isinstance(value, list):
        return [_expand(item, placeholders) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, placeholders) for key, item in value.items()}
    return value


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_command(
    *,
    gate_dir: Path,
    index: int,
    command: dict[str, Any],
    repo_root: Path,
    stamp: str,
) -> dict[str, Any]:
    label = str(command.get("label") or f"command_{index}")
    placeholders = {
        "repo_root": str(repo_root),
        "gate_dir": str(gate_dir),
        "stamp": stamp,
    }
    argv = _expand(command.get("argv") or [], placeholders)
    if not isinstance(argv, list) or not argv:
        raise ValueError(f"gate command {label!r} must provide non-empty argv")
    env = os.environ.copy()
    env_update = _expand(command.get("env") or {}, placeholders)
    if not isinstance(env_update, dict):
        raise ValueError(f"gate command {label!r} env must be a dict if provided")
    env.update({str(key): str(value) for key, value in env_update.items()})
    timeout_seconds = int(command.get("timeout_seconds") or 0) or None
    started = time.time()
    proc = subprocess.run(
        argv,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_seconds,
        check=False,
    )
    duration_seconds = round(time.time() - started, 3)

    stdout_path = gate_dir / f"{index:02d}_{label}.stdout.txt"
    stderr_path = gate_dir / f"{index:02d}_{label}.stderr.txt"
    _write_text(stdout_path, proc.stdout)
    _write_text(stderr_path, proc.stderr)
    result = {
        "label": label,
        "argv": argv,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_seconds": duration_seconds,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "timeout_seconds": timeout_seconds,
    }
    (gate_dir / f"{index:02d}_{label}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _relative_file_listing(path: Path) -> list[str]:
    files: list[str] = []
    if not path.exists():
        return files
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        files.append(str(file_path.relative_to(path)))
    return files


def run_release_gate_pack(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    stamp = _now_stamp()
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    gate_results: list[dict[str, Any]] = []
    for gate in manifest["gates"]:
        gate_id = str(gate.get("gate_id") or "").strip()
        if not gate_id:
            raise ValueError("every gate must provide a non-empty gate_id")
        gate_dir = run_dir / gate_id
        gate_dir.mkdir(parents=True, exist_ok=True)
        commands = gate.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"gate {gate_id!r} must provide a non-empty commands list")
        command_results = [
            _run_command(
                gate_dir=gate_dir,
                index=index,
                command=command,
                repo_root=repo_root,
                stamp=stamp,
            )
            for index, command in enumerate(commands, start=1)
        ]
        gate_passed = all(result["passed"] for result in command_results)
        gate_result = {
            "gate_id": gate_id,
            "description": str(gate.get("description") or ""),
            "passed": gate_passed,
            "num_commands": len(command_results),
            "num_failed_commands": sum(1 for result in command_results if not result["passed"]),
            "commands": command_results,
            "gate_dir": str(gate_dir),
            "files": _relative_file_listing(gate_dir),
        }
        (gate_dir / "manifest.json").write_text(
            json.dumps(gate_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        gate_results.append(gate_result)

    summary = {
        "ok": all(gate["passed"] for gate in gate_results),
        "schema_version": manifest["schema_version"],
        "description": str(manifest.get("description") or ""),
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "run_dir": str(run_dir),
        "num_gates": len(gate_results),
        "num_passed": sum(1 for gate in gate_results if gate["passed"]),
        "num_failed": sum(1 for gate in gate_results if not gate["passed"]),
        "gates": gate_results,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Next-Stage Unified Release Gate Pack",
        "",
        f"- `ok`: `{summary['ok']}`",
        f"- `num_gates`: `{summary['num_gates']}`",
        f"- `num_passed`: `{summary['num_passed']}`",
        f"- `num_failed`: `{summary['num_failed']}`",
        f"- `manifest_path`: `{manifest_path}`",
        "",
        "## Gates",
        "",
    ]
    for gate in gate_results:
        lines.append(f"### `{gate['gate_id']}`")
        lines.append("")
        lines.append(f"- `passed`: `{gate['passed']}`")
        lines.append(f"- `num_commands`: `{gate['num_commands']}`")
        lines.append(f"- `num_failed_commands`: `{gate['num_failed_commands']}`")
        lines.append(f"- `gate_dir`: `{gate['gate_dir']}`")
        lines.append("")
        for result in gate["commands"]:
            lines.append(
                f"- `{result['label']}` rc={result['returncode']} duration={result['duration_seconds']}s "
                f"stdout=`{result['stdout_path']}` stderr=`{result['stderr_path']}`"
            )
        lines.append("")
    markdown_path = run_dir / "summary.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the unified next-stage release gate pack.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    summary = run_release_gate_pack(
        manifest_path=Path(args.manifest),
        output_root=Path(args.output_root),
        repo_root=REPO_ROOT,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
