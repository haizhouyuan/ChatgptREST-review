#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "release_validation"
COMPILE_TARGETS = [
    "chatgptrest/api/app.py",
    "chatgptrest/api/routes_jobs.py",
    "chatgptrest/api/routes_advisor_v3.py",
    "ops/run_convergence_validation.py",
    "ops/run_convergence_live_matrix.py",
    "ops/run_convergence_soak.py",
]


def _default_pytest_bin(*, python_bin: str = sys.executable) -> str:
    python_path = Path(python_bin).expanduser()
    sibling_pytest = python_path.with_name("pytest")
    candidates = [sibling_pytest, REPO_ROOT / ".venv" / "bin" / "pytest"]
    candidates.extend(parent / ".venv" / "bin" / "pytest" for parent in REPO_ROOT.parents)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("pytest") or "pytest"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_output_dir(root: Path | None = None) -> Path:
    base = root or DEFAULT_OUTPUT_ROOT
    return base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_convergence_validation")


def _run_command(
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )


def _validation_env(*, include_auth_tokens: bool) -> dict[str, str]:
    env = os.environ.copy()
    if not include_auth_tokens:
        env.pop("CHATGPTREST_API_TOKEN", None)
        env.pop("CHATGPTREST_OPS_TOKEN", None)
    return env


def _collect_startup_manifest() -> dict[str, Any]:
    from chatgptrest.api.app import create_app

    app = create_app()
    manifest = dict(getattr(app.state, "startup_manifest", {}) or {})
    manifest.setdefault("status", "unknown")
    manifest.setdefault("route_inventory", [])
    manifest.setdefault("route_count", len(manifest["route_inventory"]))
    return manifest


