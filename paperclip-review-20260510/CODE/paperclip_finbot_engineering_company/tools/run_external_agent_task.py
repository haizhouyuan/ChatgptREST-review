#!/usr/bin/env python3
"""Run a bounded external agent task and capture durable evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


RUNTIME_COMMANDS = {
    "claudeminmax": [
        "claudeminmax",
        "-p",
        "{prompt}",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
        "--add-dir",
        str(ROOT),
        "--add-dir",
        "/vol1/1000/projects/planning",
        "--max-budget-usd",
        "20",
    ],
    "gemini": [
        "gemini",
        "--prompt",
        "{prompt}",
        "--approval-mode",
        "yolo",
        "--output-format",
        "text",
        "--include-directories",
        str(ROOT),
        "--include-directories",
        "/vol1/1000/projects/planning",
    ],
}


def resolve_inside_root(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    root_resolved = ROOT.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise SystemExit(f"path outside repo root: {resolved}")
    return resolved


def render_prompt(task_path: Path, output_dir: Path) -> str:
    task_text = task_path.read_text(encoding="utf-8")
    return render_prompt_with_mode(task_path, output_dir, task_text, "artifact", [])


def render_prompt_with_mode(task_path: Path, output_dir: Path, task_text: str, mode: str, allowed_write_scopes: list[str]) -> str:
    if mode == "repo_edit":
        write_rule = "\n".join(
            [
                "- You may edit only the allowed write scopes listed below.",
                "- Allowed write scopes:",
                *[f"  - {scope}" for scope in allowed_write_scopes],
                "- Still write task evidence artifacts under the output directory above.",
            ]
        )
    else:
        write_rule = "\n".join(
            [
                "- Write deliverables only under the output directory above.",
                "- Do not modify source code, contracts, global config, Paperclip runtime state, MCP/skill registries, or files outside this repository.",
            ]
        )
    return f"""You are executing a bounded Finbot Engineering Company task.

Repository root:
{ROOT}

Output directory:
{output_dir}

Hard instructions:
{write_rule}
- Do not run broker APIs, trading APIs, cron jobs, daemons, package installs, service restarts, or production Paperclip mutations.
- For finance content, produce research-only artifacts. Do not produce buy/sell advice, position sizing, or trade execution instructions.
- If required evidence is unavailable, write the gap/blocker explicitly instead of guessing.
- End with a concise completion note naming every file you wrote.

Task contract:

{task_text}
"""


def build_command(runtime: str, prompt: str) -> list[str]:
    try:
        template = RUNTIME_COMMANDS[runtime]
    except KeyError as exc:
        raise SystemExit(f"unsupported runtime: {runtime}") from exc
    return [prompt if part == "{prompt}" else part for part in template]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, choices=sorted(RUNTIME_COMMANDS))
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=5400)
    parser.add_argument("--mode", choices=["artifact", "repo_edit"], default="artifact")
    parser.add_argument("--allowed-write-scope", action="append", default=[])
    args = parser.parse_args(argv)

    task_path = resolve_inside_root(args.task)
    output_dir = resolve_inside_root(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    task_text = task_path.read_text(encoding="utf-8")
    prompt = render_prompt_with_mode(task_path, output_dir, task_text, args.mode, args.allowed_write_scope)
    command = build_command(args.runtime, prompt)

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    stdout_path = output_dir / f"{args.runtime}_stdout.txt"
    stderr_path = output_dir / f"{args.runtime}_stderr.txt"
    status_path = output_dir / f"{args.runtime}_status.json"

    status = {
        "runtime": args.runtime,
        "task": str(task_path.relative_to(ROOT)),
        "output_dir": str(output_dir.relative_to(ROOT)),
        "started_at": started_at,
        "timeout_seconds": args.timeout_seconds,
        "command_argv_prefix": command[:1],
        "status": "running",
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout=args.timeout_seconds,
                check=False,
                env=os.environ.copy(),
            )
            returncode = result.returncode
            final_status = "pass" if returncode == 0 else "failed"
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = 124
            final_status = "timeout"
            timed_out = True

    ended_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    if "Error: Exceeded USD budget" in stdout_text:
        final_status = "failed"
        returncode = 1

    produced_files = sorted(
        str(path.relative_to(output_dir))
        for path in output_dir.rglob("*")
        if path.is_file() and path.name not in {stdout_path.name, stderr_path.name, status_path.name}
    )
    status.update(
        {
            "status": final_status,
            "timed_out": timed_out,
            "returncode": returncode,
            "ended_at": ended_at,
            "stdout_path": str(stdout_path.relative_to(ROOT)),
            "stderr_path": str(stderr_path.relative_to(ROOT)),
            "produced_files": produced_files,
        }
    )
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if final_status == "pass" else returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
