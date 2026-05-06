#!/usr/bin/env python3
"""ChatgptREST closeout wrapper.

Runs repo-specific governance checks before delegating to the shared closeout
script. This makes doc-obligation validation part of the actual workflow
instead of a documentation-only promise.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_doc_obligations.py"
UPSTREAM_CLOSEOUT = Path("/vol1/maint/ops/scripts/agent_task_closeout.sh")
DEFAULT_CLOSEOUT_ENV_FILES = (
    "/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env",
    "/vol1/maint/MAIN/secrets/credentials.env",
    str(Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"),
)


def _repo_dirty() -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(str(proc.stdout or "").strip())


def _default_diff_spec(status: str) -> str:
    if status == "partial":
        return "HEAD"
    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD~1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if parent.returncode == 0 and not _repo_dirty():
        return "HEAD~1..HEAD"
    return "HEAD"


def _run_doc_checker(*, diff_spec: str, changed_files: list[str]) -> dict:
    command = [sys.executable, str(CHECKER), "--json"]
    if changed_files:
        command.extend(["--changed-files", *changed_files])
    elif diff_spec:
        command.extend(["--diff", diff_spec])
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "error": f"invalid checker output: {proc.stdout[:200]}"}
    payload["exit_code"] = proc.returncode
    if proc.stderr:
        payload["stderr"] = proc.stderr[:500]
    return payload


def _closeout_env_files() -> list[Path]:
    raw = os.environ.get("CHATGPTREST_CLOSEOUT_ENV_FILES", "").strip()
    values = [item.strip() for item in raw.split(",") if item.strip()] if raw else list(DEFAULT_CLOSEOUT_ENV_FILES)
    out: list[Path] = []
    seen: set[str] = set()
    for item in values:
        path = Path(item).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _read_env_value_from_files(*names: str) -> str:
    wanted = {str(name).strip() for name in names if str(name).strip()}
    if not wanted:
        return ""
    for path in _closeout_env_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in wanted:
                return value.strip().strip("'\"")
    return ""


def _build_closeout_env() -> dict[str, str]:
    env = dict(os.environ)
    mirror_key = (
        env.get("CHATGPTREST_TELEMETRY_MIRROR_API_KEY", "").strip()
        or env.get("OPENMIND_API_KEY", "").strip()
        or _read_env_value_from_files("CHATGPTREST_TELEMETRY_MIRROR_API_KEY", "OPENMIND_API_KEY")
    )
    if mirror_key:
        env.setdefault("OPENMIND_API_KEY", mirror_key)
        env.setdefault("CHATGPTREST_TELEMETRY_MIRROR_API_KEY", mirror_key)
    return env


def _forward_closeout(args: argparse.Namespace, *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        str(UPSTREAM_CLOSEOUT),
        "--repo",
        str(REPO_ROOT),
        "--agent",
        args.agent,
        "--status",
        args.status,
        "--summary",
        args.summary,
    ]
    if args.pending_reason:
        command.extend(["--pending-reason", args.pending_reason])
    if args.pending_scope:
        command.extend(["--pending-scope", args.pending_scope])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=_build_closeout_env(),
        capture_output=capture_output,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChatgptREST closeout wrapper with doc-obligation checks")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--status", choices=["completed", "partial"], required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--pending-reason", default="")
    parser.add_argument("--pending-scope", default="")
    parser.add_argument("--diff", default="")
    parser.add_argument("--changed-files", nargs="*", default=[])
    parser.add_argument("--skip-doc-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    requested_repo = Path(str(args.repo)).expanduser().resolve()
    if requested_repo != REPO_ROOT:
        print(
            json.dumps(
                {
                    "ok": False,
                    "phase": "argument_validation",
                    "error": f"repo mismatch: expected {REPO_ROOT}, got {requested_repo}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    diff_spec = str(args.diff or "").strip() or _default_diff_spec(args.status)
    checker_payload: dict | None = None
    if not args.skip_doc_check:
        checker_payload = _run_doc_checker(diff_spec=diff_spec, changed_files=list(args.changed_files or []))
        if not checker_payload.get("ok", False):
            if args.json:
                print(json.dumps({"ok": False, "phase": "doc_obligations", "checker": checker_payload}, ensure_ascii=False, indent=2))
            else:
                print(json.dumps({"ok": False, "phase": "doc_obligations", "checker": checker_payload}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1

    proc = _forward_closeout(args, capture_output=bool(args.json))
    rc = int(proc.returncode)
    if args.json:
        closeout_event = None
        if proc.stdout:
            try:
                closeout_event = json.loads(proc.stdout)
            except json.JSONDecodeError:
                closeout_event = {"raw": proc.stdout[:2000]}
        print(
            json.dumps(
                {
                    "ok": rc == 0,
                    "phase": "closeout",
                    "checker": checker_payload,
                    "closeout_event": closeout_event,
                    "diff_spec": diff_spec,
                    "exit_code": rc,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip(), file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