def build_wave_plan(
    *,
    pytest_bin: str,
    python_bin: str,
    include_wave4: bool = False,
    include_wave5: bool = False,
    include_live: bool = False,
    include_fault: bool = False,
    include_soak: bool = False,
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = [
        {
            "wave": "wave0",
            "label": "Static and Boot Baseline",
            "kind": "pytest",
            "required": True,
            "command": [
                pytest_bin,
                "-q",
                "tests/test_api_startup_smoke.py",
                "tests/test_ops_endpoints.py",
            ],
        },
        {
            "wave": "wave1",
            "label": "Deterministic Contract Validation",
            "kind": "pytest",
            "required": True,
            "command": [
                pytest_bin,
                "-q",
                "tests/test_contract_v1.py",
                "tests/test_answers_extract.py",
                "tests/test_chatgpt_web_answer_rehydration.py",
                "tests/test_conversation_single_flight.py",
                "tests/test_routes_advisor_v3_security.py",
                "tests/test_client_ip.py",
            ],
        },
        {
            "wave": "wave2",
            "label": "Durable Lifecycle Validation",
            "kind": "pytest",
            "required": True,
            "command": [
                pytest_bin,
                "-q",
                "tests/test_advisor_api.py",
                "tests/test_advisor_orchestrate_api.py",
                "tests/test_advisor_runs_replay.py",
            ],
        },
        {
            "wave": "wave3",
            "label": "Knowledge and Identity Validation",
            "kind": "pytest",
            "required": True,
            "command": [
                pytest_bin,
                "-q",
                "tests/test_cognitive_api.py",
                "tests/test_memory_tenant_isolation.py",
                "tests/test_openmind_store_paths.py",
                "tests/test_role_pack.py",
                "tests/test_openmind_memory_business_flow.py",
            ],
        },
    ]
    if include_wave4:
        plan.append(
            {
                "wave": "wave4",
                "label": "Channel and Entry Convergence Validation",
                "kind": "pytest",
                "required": True,
                "command": [
                    pytest_bin,
                    "-q",
                    "tests/test_openclaw_cognitive_plugins.py",
                    "tests/test_feishu_ws_gateway.py",
                    "tests/test_feishu_async.py",
                    "tests/test_phase3_integration.py",
                    "tests/test_cli_chatgptrestctl.py",
                    "tests/test_mcp_advisor_tool.py",
                ],
            }
        )
    if include_wave5:
        plan.append(
            {
                "wave": "wave5",
                "label": "Business-Flow Simulation",
                "kind": "pytest",
                "required": False,
                "command": [
                    pytest_bin,
                    "-q",
                    "tests/test_business_flow_advise.py",
                    "tests/test_business_flow_deep_research.py",
                    "tests/test_business_flow_openclaw.py",
                    "tests/test_business_flow_multi_turn.py",
                    "tests/test_business_flow_planning_lane.py",
                ],
            }
        )
    if include_live:
        plan.append(
            {
                "wave": "wave6",
                "label": "Live Provider Validation",
                "kind": "script",
                "required": False,
                "command": [python_bin, str(REPO_ROOT / "ops" / "run_convergence_live_matrix.py")],
            }
        )
    if include_fault:
        plan.append(
            {
                "wave": "wave7",
                "label": "Fault Injection and Recovery",
                "kind": "pytest",
                "required": False,
                "command": [
                    pytest_bin,
                    "-q",
                    "tests/test_restart_recovery.py",
                    "tests/test_db_corruption_recovery.py",
                    "tests/test_network_partition.py",
                    "tests/test_repair_check.py",
                    "tests/test_viewer_watchdog.py",
                    "tests/test_feishu_async.py",
                ],
            }
        )
    if include_soak:
        plan.append(
            {
                "wave": "wave8",
                "label": "Shadow and Canary Governance Validation",
                "kind": "pytest",
                "required": False,
                "command": [
                    pytest_bin,
                    "-q",
                    "tests/test_shadow_mode.py",
                    "tests/test_canary_routing.py",
                ],
            }
        )
        plan.append(
            {
                "wave": "wave8_soak",
                "label": "Soak Monitoring Validation",
                "kind": "script",
                "required": False,
                "command": [
                    python_bin,
                    str(REPO_ROOT / "ops" / "run_convergence_soak.py"),
                    "--duration-seconds",
                    os.environ.get("CHATGPTREST_SOAK_SECONDS", "300"),
                ],
            }
        )
    return plan


def run_validation(
    *,
    output_dir: str | Path,
    pytest_bin: str | None = None,
    python_bin: str = sys.executable,
    include_wave4: bool = False,
    include_wave5: bool = False,
    include_live: bool = False,
    include_fault: bool = False,
    include_soak: bool = False,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    deterministic_env = _validation_env(include_auth_tokens=False)
    live_env = _validation_env(include_auth_tokens=True)

    started_at = _iso_now()
    startup_manifest = _collect_startup_manifest()
    startup_manifest_path = out / "startup_manifest.json"
    startup_manifest_path.write_text(
        json.dumps(startup_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    compile_cmd = [python_bin, "-m", "py_compile", *COMPILE_TARGETS]
    compile_started = time.time()
    compile_proc = _run_command(compile_cmd, env=deterministic_env)
    compile_duration = round(time.time() - compile_started, 3)
    (out / "compile.stdout.txt").write_text(compile_proc.stdout or "", encoding="utf-8")
    (out / "compile.stderr.txt").write_text(compile_proc.stderr or "", encoding="utf-8")
    compile_result = {
        "command": compile_cmd,
        "returncode": int(compile_proc.returncode),
        "ok": compile_proc.returncode == 0,
        "duration_seconds": compile_duration,
        "stdout_path": str(out / "compile.stdout.txt"),
        "stderr_path": str(out / "compile.stderr.txt"),
    }

    wave_results: list[dict[str, Any]] = []
    effective_pytest_bin = str(pytest_bin or _default_pytest_bin(python_bin=python_bin))
    for index, wave in enumerate(
        build_wave_plan(
            pytest_bin=effective_pytest_bin,
            python_bin=python_bin,
            include_wave4=include_wave4,
            include_wave5=include_wave5,
            include_live=include_live,
            include_fault=include_fault,
            include_soak=include_soak,
        ),
        start=1,
    ):
        started = time.time()
        command = list(wave["command"])
        wave_env = deterministic_env
        if str(wave["wave"]) == "wave6":
            command.append(str(out / "live_wave"))
            wave_env = live_env
        proc = _run_command(command, env=wave_env)
        duration = round(time.time() - started, 3)
        prefix = f"{index:02d}_{wave['wave']}"
        stdout_path = out / f"{prefix}.stdout.txt"
        stderr_path = out / f"{prefix}.stderr.txt"
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")
        wave_results.append(
            {
                "wave": wave["wave"],
                "label": wave["label"],
                "kind": wave["kind"],
                "required": bool(wave["required"]),
                "command": command,
                "returncode": int(proc.returncode),
                "ok": proc.returncode == 0,
                "duration_seconds": duration,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )

    required_ok = compile_result["ok"] and all(
        wave["ok"] for wave in wave_results if wave["required"]
    )
    overall_ok = required_ok and all(wave["ok"] for wave in wave_results)
    summary = {
        "ok": overall_ok,
        "required_ok": required_ok,
        "started_at": started_at,
        "finished_at": _iso_now(),
        "output_dir": str(out),
        "startup_manifest_path": str(startup_manifest_path),
        "compile": compile_result,
        "waves": wave_results,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readme_lines = [
        "# Convergence Validation Bundle",
        "",
        f"- `ok`: `{summary['ok']}`",
        f"- `required_ok`: `{summary['required_ok']}`",
        f"- `startup_manifest`: `{startup_manifest_path}`",
        f"- `compile_ok`: `{compile_result['ok']}`",
        "",
        "## Waves",
        "",
    ]
    for wave in wave_results:
        readme_lines.append(
            f"- `{wave['wave']}` `{wave['label']}` ok=`{wave['ok']}` rc=`{wave['returncode']}`"
        )
    (out / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run curated convergence validation waves and emit an evidence bundle."
    )
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--pytest-bin", default="")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--include-wave4", action="store_true")
    parser.add_argument("--include-wave5", action="store_true")
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--include-fault", action="store_true")
    parser.add_argument("--include-soak", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir()
    report = run_validation(
        output_dir=output_dir,
        pytest_bin=args.pytest_bin or None,
        python_bin=args.python_bin,
        include_wave4=bool(args.include_wave4),
        include_wave5=bool(args.include_wave5),
        include_live=bool(args.include_live),
        include_fault=bool(args.include_fault),
        include_soak=bool(args.include_soak),
    )
    print(json.dumps(report, ensure_ascii=False, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
