"""Shared telemetry identity contract helpers.

This module keeps the live TraceEvent bus and the posthoc archive envelope
speaking the same identity language without forcing them into one payload shape.
"""

from __future__ import annotations

from typing import Any, Mapping


IDENTITY_FIELDS: tuple[str, ...] = (
    "event_type",
    "schema_version",
    "source",
    "trace_id",
    "session_id",
    "event_id",
    "upstream_event_id",
    "run_id",
    "parent_run_id",
    "job_id",
    "issue_id",
    "task_ref",
    "logical_task_id",
    "identity_confidence",
    "provider",
    "model",
    "repo_name",
    "repo_path",
    "repo_branch",
    "repo_head",
    "repo_upstream",
    "agent_name",
    "agent_source",
    "commit_sha",
)

EXECUTION_IDENTITY_FIELDS: tuple[str, ...] = (
    "trace_id",
    "run_id",
    "job_id",
    "task_ref",
    "logical_task_id",
    "identity_confidence",
)


def compact_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    """Drop empty values while preserving stable plain dict output."""
    return {
        key: value
        for key, value in data.items()
        if value not in ("", None, [], {}, ())
    }


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _repo_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    repo = payload.get("repo")
    if isinstance(repo, Mapping):
        return {
            "name": _text(repo.get("name")),
            "path": _text(repo.get("path")),
            "branch": _text(repo.get("branch")),
            "head": _text(repo.get("head")),
            "upstream": _text(repo.get("upstream")),
        }
    return {
        "name": _text(payload.get("repo_name") or payload.get("project")),
        "path": _text(payload.get("repo_path")),
        "branch": _text(payload.get("repo_branch") or payload.get("branch")),
        "head": _text(payload.get("repo_head") or payload.get("head")),
        "upstream": _text(payload.get("repo_upstream")),
    }


def _agent_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    agent = payload.get("agent")
    if isinstance(agent, Mapping):
        return {
            "name": _text(agent.get("name") or payload.get("agent_id")),
            "source": _text(agent.get("source")),
        }
    return {
        "name": _text(payload.get("agent_name") or payload.get("agent_id")),
        "source": _text(payload.get("agent_source")),
    }


def _execution_task_identity(payload: Mapping[str, Any]) -> dict[str, str]:
    explicit_logical_task_id = _text(payload.get("logical_task_id"))
    raw_task_id = _text(payload.get("task_id"))
    task_ref = _text(payload.get("task_ref") or raw_task_id)

    logical_task_id = ""
    identity_confidence = "partial"
    if explicit_logical_task_id:
        logical_task_id = explicit_logical_task_id
        identity_confidence = "authoritative"
    elif raw_task_id and (not task_ref or raw_task_id == task_ref):
        logical_task_id = raw_task_id
        identity_confidence = "derived_task_id"
    elif task_ref:
        identity_confidence = "task_ref_only"
    elif any(
        _text(payload.get(field_name))
        for field_name in ("trace_id", "run_id", "job_id")
    ):
        identity_confidence = "execution_only"

    return {
        "task_ref": task_ref,
        "logical_task_id": logical_task_id,
        "identity_confidence": identity_confidence,
    }


def extract_identity_fields(
    payload: Mapping[str, Any],
    *,
    event_type: str = "",
    trace_id: str = "",
    session_id: str = "",
    source: str = "",
) -> dict[str, Any]:
    """Extract a normalized identity view from archive or live payloads."""
    repo = _repo_context(payload)
    agent = _agent_context(payload)
    task_identity = _execution_task_identity(payload)
    commit = payload.get("commit")
    commit_sha = ""
    if isinstance(commit, Mapping):
        commit_sha = _text(commit.get("commit") or commit.get("sha"))
    if not commit_sha:
        commit_sha = _text(payload.get("commit_sha") or payload.get("hash"))

    return compact_identity(
        {
            "event_type": _text(event_type or payload.get("event_type")),
            "schema_version": _text(payload.get("schema_version")),
            "source": _text(source or payload.get("source")),
            "trace_id": _text(trace_id or payload.get("trace_id")),
            "session_id": _text(session_id or payload.get("session_id")),
            "event_id": _text(payload.get("event_id")),
            "upstream_event_id": _text(payload.get("upstream_event_id")),
            "run_id": _text(payload.get("run_id")),
            "parent_run_id": _text(payload.get("parent_run_id")),
            "job_id": _text(payload.get("job_id")),
            "issue_id": _text(payload.get("issue_id")),
            "task_ref": task_identity["task_ref"],
            "logical_task_id": task_identity["logical_task_id"],
            "identity_confidence": task_identity["identity_confidence"],
            "provider": _text(payload.get("provider")),
            "model": _text(payload.get("model")),
            "repo_name": repo["name"],
            "repo_path": repo["path"],
            "repo_branch": repo["branch"],
            "repo_head": repo["head"],
            "repo_upstream": repo["upstream"],
            "agent_name": agent["name"],
            "agent_source": agent["source"],
            "commit_sha": commit_sha,
            # Execution-layer extensions: preserve them in the normalized
            # identity view without promoting them to root canonical fields.
            "lane_id": _text(payload.get("lane_id")),
            "role_id": _text(payload.get("role_id")),
            "adapter_id": _text(payload.get("adapter_id")),
            "profile_id": _text(payload.get("profile_id")),
            "executor_kind": _text(payload.get("executor_kind")),
        }
    )


def apply_identity_defaults(
    payload: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge identity into payload without overwriting caller-provided values."""
    merged = dict(payload)
    for key, value in identity.items():
        if value in ("", None, [], {}, ()):
            continue
        merged.setdefault(key, value)
    return merged
