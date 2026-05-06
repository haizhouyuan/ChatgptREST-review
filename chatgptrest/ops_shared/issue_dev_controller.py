from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.ops_shared.issue_github_sync import (
    build_issue_title,
    default_repo_slug,
    slugify_issue_title,
    sync_issue_to_github,
)

from ops import controller_lane_continuity as continuity


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "state" / "jobdb.sqlite3"
DEFAULT_LANE_DB = REPO_ROOT / "state" / "controller_lanes.sqlite3"
DEFAULT_MANIFEST = REPO_ROOT / "config" / "controller_lanes.json"
DEFAULT_WORKTREE_ROOT = REPO_ROOT / ".worktrees"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "controller_dev_loops"
IMPLEMENTER_SCHEMA_PATH = REPO_ROOT / "ops" / "schemas" / "issue_dev_implementer_output.schema.json"
REVIEWER_SCHEMA_PATH = REPO_ROOT / "ops" / "schemas" / "issue_dev_reviewer_output.schema.json"
WRAPPER_PATH = REPO_ROOT / "ops" / "controller_lane_wrapper.py"

DEFAULT_IMPLEMENTER_LANE = "worker-1"
DEFAULT_REVIEWER_LANE = "verifier"
DEFAULT_CONTROLLER_LANE = "main"
DEFAULT_PR_BASE = "master"
HCOM_MESSAGE_SCHEMA_VERSION = "chatgptrest.issue-dev-controller.hcom.v2"


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return {
        "cmd": list(cmd),
        "returncode": int(proc.returncode),
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
        "ok": proc.returncode == 0,
    }


def _run_shell(cmd: str, *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        shell=True,
        executable="/bin/bash",
        cwd=str(cwd),
        text=True,
        capture_output=True,
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
    req = urllib.request.Request(str(url), headers={"User-Agent": "chatgptrest-issue-dev-controller/1.0"})
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


def _load_issue(db_path: Path, issue_id: str) -> client_issues.ClientIssueRecord:
    with connect(db_path) as conn:
        issue = client_issues.get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise KeyError(f"issue not found: {issue_id}")
    return issue


def _branch_name(issue: client_issues.ClientIssueRecord) -> str:
    suffix = slugify_issue_title(build_issue_title(issue), max_len=36)
    return f"codex/devloop-{issue.issue_id[-8:]}-{suffix}"


def _ensure_worktree(*, repo_root: Path, branch: str, worktree_path: Path, base_ref: str) -> dict[str, Any]:
    if worktree_path.exists():
        return {
            "ok": True,
            "created": False,
            "branch": branch,
            "path": str(worktree_path),
            "exists": True,
        }
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            str(base_ref),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "created": proc.returncode == 0,
        "branch": branch,
        "path": str(worktree_path),
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
        "returncode": int(proc.returncode),
    }


def _git_status_porcelain(worktree_path: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(worktree_path), "status", "--short"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line for line in str(proc.stdout or "").splitlines() if line.strip()]


