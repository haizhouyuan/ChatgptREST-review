from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from chatgptrest.core import client_issues


GitHubApi = Callable[[Sequence[str]], dict[str, Any]]

_PREFIX_RE = re.compile(r"^\[(P[0-3])\]\s+", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _gh_api_json(args: Sequence[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["gh", "api", *list(args)],
        text=True,
        capture_output=True,
        check=True,
    )
    raw = str(proc.stdout or "").strip()
    if not raw:
        return {}
    obj = json.loads(raw)
    return obj if isinstance(obj, dict) else {}


def default_repo_slug(repo_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
        text=True,
        capture_output=True,
        check=False,
    )
    raw = str(proc.stdout or "").strip()
    if not raw:
        return None
    url = raw.removesuffix(".git")
    if url.startswith("git@github.com:"):
        return url.split("git@github.com:", 1)[1]
    if "github.com/" in url:
        return url.split("github.com/", 1)[1]
    return None


def build_issue_title(issue: client_issues.ClientIssueRecord) -> str:
    title = str(issue.title or "").strip()
    severity = str(issue.severity or "P2").upper()
    if _PREFIX_RE.match(title):
        return title
    return f"[{severity}] {title}"


def _domain_label(issue: client_issues.ClientIssueRecord) -> str:
    haystack = " ".join(
        [
            str(issue.kind or ""),
            str(issue.source or ""),
            str(issue.title or ""),
            str(issue.symptom or ""),
            str(issue.raw_error or ""),
        ]
    ).lower()
    if "mcp" in haystack:
        return "domain/mcp"
    if "gemini" in haystack:
        return "domain/gemini"
    if any(token in haystack for token in ("openclaw", "guardian", "maintagent", "lane", "agent")):
        return "domain/openclaw"
    if "telemetry" in haystack:
        return "domain/telemetry"
    if "evomap" in haystack or "knowledge" in haystack:
        return "domain/evomap"
    return "domain/runtime"


def _track_label(issue: client_issues.ClientIssueRecord, *, domain_label: str) -> str:
    severity = str(issue.severity or "P2").upper()
    if domain_label == "domain/evomap":
        return "track/learning-loop"
    if severity == "P0":
        return "track/launch-hardening"
    if domain_label == "domain/openclaw" and any(
        token in " ".join([str(issue.title or ""), str(issue.symptom or "")]).lower()
        for token in ("topology", "mode", "maintagent", "guardian")
    ):
        return "track/openclaw-topology"
    return "track/runtime-reliability"


def derive_labels(issue: client_issues.ClientIssueRecord) -> list[str]:
    severity = str(issue.severity or "P2").upper()
    domain = _domain_label(issue)
    track = _track_label(issue, domain_label=domain)
    labels = [
        severity,
        "bug",
        domain,
        track,
        "status/triage",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def build_issue_body(issue: client_issues.ClientIssueRecord) -> str:
    lines = [
        "<!-- chatgptrest-issue-ledger -->",
        f"Authoritative Issue Ledger ID: `{issue.issue_id}`",
        "",
        "This GitHub issue was auto-created from the ChatgptREST Issue Ledger.",
        "The Issue Ledger remains the authoritative incident state; GitHub is the coordination and review anchor.",
        "",
        "## Ledger Snapshot",
        f"- Project: `{issue.project}`",
        f"- Severity: `{issue.severity}`",
        f"- Status: `{issue.status}`",
        f"- Source: `{issue.source or 'unknown'}`",
        f"- Kind: `{issue.kind or 'unknown'}`",
        f"- Occurrences: `{int(issue.count)}`",
    ]
    if issue.tags:
        lines.append(f"- Tags: `{', '.join(issue.tags)}`")
    if issue.latest_job_id:
        lines.append(f"- Latest job: `{issue.latest_job_id}`")
    if issue.latest_conversation_url:
        lines.append(f"- Latest conversation: {issue.latest_conversation_url}")
    if issue.latest_artifacts_path:
        lines.append(f"- Latest artifacts: `{issue.latest_artifacts_path}`")
    if issue.symptom:
        lines.extend(["", "## Symptom", issue.symptom])
    if issue.raw_error:
        excerpt = str(issue.raw_error)
        if len(excerpt) > 4000:
            excerpt = excerpt[:4000] + "..."
        lines.extend(["", "## Raw Error Excerpt", "```text", excerpt, "```"])
    return "\n".join(lines).strip() + "\n"


def build_status_comment(
    issue: client_issues.ClientIssueRecord,
    *,
    previous_status: str | None,
) -> str:
    prev = previous_status or "unknown"
    lines = [
        "Issue Ledger status sync:",
        f"- ledger issue: `{issue.issue_id}`",
        f"- status: `{prev}` -> `{issue.status}`",
        f"- occurrences: `{int(issue.count)}`",
    ]
    if issue.latest_job_id:
        lines.append(f"- latest job: `{issue.latest_job_id}`")
    if issue.latest_artifacts_path:
        lines.append(f"- latest artifacts: `{issue.latest_artifacts_path}`")
    lines.append("")
    lines.append("Authoritative state remains in the ChatgptREST Issue Ledger.")
    return "\n".join(lines).strip() + "\n"


def _merge_metadata(
    base: dict[str, Any] | None,
    patch: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged.get(key) or {})
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _store_issue_metadata(
    conn: Any,
    *,
    issue: client_issues.ClientIssueRecord,
    patch: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    now: float | None = None,
) -> client_issues.ClientIssueRecord:
    merged = _merge_metadata(issue.metadata if isinstance(issue.metadata, dict) else {}, patch)
    conn.execute(
        "UPDATE client_issues SET metadata_json = ? WHERE issue_id = ?",
        (_json_dumps(merged), issue.issue_id),
    )
    client_issues._insert_issue_event(  # type: ignore[attr-defined]
        conn,
        issue_id=issue.issue_id,
        event_type=event_type,
        payload=payload,
        now=(time.time() if now is None else now),
    )
    updated = client_issues.get_issue(conn, issue_id=issue.issue_id)
    assert updated is not None
    return updated


def _github_meta(issue: client_issues.ClientIssueRecord) -> dict[str, Any]:
    md = issue.metadata if isinstance(issue.metadata, dict) else {}
    obj = md.get("github_issue")
    return dict(obj) if isinstance(obj, dict) else {}


def _github_number(meta: dict[str, Any]) -> int | None:
    raw = meta.get("number")
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def sync_issue_to_github(
    conn: Any,
    *,
    issue: client_issues.ClientIssueRecord,
    repo: str,
    gh_api: GitHubApi | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    gh = gh_api or _gh_api_json
    meta = _github_meta(issue)
    issue_number = _github_number(meta)
    synced_status = str(meta.get("synced_status") or "").strip().lower() or None
    gh_state = str(meta.get("state") or "").strip().lower() or None
    labels = derive_labels(issue)
    title = build_issue_title(issue)

    if issue_number is None:
        if issue.status == client_issues.CLIENT_ISSUE_STATUS_CLOSED:
            return {
                "issue_id": issue.issue_id,
                "action": "skipped_closed_without_anchor",
                "repo": repo,
                "dry_run": dry_run,
            }
        body = build_issue_body(issue)
        if dry_run:
            return {
                "issue_id": issue.issue_id,
                "action": "dry_run_create",
                "repo": repo,
                "github_number": 0,
                "github_url": f"https://github.com/{repo}/issues/dry-run",
                "status": issue.status,
                "labels": labels,
                "title": title,
                "dry_run": True,
            }
        payload = gh(
            [
                "--method",
                "POST",
                f"repos/{repo}/issues",
                "-f",
                f"title={title}",
                "-f",
                f"body={body}",
                *sum([["-f", f"labels[]={label}"] for label in labels], []),
            ]
        )
        patch = {
            "github_issue": {
                "repo": repo,
                "number": int(payload.get("number") or 0),
                "url": str(payload.get("html_url") or payload.get("url") or ""),
                "state": str(payload.get("state") or "open"),
                "synced_status": issue.status,
                "synced_at": time.time(),
                "labels": labels,
                "title": title,
            }
        }
        updated = _store_issue_metadata(
            conn,
            issue=issue,
            patch=patch,
            event_type="issue_github_synced",
            payload={
                "action": "created",
                "repo": repo,
                "number": patch["github_issue"]["number"],
                "url": patch["github_issue"]["url"],
                "labels": labels,
                "dry_run": dry_run,
            },
        )
        return {
            "issue_id": issue.issue_id,
            "action": "created",
            "repo": repo,
            "github_number": patch["github_issue"]["number"],
            "github_url": patch["github_issue"]["url"],
            "status": updated.status,
            "dry_run": False,
        }

    actions: list[str] = []
    if issue.status != synced_status:
        comment = build_status_comment(issue, previous_status=synced_status)
        if issue.status == client_issues.CLIENT_ISSUE_STATUS_CLOSED:
            if dry_run:
                return {
                    "issue_id": issue.issue_id,
                    "action": "dry_run_commented,closed",
                    "repo": repo,
                    "github_number": issue_number,
                    "github_url": str(meta.get("url") or f"https://github.com/{repo}/issues/{issue_number}"),
                    "status": issue.status,
                    "dry_run": True,
                }
            gh(
                [
                    "--method",
                    "POST",
                    f"repos/{repo}/issues/{issue_number}/comments",
                    "-f",
                    f"body={comment}",
                ]
            )
            gh(
                [
                    "--method",
                    "PATCH",
                    f"repos/{repo}/issues/{issue_number}",
                    "-f",
                    "state=closed",
                ]
            )
            actions.extend(["commented", "closed"])
            gh_state = "closed"
        else:
            if dry_run:
                action = "dry_run_reopened,commented" if gh_state == "closed" else "dry_run_commented"
                return {
                    "issue_id": issue.issue_id,
                    "action": action,
                    "repo": repo,
                    "github_number": issue_number,
                    "github_url": str(meta.get("url") or f"https://github.com/{repo}/issues/{issue_number}"),
                    "status": issue.status,
                    "dry_run": True,
                }
            if gh_state == "closed":
                gh(
                    [
                        "--method",
                        "PATCH",
                        f"repos/{repo}/issues/{issue_number}",
                        "-f",
                        "state=open",
                    ]
                )
                actions.append("reopened")
                gh_state = "open"
            gh(
                [
                    "--method",
                    "POST",
                    f"repos/{repo}/issues/{issue_number}/comments",
                    "-f",
                    f"body={comment}",
                ]
            )
            actions.append("commented")

    patch = {
        "github_issue": {
            "repo": repo,
            "number": issue_number,
            "url": str(meta.get("url") or f"https://github.com/{repo}/issues/{issue_number}"),
            "state": gh_state or ("closed" if issue.status == client_issues.CLIENT_ISSUE_STATUS_CLOSED else "open"),
            "synced_status": issue.status,
            "synced_at": time.time(),
            "labels": meta.get("labels") or labels,
            "title": meta.get("title") or title,
        }
    }
    updated = _store_issue_metadata(
        conn,
        issue=issue,
        patch=patch,
        event_type="issue_github_synced",
        payload={
            "action": ("noop" if not actions else ",".join(actions)),
            "repo": repo,
            "number": issue_number,
            "state": patch["github_issue"]["state"],
            "synced_status": issue.status,
            "dry_run": dry_run,
        },
    )
    return {
        "issue_id": issue.issue_id,
        "action": "noop" if not actions else ("dry_run_" if dry_run else "") + ",".join(actions),
        "repo": repo,
        "github_number": issue_number,
        "github_url": patch["github_issue"]["url"],
        "status": updated.status,
        "dry_run": dry_run,
    }


def slugify_issue_title(title: str, *, max_len: int = 40) -> str:
    raw = _PREFIX_RE.sub("", str(title or "").strip()).lower()
    slug = _SLUG_RE.sub("-", raw).strip("-")
    if not slug:
        slug = "issue"
    return slug[:max_len].rstrip("-") or "issue"
