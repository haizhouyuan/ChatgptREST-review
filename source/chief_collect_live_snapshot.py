#!/usr/bin/env python3
"""Read-only live snapshot exporter for the Hermes chief dry-run harness.

The exporter only performs declared Multica read commands and allowlist-only
Hermes config parsing. It writes a snapshot atomically after every required
read succeeds. It never reads auth JSON files, environment variables, or raw
secret stores.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HERMES_CONFIG = Path.home() / ".hermes/config.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "docs/control_plane/snapshots"
DEFAULT_CHIEF_AGENT_ID = "48251656-cdc5-48e3-804d-4fd338614b7b"
DEFAULT_WORKSPACES = [
    "6aa0f38c-1f97-4fbb-a4ff-d48eb0d3a580",
    "bbc33e1b-a6d8-4724-b29f-b35ac8372572",
]

SECRET_MARKERS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "oauth",
    "bearer",
    "authorization",
)


class SnapshotError(Exception):
    """A fail-closed snapshot collection error."""


def now_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def key_value(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    return key.strip(), strip_quotes(value.strip())


def parse_hermes_config_allowlist(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SnapshotError(f"hermes_config_not_found:{path}")

    summary: dict[str, Any] = {
        "model": {},
        "agent": {},
        "mcp_server_names": [],
        "skills": {"external_dirs": []},
    }
    section: str | None = None
    in_external_dirs = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            in_external_dirs = False
            continue

        if section == "model" and indent == 2:
            parsed = key_value(line)
            if parsed:
                key, value = parsed
                if key in {"provider", "default", "api_mode", "base_url"}:
                    summary["model"][key] = value
            continue

        if section == "agent" and indent == 2:
            parsed = key_value(line)
            if parsed:
                key, value = parsed
                if key == "reasoning_effort":
                    summary["agent"][key] = value
            continue

        if section == "mcp_servers" and indent == 2 and line.endswith(":"):
            server_name = line[:-1].strip()
            if server_name and not any(marker in server_name.lower() for marker in SECRET_MARKERS):
                summary["mcp_server_names"].append(server_name)
            continue

        if section == "skills" and in_external_dirs and indent >= 2 and line.startswith("- "):
            summary["skills"]["external_dirs"].append(strip_quotes(line[2:].strip()))
            continue

        if section == "skills" and indent == 2:
            parsed = key_value(line)
            if parsed:
                key, value = parsed
                in_external_dirs = key == "external_dirs"
                if key == "external_dirs" and value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1].strip()
                    if inner:
                        summary["skills"]["external_dirs"] = [
                            strip_quotes(item.strip())
                            for item in inner.split(",")
                            if item.strip()
                        ]
            continue

    return summary


def contains_secret_like_key(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_MARKERS):
                findings.append(next_path)
            findings.extend(contains_secret_like_key(nested, next_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            findings.extend(contains_secret_like_key(item, f"{path}[{idx}]"))
    return findings


def run_multica_json(multica_bin: str, workspace_id: str, args: list[str], timeout: int) -> Any:
    cmd = [multica_bin, "--workspace-id", workspace_id, *args, "--output", "json"]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SnapshotError(f"multica_timeout:{workspace_id}:{' '.join(args)}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        message = detail[0] if detail else "no_error_output"
        raise SnapshotError(f"multica_failed:{workspace_id}:{' '.join(args)}:{message}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"multica_invalid_json:{workspace_id}:{' '.join(args)}") from exc


def list_all_issues(multica_bin: str, workspace_id: str, timeout: int, limit: int) -> list[dict[str, Any]]:
    offset = 0
    issues: list[dict[str, Any]] = []
    while True:
        payload = run_multica_json(
            multica_bin,
            workspace_id,
            ["issue", "list", "--limit", str(limit), "--offset", str(offset)],
            timeout,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
            raise SnapshotError(f"unexpected_issue_list_shape:{workspace_id}")
        issues.extend(item for item in payload["issues"] if isinstance(item, dict))
        if not payload.get("has_more"):
            break
        offset += limit
    return issues


def list_projects(multica_bin: str, workspace_id: str, timeout: int) -> dict[str, dict[str, Any]]:
    payload = run_multica_json(multica_bin, workspace_id, ["project", "list"], timeout)
    if not isinstance(payload, list):
        raise SnapshotError(f"unexpected_project_list_shape:{workspace_id}")
    return {
        str(project.get("id")): project
        for project in payload
        if isinstance(project, dict) and project.get("id")
    }


def find_chief_agent(multica_bin: str, workspace_id: str, timeout: int, chief_agent_id: str) -> dict[str, Any]:
    payload = run_multica_json(multica_bin, workspace_id, ["agent", "list"], timeout)
    if not isinstance(payload, list):
        raise SnapshotError(f"unexpected_agent_list_shape:{workspace_id}")
    for agent in payload:
        if isinstance(agent, dict) and agent.get("id") == chief_agent_id:
            return agent
    raise SnapshotError(f"chief_agent_not_found:{workspace_id}:{chief_agent_id}")


def normalize_mcp_config(raw: Any) -> dict[str, list[str]] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        lanes = raw.get("lanes")
        if isinstance(lanes, list):
            return {"lanes": [str(item) for item in lanes]}
        return {"lanes": sorted(str(key) for key in raw.keys())}
    if isinstance(raw, list):
        return {"lanes": [str(item) for item in raw]}
    return None


def normalize_issue(issue: dict[str, Any], project_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    project = project_by_id.get(str(issue.get("project_id")), {})
    project_priority = project.get("priority") or project.get("status") or "none"
    return {
        "id": str(issue.get("id") or ""),
        "identifier": issue.get("identifier"),
        "number": issue.get("number"),
        "title": str(issue.get("title") or ""),
        "status": str(issue.get("status") or "unknown"),
        "priority": str(issue.get("priority") or "none"),
        "project_priority": str(project_priority or "none"),
        "created_at": issue.get("created_at"),
        "action_class": "implementation",
        "risk_class": "high",
        "contract": {"full": False},
        "dependencies": [],
        "red_team": {"status": "not_started", "independence_grade": "C"},
        "sidecar_unlock_order": None,
        "workspace_id": issue.get("workspace_id"),
        "project_id": issue.get("project_id"),
        "source_defaults": {
            "action_class": "conservative_default",
            "risk_class": "conservative_default",
            "contract.full": "conservative_default",
            "red_team": "conservative_default",
        },
    }


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    hermes_summary = parse_hermes_config_allowlist(args.hermes_config)
    secret_keys = contains_secret_like_key(hermes_summary)
    if secret_keys:
        raise SnapshotError(f"secret_like_key_in_sanitized_summary:{','.join(secret_keys)}")

    chief_agent = find_chief_agent(args.multica_bin, args.ops_workspace_id, args.timeout, args.chief_agent_id)
    project_maps: dict[str, dict[str, dict[str, Any]]] = {}
    all_issues: list[dict[str, Any]] = []
    issue_counts: dict[str, int] = {}

    for workspace_id in args.workspace_id:
        projects = list_projects(args.multica_bin, workspace_id, args.timeout)
        project_maps[workspace_id] = projects
        issues = list_all_issues(args.multica_bin, workspace_id, args.timeout, args.limit)
        issue_counts[workspace_id] = len(issues)
        all_issues.extend(normalize_issue(issue, projects) for issue in issues)

    mcp_config = normalize_mcp_config(chief_agent.get("mcp_config"))
    skills = chief_agent.get("skills")
    if not isinstance(skills, list):
        skills = []

    return {
        "snapshot_id": args.snapshot_id or f"chief-live-{now_rfc3339()}",
        "captured_at": now_rfc3339(),
        "chief_state": {
            "agent_id": str(chief_agent.get("id") or args.chief_agent_id),
            "model": chief_agent.get("model"),
            "reasoning_effort": hermes_summary.get("agent", {}).get("reasoning_effort"),
            "mcp_config": mcp_config,
            "skills": [str(item) for item in skills],
        },
        "hermes_config_summary": hermes_summary,
        "source": {
            "exporter_version": "0.1.0",
            "multica_workspace_ids": args.workspace_id,
            "ops_workspace_id": args.ops_workspace_id,
            "issue_count_by_workspace": issue_counts,
            "issue_field_defaults": {
                "action_class": "implementation",
                "risk_class": "high",
                "contract.full": False,
                "red_team.status": "not_started",
                "red_team.independence_grade": "C",
                "sidecar_unlock_order": None,
            },
            "omitted": [
                "auth_store_contents",
                "environment_variables",
                "credential_values",
                "session_material",
                "mcp_urls",
                "mcp_headers",
            ],
        },
        "issues": all_issues,
    }


def write_atomic(path: Path, payload: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as fh:
        tmp_path = Path(fh.name)
        json.dump(payload, fh, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
        fh.write("\n")
    tmp_path.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect read-only live snapshot for chief dry-run harness")
    parser.add_argument("--multica-bin", default="multica")
    parser.add_argument("--workspace-id", action="append", default=list(DEFAULT_WORKSPACES))
    parser.add_argument("--ops-workspace-id", default="bbc33e1b-a6d8-4724-b29f-b35ac8372572")
    parser.add_argument("--chief-agent-id", default=DEFAULT_CHIEF_AGENT_ID)
    parser.add_argument("--hermes-config", type=Path, default=DEFAULT_HERMES_CONFIG)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--snapshot-id", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    output_path = args.output
    try:
        payload = build_snapshot(args)
        if output_path:
            write_atomic(output_path, payload, pretty=args.pretty)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    except SnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