def _git_head(worktree_path: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return str(proc.stdout or "").strip() if proc.returncode == 0 else ""


def _git_commit_all(worktree_path: Path, message: str) -> dict[str, Any]:
    add = _run_cmd(["git", "-C", str(worktree_path), "add", "-A"], cwd=worktree_path)
    if not add["ok"]:
        return {"ok": False, "stage": "add", "result": add}
    commit = _run_cmd(["git", "-C", str(worktree_path), "commit", "-m", str(message)], cwd=worktree_path)
    return {
        "ok": bool(commit.get("ok")),
        "stage": "commit",
        "result": commit,
        "head": _git_head(worktree_path),
    }


def _git_push_branch(worktree_path: Path, branch: str, *, remote: str = "origin") -> dict[str, Any]:
    push = _run_cmd(
        ["git", "-C", str(worktree_path), "push", "-u", str(remote), str(branch)],
        cwd=worktree_path,
    )
    return {
        "ok": bool(push.get("ok")),
        "result": push,
        "remote": remote,
        "branch": branch,
    }


def _git_head_files(worktree_path: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(worktree_path), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in str(proc.stdout or "").splitlines() if line.strip()]


def _merge_metadata(base: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged.get(key) or {})
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _update_issue_metadata(*, db_path: Path, issue_id: str, patch: dict[str, Any]) -> client_issues.ClientIssueRecord:
    with connect(db_path) as conn:
        issue = client_issues.get_issue(conn, issue_id=issue_id)
        if issue is None:
            raise KeyError(f"issue not found: {issue_id}")
        merged = _merge_metadata(issue.metadata if isinstance(issue.metadata, dict) else {}, patch)
        conn.execute(
            "UPDATE client_issues SET metadata_json = ? WHERE issue_id = ?",
            (json.dumps(merged, ensure_ascii=False, sort_keys=True, separators=(",", ":")), issue_id),
        )
        updated = client_issues.link_issue_evidence(
            conn,
            issue_id=issue_id,
            note="issue dev controller metadata updated",
            metadata={"issue_dev_controller": patch},
        )
        conn.commit()
        return updated


def _relpath_or_abs(path: Path, *, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path.resolve())


def _placeholder_context(values: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in values.items():
        if value is None:
            continue
        text = str(value)
        out[key] = text
        out[f"{key}_q"] = shlex.quote(text)
        out[f"{key}_py"] = repr(text)
    return out


def _render_template(template: str, context: dict[str, str]) -> str:
    try:
        return str(template).format_map(context)
    except KeyError as exc:
        raise KeyError(f"missing template field: {exc.args[0]}") from exc


def _ensure_lane_manifest(*, lane_db_path: Path, manifest_path: Path | None) -> dict[str, Any] | None:
    if manifest_path is None or not manifest_path.exists():
        return None
    return continuity.sync_manifest(db_path=lane_db_path, manifest_path=manifest_path)


def _ensure_lane_exists(*, lane_db_path: Path, lane_id: str, cwd: Path, purpose: str) -> dict[str, Any]:
    try:
        return continuity.lane_status(db_path=lane_db_path, lane_id=lane_id)
    except KeyError:
        return continuity.upsert_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            purpose=purpose,
            lane_kind="codex",
            cwd=str(cwd),
            desired_state="observed",
            run_state="idle",
            session_key=f"lane:{lane_id}",
            stale_after_seconds=900,
            restart_cooldown_seconds=300,
            launch_cmd="",
            resume_cmd="",
        )


def _run_lane_wrapper(
    *,
    lane_db_path: Path,
    lane_id: str,
    cwd: Path,
    summary: str,
    artifact_path: Path,
    task_ref: str,
    role_id: str,
    executor_kind: str,
    rendered_command: str,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(WRAPPER_PATH),
        "--db-path",
        str(lane_db_path),
        "--lane-id",
        str(lane_id),
        "--cwd",
        str(cwd),
        "--summary",
        str(summary),
        "--artifact-path",
        str(artifact_path),
        "--task-ref",
        str(task_ref),
        "--role-id",
        str(role_id),
        "--executor-kind",
        str(executor_kind),
        "--",
        "/bin/bash",
        "-lc",
        rendered_command,
    ]
    return _run_cmd(cmd, cwd=REPO_ROOT)


def _hcom_env(hcom_dir: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if str(hcom_dir or "").strip():
        env["HCOM_DIR"] = str(hcom_dir).strip()
    return env


def _hcom_list_names(*, hcom_dir: str | None) -> dict[str, Any]:
    result = _run_cmd(
        ["hcom", "list", "--names"],
        cwd=REPO_ROOT,
        env=_hcom_env(hcom_dir),
    )
    names = [line.strip() for line in str(result.get("stdout") or "").splitlines() if line.strip()]
    result["names"] = names
    return result


def _hcom_target_available(target: str, names: list[str]) -> bool:
    needle = str(target or "").strip()
    if not needle:
        return False
    if needle.startswith("@"):
        needle = needle[1:]
    if needle.endswith("*"):
        prefix = needle[:-1]
        return bool(prefix) and any(name.startswith(prefix) for name in names)
    return needle in names


def _hcom_output_tmp_path(output_path: Path) -> Path:
    return output_path.with_name(f".{output_path.name}.tmp")


def _build_hcom_task_message(
    *,
    role: str,
    issue_id: str,
    branch: str,
    worktree_path: Path,
    prompt_path: Path,
    output_path: Path,
    schema_path: Path,
    task_readme: Path,
    pr_url: str | None,
) -> str:
    payload = {
        "message_type": "issue_dev_controller_task",
        "schema_version": HCOM_MESSAGE_SCHEMA_VERSION,
        "role": role,
        "issue_id": issue_id,
        "branch": branch,
        "worktree_path": str(worktree_path),
        "task_readme": str(task_readme),
        "prompt_path": str(prompt_path),
        "output_path": str(output_path),
        "output_tmp_path": str(_hcom_output_tmp_path(output_path)),
        "schema_path": str(schema_path),
        "pull_request_url": pr_url,
        "instructions": [
            "Open the prompt file and work only inside the shared worktree.",
            "Write the final JSON result to output_tmp_path first.",
            "Atomically rename output_tmp_path to output_path after the JSON is complete.",
            "Ack back on hcom after the final output_path is visible.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _wait_for_json_output(
    path: Path,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    sleep_seconds = max(0.2, float(poll_seconds))
    tmp_path = _hcom_output_tmp_path(path)
    last_state: dict[str, Any] = {"exists": False, "parsed": False, "tmp_exists": False}
    last_signature: tuple[int, int] | None = None
    while time.time() < deadline:
        last_state["tmp_exists"] = tmp_path.exists()
        if path.exists():
            last_state["exists"] = True
            try:
                stat = path.stat()
                signature = (int(stat.st_size), int(stat.st_mtime_ns))
                last_state["size"] = signature[0]
                last_state["mtime_ns"] = signature[1]
            except OSError:
                signature = None
            if signature is not None and signature == last_signature:
                parsed = _parse_json_file(path)
                if parsed is not None:
                    return {
                        "ok": True,
                        "parsed": parsed,
                        "path": str(path),
                        "tmp_path": str(tmp_path),
                    }
                last_state["parsed"] = False
            last_signature = signature
        time.sleep(sleep_seconds)
    parsed = _parse_json_file(path) if path.exists() else None
    if parsed is not None:
        return {
            "ok": True,
            "parsed": parsed,
            "path": str(path),
            "tmp_path": str(tmp_path),
        }
    return {
        "ok": False,
        "path": str(path),
        "tmp_path": str(tmp_path),
        "timeout_seconds": float(timeout_seconds),
        "last_state": last_state,
    }


def _run_hcom_lane(
    *,
    lane_db_path: Path,
    lane_id: str,
    summary: str,
    artifact_path: Path,
    task_ref: str,
    role: str,
    target: str,
    sender: str,
    hcom_dir: str | None,
    prompt_path: Path,
    output_path: Path,
    schema_path: Path,
    task_readme: Path,
    issue_id: str,
    branch: str,
    worktree_path: Path,
    pr_url: str | None,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    available = _hcom_list_names(hcom_dir=hcom_dir)
    if not available.get("ok"):
        error_text = str(available.get("stderr") or available.get("stdout") or "hcom list failed").strip()
        continuity.report_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            run_state="failed",
            summary=f"{summary} failed",
            artifact_path=str(artifact_path),
            error=error_text,
            checkpoint_pending=False,
            exit_code=int(available.get("returncode") or 1),
        )
        return {
            "ok": False,
            "mode": "hcom",
            "target": target,
            "available": available,
            "send": None,
            "result": None,
            "wait": None,
            "error": error_text,
        }
    names = list(available.get("names") or [])
    if not _hcom_target_available(target, names):
        continuity.report_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            run_state="failed",
            summary=f"{summary} target missing",
            artifact_path=str(artifact_path),
            error=f"hcom target not found: {target}",
            checkpoint_pending=False,
            exit_code=1,
        )
        return {
            "ok": False,
            "mode": "hcom",
            "target": target,
            "available": available,
            "send": None,
            "result": None,
            "wait": None,
            "error": f"hcom target not found: {target}",
        }

    continuity.heartbeat_lane(
        db_path=lane_db_path,
        lane_id=lane_id,
        pid=None,
        run_state="working",
        summary=f"{summary} dispatched to {target}",
    )
    message = _build_hcom_task_message(
        role=role,
        issue_id=issue_id,
        branch=branch,
        worktree_path=worktree_path,
        prompt_path=prompt_path,
        output_path=output_path,
        schema_path=schema_path,
        task_readme=task_readme,
        pr_url=pr_url,
    )
    send = _run_cmd(
        [
            "hcom",
            "send",
            "--from",
            sender,
            str(target),
            "--intent",
            "request",
            "--thread",
            str(task_ref),
            "--",
            message,
        ],
        cwd=REPO_ROOT,
        env=_hcom_env(hcom_dir),
    )
    if not send.get("ok"):
        continuity.report_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            run_state="failed",
            summary=f"{summary} send failed",
            artifact_path=str(artifact_path),
            error=str(send.get("stderr") or send.get("stdout") or "hcom send failed"),
            checkpoint_pending=False,
            exit_code=int(send.get("returncode") or 1),
        )
        return {
            "ok": False,
            "mode": "hcom",
            "target": target,
            "available": available,
            "send": send,
            "result": None,
            "wait": None,
        }

    waited = _wait_for_json_output(
        output_path,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    if waited.get("ok"):
        continuity.report_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            run_state="completed",
            summary=f"{summary} completed via {target}",
            artifact_path=str(artifact_path),
            error="",
            checkpoint_pending=False,
            exit_code=0,
        )
    else:
        continuity.report_lane(
            db_path=lane_db_path,
            lane_id=lane_id,
            run_state="failed",
            summary=f"{summary} timed out",
            artifact_path=str(artifact_path),
            error=f"hcom output not produced within {timeout_seconds}s",
            checkpoint_pending=False,
            exit_code=124,
        )
    return {
        "ok": bool(waited.get("ok")),
        "mode": "hcom",
        "target": target,
        "available": available,
        "send": send,
        "result": waited.get("parsed"),
        "wait": waited,
        "message": message,
    }


class GhCliPullRequestClient:
    def _run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gh", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
        )

    def ensure_pull_request(
        self,
        *,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body_path: Path,
        cwd: Path,
    ) -> dict[str, Any]:
        listed = self._run(
            [
                "pr",
                "list",
                "--repo",
                repo,
                "--head",
                head_branch,
                "--base",
                base_branch,
                "--state",
                "open",
                "--json",
                "number,url,state,title,headRefName,baseRefName",
            ],
            cwd=cwd,
        )
        if listed.returncode == 0:
            try:
                rows = json.loads(str(listed.stdout or "[]"))
            except Exception:
                rows = []
            if isinstance(rows, list) and rows:
                row = rows[0]
                return {
                    "ok": True,
                    "created": False,
                    "number": int(row.get("number") or 0),
                    "url": str(row.get("url") or ""),
                    "state": str(row.get("state") or "OPEN"),
                    "title": str(row.get("title") or ""),
                    "head": str(row.get("headRefName") or head_branch),
                    "base": str(row.get("baseRefName") or base_branch),
                }
        created = self._run(
            [
                "pr",
                "create",
                "--repo",
                repo,
                "--base",
                base_branch,
                "--head",
                head_branch,
                "--title",
                title,
                "--body-file",
                str(body_path),
            ],
            cwd=cwd,
        )
        if created.returncode != 0:
            return {
                "ok": False,
                "created": False,
                "stderr": str(created.stderr or ""),
                "stdout": str(created.stdout or ""),
            }
        view = self._run(
            [
                "pr",
                "view",
                "--repo",
                repo,
                head_branch,
                "--json",
                "number,url,state,title,headRefName,baseRefName",
            ],
            cwd=cwd,
        )
        if view.returncode != 0:
            return {
                "ok": False,
                "created": True,
                "stderr": str(view.stderr or ""),
                "stdout": str(view.stdout or ""),
            }
        row = json.loads(str(view.stdout or "{}"))
        return {
            "ok": True,
            "created": True,
            "number": int(row.get("number") or 0),
            "url": str(row.get("url") or ""),
            "state": str(row.get("state") or "OPEN"),
            "title": str(row.get("title") or ""),
            "head": str(row.get("headRefName") or head_branch),
            "base": str(row.get("baseRefName") or base_branch),
        }

    def merge_pull_request(
        self,
        *,
        repo: str,
        number: int,
        method: str,
        cwd: Path,
    ) -> dict[str, Any]:
        flag = "--merge"
        if method == "squash":
            flag = "--squash"
        if method == "rebase":
            flag = "--rebase"
        proc = self._run(
            [
                "pr",
                "merge",
                "--repo",
                repo,
                str(int(number)),
                flag,
                "--delete-branch=false",
            ],
            cwd=cwd,
        )
        return {
            "ok": proc.returncode == 0,
            "number": int(number),
            "method": method,
            "stdout": str(proc.stdout or ""),
            "stderr": str(proc.stderr or ""),
        }


GitHubPrClient = Any


@dataclass
class ControllerLoopConfig:
    issue_id: str
    db_path: Path = DEFAULT_DB
    lane_db_path: Path = DEFAULT_LANE_DB
    repo_root: Path = REPO_ROOT
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT
    worktree_root: Path = DEFAULT_WORKTREE_ROOT
    manifest_path: Path | None = DEFAULT_MANIFEST
    repo_slug: str | None = None
    base_ref: str = "origin/master"
    pr_base: str = DEFAULT_PR_BASE
    create_worktree: bool = True
    skip_github_issue_sync: bool = False
    implementer_lane: str = DEFAULT_IMPLEMENTER_LANE
    reviewer_lane: str = DEFAULT_REVIEWER_LANE
    controller_lane: str = DEFAULT_CONTROLLER_LANE
    implementer_command_template: str = ""
    reviewer_command_template: str = ""
    implementer_hcom_target: str = ""
    reviewer_hcom_target: str = ""
    hcom_dir: str | None = None
    hcom_sender: str = "issue-dev-controller"
    hcom_poll_seconds: float = 2.0
    implementer_timeout_seconds: float = 1800.0
    reviewer_timeout_seconds: float = 1800.0
    validation_commands: list[str] = field(default_factory=list)
    service_start_commands: list[str] = field(default_factory=list)
    health_url: str | None = None
    health_timeout_seconds: float = 10.0
    auto_commit: bool = True
    push_branch: bool = True
    create_pr: bool = True
    merge_pr: bool = False
    merge_method: str = "merge"
    close_issue_status: str | None = None
    role_id: str = "devops"
    commit_message: str = ""


def _task_markdown(payload: dict[str, Any]) -> str:
    issue = payload["issue"]
    dev = payload["development"]
    gh_issue = payload.get("github_issue") or {}
    lines = [
        f"# Controller Dev Loop for {issue['issue_id']}",
        "",
        f"- Title: `{issue['title']}`",
        f"- Severity: `{issue['severity']}`",
        f"- Status: `{issue['status']}`",
        f"- Branch: `{dev['branch']}`",
        f"- Worktree: `{dev['worktree_path']}`",
        f"- Implementer lane: `{dev['implementer_lane']}`",
        f"- Reviewer lane: `{dev['reviewer_lane']}`",
    ]
    if dev.get("implementer_hcom_target"):
        lines.append(f"- Implementer hcom target: `{dev['implementer_hcom_target']}`")
    if dev.get("reviewer_hcom_target"):
        lines.append(f"- Reviewer hcom target: `{dev['reviewer_hcom_target']}`")
    if gh_issue.get("github_url"):
        lines.append(f"- GitHub issue: {gh_issue['github_url']}")
    lines.extend(
        [
            "",
            "## Symptom",
            issue.get("symptom") or "N/A",
        ]
    )
    if issue.get("raw_error"):
        lines.extend(["", "## Raw Error", "```text", str(issue["raw_error"]), "```"])
    if dev.get("validation_commands"):
        lines.extend(["", "## Validation Commands"])
        lines.extend([f"- `{cmd}`" for cmd in dev["validation_commands"]])
    if dev.get("service_start_commands"):
        lines.extend(["", "## Service Commands"])
        lines.extend([f"- `{cmd}`" for cmd in dev["service_start_commands"]])
    if dev.get("health_url"):
        lines.extend(["", "## Health URL", f"- `{dev['health_url']}`"])
    return "\n".join(lines).strip() + "\n"


def _default_commit_message(issue: client_issues.ClientIssueRecord) -> str:
    return f"fix: resolve {issue.issue_id} {slugify_issue_title(issue.title, max_len=40)}"


def _implementer_prompt(
    *,
    issue: client_issues.ClientIssueRecord,
    worktree_path: Path,
    branch: str,
    task_readme: Path,
    output_path: Path,
    schema_path: Path,
) -> str:
    return (
        f"# Implementer Task\n\n"
        f"- Issue ID: `{issue.issue_id}`\n"
        f"- Branch: `{branch}`\n"
        f"- Worktree: `{worktree_path}`\n"
        f"- Task pack: `{task_readme}`\n"
        f"- Output JSON path: `{output_path}`\n"
        f"- Output schema: `{schema_path}`\n\n"
        "You are the implementer lane. Work only inside the provided worktree.\n"
        "Make the required code changes, run relevant validation, and do not push or merge.\n"
        "Return a JSON object that matches the schema. Include changed_files and tests_ran.\n\n"
        f"## Issue\n{issue.title}\n\n"
        f"## Symptom\n{issue.symptom or 'N/A'}\n\n"
        f"## Raw Error\n{issue.raw_error or 'N/A'}\n"
    )


def _reviewer_prompt(
    *,
    issue: client_issues.ClientIssueRecord,
    worktree_path: Path,
    branch: str,
    task_readme: Path,
    output_path: Path,
    schema_path: Path,
    pr_url: str | None,
) -> str:
    lines = [
        "# Reviewer Task",
        "",
        f"- Issue ID: `{issue.issue_id}`",
        f"- Branch: `{branch}`",
        f"- Worktree: `{worktree_path}`",
        f"- Task pack: `{task_readme}`",
        f"- Output JSON path: `{output_path}`",
        f"- Output schema: `{schema_path}`",
    ]
    if pr_url:
        lines.append(f"- Pull request: {pr_url}")
    lines.extend(
        [
            "",
            "You are the detached reviewer lane.",
            "Review the current branch/worktree state and return a JSON object matching the schema.",
            "Set decision to approve only if the change is ready to merge.",
            "",
            f"## Issue\n{issue.title}",
            "",
            f"## Symptom\n{issue.symptom or 'N/A'}",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def run_controller_loop(
    cfg: ControllerLoopConfig,
    *,
    github_client: GitHubPrClient | None = None,
) -> dict[str, Any]:
    repo_root = Path(cfg.repo_root).resolve()
    db_path = Path(cfg.db_path).resolve()
    lane_db_path = Path(cfg.lane_db_path).resolve()
    artifact_root = Path(cfg.artifact_root).resolve()
    worktree_root = Path(cfg.worktree_root).resolve()
    manifest_path = Path(cfg.manifest_path).resolve() if cfg.manifest_path is not None else None
    repo_slug = str(cfg.repo_slug or "").strip() or default_repo_slug(repo_root)
    gh = github_client or GhCliPullRequestClient()

    issue = _load_issue(db_path, cfg.issue_id)
    branch = _branch_name(issue)
    worktree_path = worktree_root / f"devloop-{issue.issue_id[-8:]}"
    run_dir = artifact_root / issue.issue_id / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir.mkdir(parents=True, exist_ok=True)

    github_issue: dict[str, Any] | None = None
    if not cfg.skip_github_issue_sync and repo_slug:
        with connect(db_path) as conn:
            github_issue = sync_issue_to_github(conn, issue=issue, repo=repo_slug, dry_run=False)
            conn.commit()

    worktree_result: dict[str, Any] | None = None
    if cfg.create_worktree:
        worktree_result = _ensure_worktree(
            repo_root=repo_root,
            branch=branch,
            worktree_path=worktree_path,
            base_ref=cfg.base_ref,
        )
        if not worktree_result.get("ok"):
            raise RuntimeError(f"worktree creation failed: {worktree_result}")
    else:
        worktree_path = repo_root
        worktree_result = {
            "ok": True,
            "created": False,
            "branch": branch,
            "path": str(worktree_path),
            "exists": True,
        }

    task_json = run_dir / "task.json"
    task_readme = run_dir / "README.md"
    implementer_output = run_dir / "implementer_result.json"
    reviewer_output = run_dir / "reviewer_result.json"
    implementer_prompt = run_dir / "implementer_prompt.md"
    reviewer_prompt = run_dir / "reviewer_prompt.md"
    pr_body_path = run_dir / "pull_request_body.md"

    task_payload = {
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
        "github_issue": github_issue,
        "development": {
            "branch": branch,
            "worktree_path": str(worktree_path),
            "implementer_lane": cfg.implementer_lane,
            "reviewer_lane": cfg.reviewer_lane,
            "implementer_hcom_target": (str(cfg.implementer_hcom_target or "").strip() or None),
            "reviewer_hcom_target": (str(cfg.reviewer_hcom_target or "").strip() or None),
            "hcom_dir": (str(cfg.hcom_dir or "").strip() or None),
            "hcom_sender": str(cfg.hcom_sender),
            "hcom_poll_seconds": float(cfg.hcom_poll_seconds),
            "implementer_timeout_seconds": float(cfg.implementer_timeout_seconds),
            "reviewer_timeout_seconds": float(cfg.reviewer_timeout_seconds),
            "validation_commands": list(cfg.validation_commands or []),
            "service_start_commands": list(cfg.service_start_commands or []),
            "health_url": cfg.health_url,
            "implementer_schema": str(IMPLEMENTER_SCHEMA_PATH),
            "reviewer_schema": str(REVIEWER_SCHEMA_PATH),
            "implementer_prompt_path": str(implementer_prompt),
            "reviewer_prompt_path": str(reviewer_prompt),
            "implementer_output_path": str(implementer_output),
            "reviewer_output_path": str(reviewer_output),
        },
    }
    _json_dump(task_json, task_payload)
    task_readme.write_text(_task_markdown(task_payload), encoding="utf-8")
    implementer_prompt.write_text(
        _implementer_prompt(
            issue=issue,
            worktree_path=worktree_path,
            branch=branch,
            task_readme=task_readme,
            output_path=implementer_output,
            schema_path=IMPLEMENTER_SCHEMA_PATH,
        ),
        encoding="utf-8",
    )

    manifest_sync = _ensure_lane_manifest(lane_db_path=lane_db_path, manifest_path=manifest_path)
    _ensure_lane_exists(lane_db_path=lane_db_path, lane_id=cfg.controller_lane, cwd=repo_root, purpose="controller")
    _ensure_lane_exists(lane_db_path=lane_db_path, lane_id=cfg.implementer_lane, cwd=worktree_path, purpose="implementer")
    _ensure_lane_exists(lane_db_path=lane_db_path, lane_id=cfg.reviewer_lane, cwd=worktree_path, purpose="reviewer")

    placeholder_context = _placeholder_context(
        {
            "python_executable": sys.executable,
            "issue_id": issue.issue_id,
            "issue_title": issue.title,
            "branch": branch,
            "repo_root": str(repo_root),
            "worktree_path": str(worktree_path),
            "task_json": str(task_json),
            "task_readme": str(task_readme),
            "run_dir": str(run_dir),
            "implementer_prompt": str(implementer_prompt),
            "implementer_output": str(implementer_output),
            "implementer_schema": str(IMPLEMENTER_SCHEMA_PATH),
            "reviewer_prompt": str(reviewer_prompt),
            "reviewer_output": str(reviewer_output),
            "reviewer_schema": str(REVIEWER_SCHEMA_PATH),
            "pr_body_path": str(pr_body_path),
            "repo_slug": (repo_slug or ""),
            "github_issue_url": ((github_issue or {}).get("github_url") or ""),
        }
    )

    implementer_command = ""
    implementer_exec: dict[str, Any]
    if str(cfg.implementer_command_template or "").strip():
        implementer_command = _render_template(cfg.implementer_command_template, placeholder_context)
        implementer_exec = _run_lane_wrapper(
            lane_db_path=lane_db_path,
            lane_id=cfg.implementer_lane,
            cwd=worktree_path,
            summary=f"{issue.issue_id} implementer",
            artifact_path=implementer_output,
            task_ref=issue.issue_id,
            role_id=cfg.role_id,
            executor_kind="implementer",
            rendered_command=implementer_command,
        )
    elif str(cfg.implementer_hcom_target or "").strip():
        implementer_exec = _run_hcom_lane(
            lane_db_path=lane_db_path,
            lane_id=cfg.implementer_lane,
            summary=f"{issue.issue_id} implementer",
            artifact_path=implementer_output,
            task_ref=issue.issue_id,
            role="implementer",
            target=str(cfg.implementer_hcom_target),
            sender=str(cfg.hcom_sender),
            hcom_dir=cfg.hcom_dir,
            prompt_path=implementer_prompt,
            output_path=implementer_output,
            schema_path=IMPLEMENTER_SCHEMA_PATH,
            task_readme=task_readme,
            issue_id=issue.issue_id,
            branch=branch,
            worktree_path=worktree_path,
            pr_url=None,
            timeout_seconds=float(cfg.implementer_timeout_seconds),
            poll_seconds=float(cfg.hcom_poll_seconds),
        )
    else:
        raise ValueError("implementer_command_template or implementer_hcom_target is required")
    implementer_result = (
        implementer_exec.get("result")
        if isinstance(implementer_exec.get("result"), dict)
        else _parse_json_file(implementer_output)
    )

    validation_runs = [_run_shell(cmd, cwd=worktree_path) for cmd in list(cfg.validation_commands or [])]

    dirty_before_commit = _git_status_porcelain(worktree_path)
    git_commit = None
    if dirty_before_commit and cfg.auto_commit:
        git_commit = _git_commit_all(
            worktree_path,
            str(cfg.commit_message or "").strip() or _default_commit_message(issue),
        )
    git_push = None
    if cfg.push_branch and (git_commit or not dirty_before_commit):
        git_push = _git_push_branch(worktree_path, branch)

    pr_title = build_issue_title(issue)
    pr_body_lines = [
        f"Resolves issue ledger `{issue.issue_id}`.",
        "",
        "## Source",
        f"- Issue: {(github_issue or {}).get('github_url') or 'n/a'}",
        f"- Task pack: `{task_readme}`",
        "",
        "## Validation",
    ]
    if validation_runs:
        pr_body_lines.extend([f"- `{run['cmd']}` -> rc={run['returncode']}" for run in validation_runs])
    else:
        pr_body_lines.append("- no controller-run validation commands")
    pr_body_path.write_text("\n".join(pr_body_lines).strip() + "\n", encoding="utf-8")

    pr_result = None
    if cfg.create_pr and repo_slug:
        pr_result = gh.ensure_pull_request(
            repo=repo_slug,
            head_branch=branch,
            base_branch=cfg.pr_base,
            title=pr_title,
            body_path=pr_body_path,
            cwd=worktree_path,
        )

    reviewer_result = None
    reviewer_exec = None
    reviewer_command = ""
    if str(cfg.reviewer_command_template or "").strip() or str(cfg.reviewer_hcom_target or "").strip():
        reviewer_prompt.write_text(
            _reviewer_prompt(
                issue=issue,
                worktree_path=worktree_path,
                branch=branch,
                task_readme=task_readme,
                output_path=reviewer_output,
                schema_path=REVIEWER_SCHEMA_PATH,
                pr_url=(pr_result or {}).get("url"),
            ),
            encoding="utf-8",
        )
        reviewer_context = dict(placeholder_context)
        reviewer_context["pull_request_url"] = str((pr_result or {}).get("url") or "")
        reviewer_context["pull_request_url_q"] = shlex.quote(reviewer_context["pull_request_url"])
        reviewer_context["pull_request_url_py"] = repr(reviewer_context["pull_request_url"])
        if str(cfg.reviewer_command_template or "").strip():
            reviewer_command = _render_template(cfg.reviewer_command_template, reviewer_context)
            reviewer_exec = _run_lane_wrapper(
                lane_db_path=lane_db_path,
                lane_id=cfg.reviewer_lane,
                cwd=worktree_path,
                summary=f"{issue.issue_id} reviewer",
                artifact_path=reviewer_output,
                task_ref=issue.issue_id,
                role_id=cfg.role_id,
                executor_kind="reviewer",
                rendered_command=reviewer_command,
            )
        elif str(cfg.reviewer_hcom_target or "").strip():
            reviewer_exec = _run_hcom_lane(
                lane_db_path=lane_db_path,
                lane_id=cfg.reviewer_lane,
                summary=f"{issue.issue_id} reviewer",
                artifact_path=reviewer_output,
                task_ref=issue.issue_id,
                role="reviewer",
                target=str(cfg.reviewer_hcom_target),
                sender=str(cfg.hcom_sender),
                hcom_dir=cfg.hcom_dir,
                prompt_path=reviewer_prompt,
                output_path=reviewer_output,
                schema_path=REVIEWER_SCHEMA_PATH,
                task_readme=task_readme,
                issue_id=issue.issue_id,
                branch=branch,
                worktree_path=worktree_path,
                pr_url=(pr_result or {}).get("url"),
                timeout_seconds=float(cfg.reviewer_timeout_seconds),
                poll_seconds=float(cfg.hcom_poll_seconds),
            )
        reviewer_result = (
            reviewer_exec.get("result")
            if isinstance((reviewer_exec or {}).get("result"), dict)
            else _parse_json_file(reviewer_output)
        )

    merge_result = None
    reviewer_approved = bool(reviewer_result and str(reviewer_result.get("decision") or "").strip().lower() == "approve")
    if cfg.merge_pr:
        if pr_result is None or not pr_result.get("ok"):
            raise RuntimeError("merge_pr requires a valid pull request")
        if reviewer_result is None or not reviewer_approved:
            raise RuntimeError("merge_pr requires reviewer approval")
        merge_result = gh.merge_pull_request(
            repo=repo_slug or "",
            number=int(pr_result["number"]),
            method=cfg.merge_method,
            cwd=worktree_path,
        )

    reviewer_ok = reviewer_exec is None or (
        reviewer_result is not None and bool(reviewer_exec.get("ok"))
    )
    service_runs = [_run_shell(cmd, cwd=repo_root) for cmd in list(cfg.service_start_commands or [])]
    health = _check_health(cfg.health_url, timeout_seconds=cfg.health_timeout_seconds) if cfg.health_url else None

    report = {
        "ok": bool(implementer_exec.get("ok"))
        and implementer_result is not None
        and all(run["ok"] for run in validation_runs)
        and reviewer_ok
        and (not cfg.merge_pr or bool(merge_result and merge_result.get("ok")))
        and all(run["ok"] for run in service_runs)
        and (health is None or bool(health.get("ok"))),
        "issue_id": issue.issue_id,
        "artifact_dir": str(run_dir),
        "github_issue": github_issue,
        "worktree": worktree_result,
        "lane_manifest_sync": manifest_sync,
        "implementer": {
            "command": implementer_command,
            "execution": implementer_exec,
            "result": implementer_result,
        },
        "validation_runs": validation_runs,
        "git": {
            "dirty_before_commit": dirty_before_commit,
            "commit": git_commit,
            "push": git_push,
            "head": _git_head(worktree_path),
            "head_files": _git_head_files(worktree_path),
        },
        "pull_request": pr_result,
        "reviewer": {
            "command": reviewer_command,
            "execution": reviewer_exec,
            "result": reviewer_result,
            "approved": reviewer_approved,
        },
        "merge": merge_result,
        "service_runs": service_runs,
        "health": health,
    }
    report_path = run_dir / "report.json"
    _json_dump(report_path, report)

    issue_metadata_patch = {
        "dev_loop": {
            "artifact_dir": str(run_dir),
            "artifact_report_path": _relpath_or_abs(report_path, repo_root=repo_root),
            "branch": branch,
            "worktree_path": str(worktree_path),
            "pull_request": (
                {
                    "number": (pr_result or {}).get("number"),
                    "url": (pr_result or {}).get("url"),
                    "state": (pr_result or {}).get("state"),
                }
                if pr_result
                else None
            ),
        }
    }
    _update_issue_metadata(db_path=db_path, issue_id=issue.issue_id, patch=issue_metadata_patch)
    with connect(db_path) as conn:
        client_issues.link_issue_evidence(
            conn,
            issue_id=issue.issue_id,
            artifacts_path=_relpath_or_abs(report_path, repo_root=repo_root),
            note="issue dev controller report",
            source="issue_dev_controller",
            metadata={"ok": bool(report.get("ok")), "branch": branch, "pull_request": pr_result},
        )
        if report["ok"] and health and health.get("ok"):
            client_issues.record_issue_verification(
                conn,
                issue_id=issue.issue_id,
                verification_type="controller_health",
                status="passed",
                verifier="issue_dev_controller",
                note="controller lane service health verified",
                artifacts_path=_relpath_or_abs(report_path, repo_root=repo_root),
                metadata={"health_url": cfg.health_url, "pull_request": pr_result},
            )
        if report["ok"] and cfg.close_issue_status:
            client_issues.update_issue_status(
                conn,
                issue_id=issue.issue_id,
                status=cfg.close_issue_status,
                note=f"issue dev controller completed branch={branch}",
                actor="issue_dev_controller",
                metadata={
                    "verification": {
                        "type": "controller_health",
                        "status": "passed" if (health or {}).get("ok") else "unknown",
                        "verifier": "issue_dev_controller",
                        "note": "controller lane service health verified",
                        "artifacts_path": _relpath_or_abs(report_path, repo_root=repo_root),
                        "metadata": {
                            "pull_request": pr_result,
                            "merge": merge_result,
                            "health": health,
                        },
                    }
                },
            )
        conn.commit()

    return report
