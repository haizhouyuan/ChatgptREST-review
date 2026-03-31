#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.ops_shared.issue_github_sync import (
    build_issue_title,
    default_repo_slug,
    slugify_issue_title,
    sync_issue_to_github,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "state" / "jobdb.sqlite3"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "dev_loops"


ROLE_ASSIGNMENTS = {
    "controller": {
        "lane": "openclaw main + guardian sidecar",
        "notes": "Use the OpenClaw main lane as controller. Keep guardian as the operational sidecar; do not route work through retired orch topology.",
    },
    "implementer": {
        "lane": "codex_auth_only",
        "notes": "Current best direct implementer lane for code changes and local test execution.",
    },
    "reviewer": {
        "lane": "claudeminmax",
        "notes": "Current best detached reviewer lane for second-pass review before merge.",
    },
    "references": [
        "docs/runbook.md",
        "ops/runner_lane_probe.py",
    ],
}


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_id")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--repo", default=str(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_REPO") or "").strip() or None)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--worktree-root", type=Path, default=REPO_ROOT / ".worktrees")
    parser.add_argument("--base-ref", default="origin/master")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--create-worktree", action="store_true")
    parser.add_argument("--worktree-path", type=Path, default=None)
    parser.add_argument("--run-test-cmd", action="append", default=[])
    parser.add_argument("--service-start-cmd", action="append", default=[])
    parser.add_argument("--health-url", default=None)
    parser.add_argument("--health-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _load_issue(db_path: Path, issue_id: str) -> client_issues.ClientIssueRecord:
    with connect(db_path) as conn:
        issue = client_issues.get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise SystemExit(f"issue not found: {issue_id}")
    return issue


def _branch_name(issue: client_issues.ClientIssueRecord) -> str:
    suffix = slugify_issue_title(build_issue_title(issue), max_len=36)
    return f"codex/devloop-{issue.issue_id[-8:]}-{suffix}"


def _worktree_path(args: argparse.Namespace, issue: client_issues.ClientIssueRecord) -> Path:
    if args.worktree_path is not None:
        return args.worktree_path
    return args.worktree_root / f"devloop-{issue.issue_id[-8:]}"


def _run_shell(cmd: str, *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        shell=True,
        executable="/bin/bash",
        text=True,
        capture_output=True,
        cwd=str(cwd),
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
        "ok": proc.returncode == 0,
    }


def _check_health(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    req = urllib.request.Request(str(url), headers={"User-Agent": "chatgptrest-dev-loop/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= int(resp.status) < 300,
                "status": int(resp.status),
                "body": body,
                "url": str(url),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": int(exc.code),
            "body": exc.read().decode("utf-8", errors="replace"),
            "url": str(url),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "url": str(url),
        }


def _ensure_worktree(
    issue: client_issues.ClientIssueRecord,
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    branch = _branch_name(issue)
    worktree = _worktree_path(args, issue)
    if args.dry_run:
        return {
            "ok": True,
            "created": False,
            "branch": branch,
            "path": str(worktree),
            "dry_run": True,
        }
    if worktree.exists():
        return {
            "ok": True,
            "created": False,
            "branch": branch,
            "path": str(worktree),
            "exists": True,
        }
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree),
            str(args.base_ref),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "created": proc.returncode == 0,
        "branch": branch,
        "path": str(worktree),
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
        "returncode": int(proc.returncode),
    }


def _task_pack(
    issue: client_issues.ClientIssueRecord,
    *,
    github_sync: dict[str, Any] | None,
    branch: str,
    worktree_path: Path | None,
    test_cmds: list[str],
    service_cmds: list[str],
    health_url: str | None,
) -> dict[str, Any]:
    return {
        "generated_at": time.time(),
        "issue": {
            "issue_id": issue.issue_id,
            "title": issue.title,
            "severity": issue.severity,
            "status": issue.status,
            "project": issue.project,
            "source": issue.source,
            "kind": issue.kind,
            "count": issue.count,
            "latest_job_id": issue.latest_job_id,
            "latest_artifacts_path": issue.latest_artifacts_path,
            "latest_conversation_url": issue.latest_conversation_url,
            "symptom": issue.symptom,
            "raw_error": issue.raw_error,
            "tags": list(issue.tags or []),
        },
        "github": github_sync,
        "development": {
            "branch": branch,
            "worktree_path": (str(worktree_path) if worktree_path is not None else None),
            "test_commands": test_cmds,
            "service_start_commands": service_cmds,
            "health_url": health_url,
        },
        "roles": ROLE_ASSIGNMENTS,
    }


def _task_markdown(payload: dict[str, Any]) -> str:
    issue = payload["issue"]
    dev = payload["development"]
    github = payload.get("github") or {}
    lines = [
        f"# Dev Loop Task Pack for {issue['issue_id']}",
        "",
        f"- Title: `{issue['title']}`",
        f"- Severity: `{issue['severity']}`",
        f"- Status: `{issue['status']}`",
        f"- Project: `{issue['project']}`",
        f"- Kind: `{issue['kind'] or 'unknown'}`",
        f"- Branch: `{dev['branch']}`",
    ]
    if dev.get("worktree_path"):
        lines.append(f"- Worktree: `{dev['worktree_path']}`")
    if github.get("github_url"):
        lines.append(f"- GitHub issue: {github['github_url']}")
    lines.extend(
        [
            "",
            "## Role Assignment",
            f"- Controller: `{ROLE_ASSIGNMENTS['controller']['lane']}`",
            f"- Implementer: `{ROLE_ASSIGNMENTS['implementer']['lane']}`",
            f"- Reviewer: `{ROLE_ASSIGNMENTS['reviewer']['lane']}`",
            "",
            "## Symptom",
            issue.get("symptom") or "N/A",
        ]
    )
    if issue.get("raw_error"):
        lines.extend(["", "## Raw Error", "```text", str(issue["raw_error"]), "```"])
    if dev.get("test_commands"):
        lines.extend(["", "## Validation Commands"])
        for cmd in dev["test_commands"]:
            lines.append(f"- `{cmd}`")
    if dev.get("service_start_commands"):
        lines.extend(["", "## Service Start Commands"])
        for cmd in dev["service_start_commands"]:
            lines.append(f"- `{cmd}`")
    if dev.get("health_url"):
        lines.extend(["", "## Health Check", f"- `{dev['health_url']}`"])
    lines.extend(
        [
            "",
            "## References",
            "- `docs/runbook.md`",
            "- `ops/runner_lane_probe.py`",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def run_loop(args: argparse.Namespace) -> dict[str, Any]:
    issue = _load_issue(args.db, args.issue_id)
    github_sync: dict[str, Any] | None = None
    repo = str(args.repo or "").strip() or default_repo_slug(REPO_ROOT)

    with connect(args.db) as conn:
        if not args.skip_github and repo:
            github_sync = sync_issue_to_github(
                conn,
                issue=issue,
                repo=repo,
                dry_run=bool(args.dry_run),
            )
            conn.commit()

    worktree_result: dict[str, Any] | None = None
    worktree_path: Path | None = None
    branch = _branch_name(issue)
    if args.create_worktree:
        worktree_result = _ensure_worktree(issue, args=args)
        if not worktree_result.get("ok"):
            raise SystemExit(f"worktree creation failed: {worktree_result.get('stderr') or worktree_result}")
        worktree_path = Path(str(worktree_result["path"]))
        branch = str(worktree_result["branch"])

    run_dir = args.artifact_root / issue.issue_id / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    payload = _task_pack(
        issue,
        github_sync=github_sync,
        branch=branch,
        worktree_path=worktree_path,
        test_cmds=list(args.run_test_cmd or []),
        service_cmds=list(args.service_start_cmd or []),
        health_url=(str(args.health_url) if args.health_url else None),
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    _json_dump(run_dir / "task.json", payload)
    (run_dir / "README.md").write_text(_task_markdown(payload), encoding="utf-8")

    execution_cwd = worktree_path if worktree_path is not None else REPO_ROOT
    test_runs = [_run_shell(cmd, cwd=execution_cwd) for cmd in list(args.run_test_cmd or [])]
    service_runs = [_run_shell(cmd, cwd=execution_cwd) for cmd in list(args.service_start_cmd or [])]
    health = _check_health(args.health_url, timeout_seconds=args.health_timeout_seconds) if args.health_url else None

    report = {
        "ok": all(run["ok"] for run in [*test_runs, *service_runs]) and (health is None or bool(health.get("ok"))),
        "issue_id": issue.issue_id,
        "artifact_dir": str(run_dir),
        "github_sync": github_sync,
        "worktree": worktree_result,
        "test_runs": test_runs,
        "service_runs": service_runs,
        "health": health,
    }
    _json_dump(run_dir / "report.json", report)
    return report


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    report = run_loop(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
