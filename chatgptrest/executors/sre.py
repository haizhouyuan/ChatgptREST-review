from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues, job_store
from chatgptrest.core.config import AppConfig
from chatgptrest.core.codex_runner import codex_exec_with_schema, codex_resume_last_message_json
from chatgptrest.core.db import connect
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.repair_jobs import create_repair_autofix_job
from chatgptrest.core.sre_jobs import requested_by_transport
from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.ops_shared.infra import atomic_write_json, now_iso, read_json, read_text, truncate_text
from chatgptrest.ops_shared.issue_targets import resolve_issue_external_target
from chatgptrest.ops_shared.maint_memory import load_maintagent_bootstrap_memory, load_maintagent_repo_memory


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRE_LANES_ROOT = (_REPO_ROOT / "state" / "sre_lanes").resolve()
_SCHEMA_PATH = (_REPO_ROOT / "ops" / "schemas" / "sre_fix_request_decision.schema.json").resolve()
_ROUTE_VALUES = {"manual", "repair.autofix", "repair.open_pr"}
_CONFIDENCE_VALUES = {"low", "medium", "high"}
_ROUTE_MODE_VALUES = {"plan_only", "auto_runtime", "auto_best_effort"}
_EXISTING_JOB_ID_RE = re.compile(r"existing_job_id=([a-f0-9]{32})", re.IGNORECASE)


def _bool_param(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _int_param(value: Any, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    out = max(int(minimum), out)
    if maximum is not None:
        out = min(int(maximum), out)
    return out


def _string_param(value: Any, default: str = "") -> str:
    raw = str(value or "").strip()
    return raw or default


def _sanitize_lane_component(value: str) -> str:
    out: list[str] = []
    for ch in str(value or "").strip().lower():
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("-")
    cleaned = "".join(out).strip("-")
    return cleaned[:80] if cleaned else ""


def _sre_lanes_root() -> Path:
    raw = _string_param(os.environ.get("CHATGPTREST_SRE_LANES_DIR"))
    if not raw:
        return _SRE_LANES_ROOT
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (_REPO_ROOT / raw).resolve(strict=False)
    return path


def _lane_id_for_request(input_obj: dict[str, Any], *, issue_id: str | None, incident_id: str | None, job_id: str | None) -> str:
    explicit = _sanitize_lane_component(_string_param(input_obj.get("lane_id")))
    if explicit:
        return explicit
    if issue_id:
        return f"issue-{_sanitize_lane_component(issue_id)}"
    if incident_id:
        return f"incident-{_sanitize_lane_component(incident_id)}"
    if job_id:
        return f"job-{_sanitize_lane_component(job_id)}"
    symptom = _string_param(input_obj.get("symptom"))
    if symptom:
        digest = hashlib.sha1(symptom.encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"symptom-{digest}"
    return f"request-{hashlib.sha1(json.dumps(input_obj, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]}"


def _job_relpath(*parts: str) -> str:
    return (Path("jobs") / parts[0] / parts[1]).as_posix()


def _json_preview(value: Any, *, limit: int = 20_000) -> str:
    try:
        raw = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        raw = str(value)
    if len(raw) > limit:
        return raw[:limit] + f"\n...<truncated {len(raw) - limit} chars>"
    return raw


def _append_section(lines: list[str], *, title: str, body: str) -> None:
    text = str(body or "").strip()
    if not text:
        return
    lines.append(f"=== {title} ===")
    lines.append(text)
    lines.append("")


def _append_section_with_stats(
    lines: list[str],
    section_stats: list[dict[str, Any]],
    *,
    title: str,
    body: str,
) -> None:
    text = str(body or "").strip()
    if not text:
        return
    _append_section(lines, title=title, body=text)
    section_stats.append({"title": title, "chars": len(text)})


def _compact_prompt_value(
    value: Any,
    *,
    string_limit: int = 1200,
    list_limit: int = 4,
    dict_limit: int = 10,
    depth: int = 0,
    max_depth: int = 3,
) -> Any:
    if isinstance(value, str):
        return truncate_text(value, limit=max(120, int(string_limit)))
    if isinstance(value, dict):
        if depth >= max_depth:
            return truncate_text(_json_preview(value, limit=max(240, int(string_limit))), limit=max(240, int(string_limit)))
        out: dict[str, Any] = {}
        items = list(value.items())
        for key, item in items[: int(dict_limit)]:
            out[str(key)] = _compact_prompt_value(
                item,
                string_limit=max(200, int(string_limit * 0.6)),
                list_limit=max(2, int(list_limit) - 1),
                dict_limit=max(4, int(dict_limit) - 2),
                depth=depth + 1,
                max_depth=max_depth,
            )
        if len(items) > int(dict_limit):
            out["_truncated_keys"] = len(items) - int(dict_limit)
        return out
    if isinstance(value, list):
        out = [
            _compact_prompt_value(
                item,
                string_limit=max(200, int(string_limit * 0.7)),
                list_limit=max(2, int(list_limit) - 1),
                dict_limit=max(4, int(dict_limit) - 2),
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in value[: int(list_limit)]
        ]
        if len(value) > int(list_limit):
            out.append({"_truncated_items": len(value) - int(list_limit)})
        return out
    return value


def _compact_context_pack_for_prompt(context_pack: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(context_pack, dict):
        return None
    compact = dict(context_pack)
    compact.pop("global_memory_md", None)
    return _compact_prompt_value(compact, string_limit=900, list_limit=4, dict_limit=10)


def _tail_text(path: Path, *, max_lines: int = 100, max_bytes: int = 80_000) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            end = handle.tell()
            size = min(int(max_bytes), end)
            handle.seek(max(0, end - size))
            raw = handle.read()
    except Exception:
        return ""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if len(lines) > int(max_lines):
        lines = lines[-int(max_lines) :]
    return "\n".join(lines)


def _requested_by_payload(*, lane_id: str, parent_job_id: str) -> dict[str, Any]:
    payload = requested_by_transport("sre.fix_request")
    payload["lane_id"] = str(lane_id)
    payload["parent_job_id"] = str(parent_job_id)
    return payload


@contextmanager
def _lane_lock(lane_dir: Path):
    lane_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lane_dir / ".lane.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_history(history_path: Path, *, limit: int = 3) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    if limit > 0 and len(rows) > limit:
        rows = rows[-limit:]
    return rows


def _append_history(history_path: Path, payload: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _normalize_actions_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = list(value)
    elif isinstance(value, tuple):
        items = list(value)
    else:
        items = re.split(r"[,\n]", str(value))
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        raw = _string_param(item)
        if not raw or raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
    return out


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        raw = _string_param(item)
        if raw:
            out.append(raw)
    return out


def _controller_run_kind(
    *,
    input_obj: dict[str, Any],
    issue_id: str | None,
    incident_id: str | None,
    target_job_id: str | None,
) -> str:
    explicit = _string_param(input_obj.get("run_kind"))
    if explicit:
        return explicit
    if incident_id:
        return "incident_maintenance"
    if issue_id:
        return "issue_maintenance"
    if target_job_id:
        return "job_maintenance"
    return "maintenance"


def _controller_escalation_source(*, input_obj: dict[str, Any], incident_id: str | None) -> str:
    explicit = _string_param(input_obj.get("escalation_source"))
    if explicit:
        return explicit
    if incident_id:
        return "maint_daemon"
    return "direct_request"


def _controller_acceptance_criteria(
    *,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
) -> list[str]:
    explicit = _normalize_string_list(input_obj.get("acceptance_criteria"))
    if explicit:
        return explicit
    explicit = _normalize_string_list(params_obj.get("acceptance_criteria"))
    if explicit:
        return explicit
    return [
        "Choose exactly one next route: manual, repair.autofix, or repair.open_pr.",
        "Ground the route in the current incident evidence and lane history.",
        "Preserve canonical lane memory and request/prompt artifacts.",
        "Keep runtime actions within the configured risk and allowlist constraints.",
    ]


def _controller_decision_override(params_obj: dict[str, Any]) -> dict[str, Any] | None:
    raw = params_obj.get("decision_override")
    if not isinstance(raw, dict):
        return None
    route = _string_param(raw.get("route"))
    if route not in {"manual", "repair.autofix", "repair.open_pr"}:
        return None
    payload = dict(raw)
    if not _string_param(payload.get("summary")):
        payload["summary"] = "Controller decision override supplied by upstream maintenance policy."
    if not _string_param(payload.get("root_cause")):
        payload["root_cause"] = "Upstream maintenance policy selected an explicit fallback route."
    if not _string_param(payload.get("rationale")):
        payload["rationale"] = "This run bypassed Codex analysis and reused a controller decision override."
    if not _string_param(payload.get("confidence")):
        payload["confidence"] = "high"
    notes = payload.get("notes")
    if isinstance(notes, list):
        payload["notes"] = [str(item).strip() for item in notes if str(item or "").strip()]
    else:
        payload["notes"] = []
    if "controller_override" not in payload["notes"]:
        payload["notes"].append("controller_override")
    return payload


def _controller_phase(*, decision: dict[str, Any], downstream: dict[str, Any] | None) -> str:
    if downstream:
        kind = _string_param(downstream.get("kind"))
        if kind == "repair.autofix":
            return "routed_to_repair_autofix"
        if kind == "repair.open_pr":
            return "routed_to_repair_open_pr"
    if _string_param(decision.get("route")) == "manual":
        return "manual_required"
    return "resolved"


def _taskpack_projection_paths(lane_dir: Path) -> dict[str, Path]:
    taskpack_dir = lane_dir / "taskpack"
    return {
        "dir": taskpack_dir,
        "request_view": taskpack_dir / "request_view.json",
        "prompt_view": taskpack_dir / "prompt_view.md",
        "acceptance_view": taskpack_dir / "acceptance_view.md",
        "allowed_actions_view": taskpack_dir / "allowed_actions_view.json",
    }


def _operator_attach_payload(*, lane_id: str, lane_dir: Path) -> dict[str, Any]:
    script_path = (_REPO_ROOT / "ops" / "codex_maint_attach.py").resolve()
    return {
        "script_path": script_path.as_posix(),
        "lane_id": lane_id,
        "lane_dir": lane_dir.as_posix(),
        "argv": ["python3", script_path.as_posix(), "--lane-id", lane_id],
    }


def _write_taskpack_projection(
    *,
    lane_dir: Path,
    lane_id: str,
    run_kind: str,
    escalation_source: str,
    issue_id: str | None,
    incident_id: str | None,
    target_job_id: str | None,
    target_conversation_url: str | None,
    symptom: str | None,
    context_pack: Any,
    prompt: str,
    memory_snapshot_path: str | None,
    allowed_actions: list[str],
    max_risk: str,
    acceptance_criteria: list[str],
    resume_allowed: bool,
    operator_attachable: bool,
    runbook_excerpt: str,
) -> dict[str, str]:
    paths = _taskpack_projection_paths(lane_dir)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        paths["request_view"],
        {
            "lane_id": lane_id,
            "run_kind": run_kind,
            "escalation_source": escalation_source,
            "issue_id": issue_id,
            "incident_id": incident_id,
            "target_job_id": target_job_id,
            "target_conversation_url": target_conversation_url,
            "symptom": symptom,
            "context_pack": context_pack,
            "runbook_excerpt": runbook_excerpt,
            "memory_snapshot": memory_snapshot_path,
            "allowed_actions": allowed_actions,
            "max_risk": max_risk,
            "acceptance_criteria": acceptance_criteria,
            "resume_allowed": bool(resume_allowed),
            "operator_attachable": bool(operator_attachable),
        },
    )
    paths["prompt_view"].write_text(prompt.rstrip() + "\n", encoding="utf-8")
    acceptance_lines = ["# acceptance criteria", ""]
    for item in acceptance_criteria:
        acceptance_lines.append(f"- {item}")
    acceptance_lines.append("")
    paths["acceptance_view"].write_text("\n".join(acceptance_lines), encoding="utf-8")
    atomic_write_json(
        paths["allowed_actions_view"],
        {
            "lane_id": lane_id,
            "allowed_actions": allowed_actions,
            "max_risk": max_risk,
            "resume_allowed": bool(resume_allowed),
            "operator_attachable": bool(operator_attachable),
        },
    )
    return {name: path.as_posix() for name, path in paths.items()}


def _job_summary(job: job_store.JobRecord) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status.value,
        "phase": job.phase,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "conversation_url": job.conversation_url,
        "answer_path": job.answer_path,
        "answer_chars": job.answer_chars,
        "last_error_type": job.last_error_type,
        "last_error": truncate_text(job.last_error, limit=2000),
    }


def _issue_summary(issue: client_issues.ClientIssueRecord) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "project": issue.project,
        "title": issue.title,
        "severity": issue.severity,
        "status": issue.status,
        "kind": issue.kind,
        "count": issue.count,
        "symptom": truncate_text(issue.symptom, limit=4000),
        "raw_error": truncate_text(issue.raw_error, limit=4000),
        "latest_job_id": issue.latest_job_id,
        "latest_conversation_url": issue.latest_conversation_url,
        "latest_artifacts_path": issue.latest_artifacts_path,
        "tags": list(issue.tags or []),
        "metadata": dict(issue.metadata or {}),
    }


def _resolve_artifact_path(artifacts_dir: Path, rel_or_abs: str | None) -> Path | None:
    raw = _string_param(rel_or_abs)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (artifacts_dir / raw).resolve(strict=False)


def _target_job_context(*, artifacts_dir: Path, target_job: job_store.JobRecord) -> dict[str, Any]:
    job_dir = artifacts_dir / "jobs" / target_job.job_id
    answer_text = ""
    answer_path = _resolve_artifact_path(artifacts_dir, target_job.answer_path)
    if answer_path is not None and answer_path.exists():
        answer_text = read_text(answer_path, limit=20_000)
    result_text = read_text(job_dir / "result.json", limit=20_000)
    run_meta_text = read_text(job_dir / "run_meta.json", limit=20_000)
    events_tail = _tail_text(job_dir / "events.jsonl", max_lines=120)
    return {
        "summary": _job_summary(target_job),
        "answer_text": answer_text,
        "result_json": result_text,
        "run_meta_json": run_meta_text,
        "events_tail": events_tail,
    }


def _recent_issue_events(conn: Any, *, issue_id: str) -> list[dict[str, Any]]:
    events, _next_after = client_issues.list_issue_events(conn, issue_id=issue_id, limit=12)
    out: list[dict[str, Any]] = []
    for event in events:
        out.append(
            {
                "id": event.id,
                "ts": event.ts,
                "type": event.type,
                "payload": event.payload,
            }
        )
    return out


def _git_cmd(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(_REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return str(proc.stdout or "").strip()


def _gitnexus_query(*, query: str, limit: int) -> dict[str, Any]:
    enabled = _bool_param(os.environ.get("CHATGPTREST_SRE_ENABLE_GITNEXUS"), False)
    if not enabled:
        return {"enabled": False, "ok": False, "reason": "disabled"}
    prompt = _string_param(query)
    if not prompt:
        return {"enabled": True, "ok": False, "reason": "empty_query"}
    raw_cmd = _string_param(
        os.environ.get("CHATGPTREST_SRE_GITNEXUS_QUERY_CMD"),
        '/usr/bin/env npm_config_cache=/tmp/chatgptrest-gitnexus-npx-cache npx --yes gitnexus query',
    )
    timeout_seconds = max(5.0, float(_int_param(os.environ.get("CHATGPTREST_SRE_GITNEXUS_TIMEOUT_SECONDS"), 20)))
    try:
        cmd = shlex.split(raw_cmd)
    except Exception as exc:
        return {"enabled": True, "ok": False, "reason": f"bad_command:{type(exc).__name__}"}
    cmd.extend(["--repo", "ChatgptREST", "--limit", str(max(1, limit)), prompt])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return {"enabled": True, "ok": False, "reason": f"{type(exc).__name__}: {exc}"[:1200], "query": prompt}
    stdout = str(proc.stdout or "").strip()
    stderr = str(proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "enabled": True,
            "ok": False,
            "query": prompt,
            "returncode": int(proc.returncode),
            "error": truncate_text(stderr or stdout, limit=2000),
        }
    if not stdout:
        return {"enabled": True, "ok": True, "query": prompt, "markdown": "", "evidence": []}
    try:
        payload = json.loads(stdout)
    except Exception:
        return {
            "enabled": True,
            "ok": True,
            "query": prompt,
            "markdown": truncate_text(stdout, limit=4000),
            "evidence": [],
        }
    if not isinstance(payload, dict):
        return {
            "enabled": True,
            "ok": True,
            "query": prompt,
            "markdown": truncate_text(stdout, limit=4000),
            "evidence": [],
        }
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    return {
        "enabled": True,
        "ok": True,
        "query": prompt,
        "markdown": truncate_text(payload.get("markdown"), limit=8000),
        "evidence": evidence[:8],
        "processes": payload.get("processes") if isinstance(payload.get("processes"), list) else [],
    }


def _normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    route = _string_param(raw.get("route"), "manual").lower()
    if route not in _ROUTE_VALUES:
        route = "manual"
    confidence = _string_param(raw.get("confidence"), "medium").lower()
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "medium"
    runtime_fix_raw = raw.get("runtime_fix")
    runtime_fix = dict(runtime_fix_raw) if isinstance(runtime_fix_raw, dict) else {}
    open_pr_raw = raw.get("open_pr")
    open_pr = dict(open_pr_raw) if isinstance(open_pr_raw, dict) else {}
    recommended_actions = raw.get("recommended_actions")
    if not isinstance(recommended_actions, list):
        recommended_actions = []
    notes = raw.get("notes")
    if not isinstance(notes, list):
        notes = []
    gitnexus_queries = raw.get("gitnexus_queries")
    if not isinstance(gitnexus_queries, list):
        gitnexus_queries = []
    return {
        "summary": truncate_text(raw.get("summary"), limit=4000),
        "root_cause": truncate_text(raw.get("root_cause"), limit=8000),
        "route": route,
        "confidence": confidence,
        "rationale": truncate_text(raw.get("rationale"), limit=8000),
        "recommended_actions": [truncate_text(item, limit=200) for item in recommended_actions if str(item or "").strip()],
        "gitnexus_queries": [truncate_text(item, limit=400) for item in gitnexus_queries if str(item or "").strip()],
        "runtime_fix": runtime_fix,
        "open_pr": open_pr,
        "notes": [truncate_text(item, limit=2000) for item in notes if str(item or "").strip()],
    }


def _decision_hash(decision: dict[str, Any], *, lane_id: str, target_job_id: str | None) -> str:
    payload = {
        "lane_id": lane_id,
        "target_job_id": target_job_id,
        "route": decision.get("route"),
        "summary": decision.get("summary"),
        "root_cause": decision.get("root_cause"),
        "runtime_fix": decision.get("runtime_fix"),
        "open_pr": decision.get("open_pr"),
    }
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _reuse_existing_downstream_job(conn: Any, *, exc: IdempotencyCollision, expected_kind: str) -> dict[str, Any] | None:
    existing = job_store.get_job(conn, job_id=exc.existing_job_id)
    if existing is None or existing.kind != expected_kind:
        return None
    payload: dict[str, Any] = {
        "kind": existing.kind,
        "job_id": existing.job_id,
        "status": existing.status.value,
        "idempotency_reused": True,
    }
    if existing.answer_path:
        payload["answer_path"] = existing.answer_path
    if existing.conversation_url:
        payload["conversation_url"] = existing.conversation_url
    return payload


def _reused_downstream_from_issue_payload(conn: Any, *, issue_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(issue_payload, dict):
        return None
    raw_error = _string_param(issue_payload.get("raw_error"))
    if "idempotencycollision" not in raw_error.lower():
        return None
    match = _EXISTING_JOB_ID_RE.search(raw_error)
    if match is None:
        return None
    existing_job_id = match.group(1)
    existing = job_store.get_job(conn, job_id=existing_job_id)
    if existing is None or existing.kind not in {"repair.autofix", "repair.open_pr"}:
        return None
    decision = {
        "summary": "An equivalent downstream repair job already exists and should be reused.",
        "root_cause": (
            "The prior sre.fix_request already created the concrete downstream repair lane, "
            "and a later retry collided on the same idempotent downstream target instead of revealing a new defect."
        ),
        "route": existing.kind,
        "confidence": "high",
        "rationale": (
            "The issue payload already names an existing downstream job id, so the fastest correct action is to reuse "
            "that repair job instead of re-running Codex diagnosis or creating another downstream request."
        ),
        "recommended_actions": [
            f"Reuse the existing downstream job `{existing.job_id}` instead of creating a duplicate repair request."
        ],
        "gitnexus_queries": [],
        "runtime_fix": {},
        "open_pr": {},
        "notes": ["heuristic_fast_path", "downstream_reuse_from_issue_payload"],
    }
    downstream: dict[str, Any] = {
        "kind": existing.kind,
        "job_id": existing.job_id,
        "status": existing.status.value,
        "idempotency_reused": True,
        "reused_reason": "issue_existing_job_id",
    }
    if existing.answer_path:
        downstream["answer_path"] = existing.answer_path
    if existing.conversation_url:
        downstream["conversation_url"] = existing.conversation_url
    return {"decision": decision, "downstream": downstream}


def _route_mode(params: dict[str, Any]) -> str:
    route_mode = _string_param(params.get("route_mode"), "auto_best_effort")
    if route_mode not in _ROUTE_MODE_VALUES:
        return "auto_best_effort"
    return route_mode


def _should_submit_runtime_fix(route_mode: str) -> bool:
    return route_mode in {"auto_runtime", "auto_best_effort"}


def _should_submit_open_pr(route_mode: str) -> bool:
    return route_mode == "auto_best_effort"


def _merge_open_pr_instructions(*, request_instructions: str, decision_instructions: str) -> str | None:
    parts: list[str] = []
    if request_instructions:
        parts.append(f"Requester instructions:\n{request_instructions}")
    if decision_instructions:
        parts.append(f"Coordinator instructions:\n{decision_instructions}")
    merged = "\n\n".join(parts).strip()
    return merged or None


def _heuristic_runtime_fix_decision(
    *,
    kind: str,
    status: str,
    error_type: str,
    error: str,
) -> dict[str, Any] | None:
    kind_l = str(kind or "").strip().lower()
    status_l = str(status or "").strip().lower()
    error_type_l = str(error_type or "").strip().lower()
    error_text = str(error or "").strip()
    error_l = error_text.lower()
    is_chatgpt = kind_l.startswith("chatgpt_web.")
    is_gemini = kind_l.startswith("gemini_web.")

    allow_actions: list[str] = ["capture_ui"]
    recommended_actions: list[str] = []
    summary = ""
    root_cause = ""
    rationale = ""
    confidence = "high"

    if "cdp connect failed" in error_l or "target page, context or browser has been closed" in error_l or error_type_l in {"infraerror", "targetclosederror"}:
        if is_chatgpt:
            allow_actions.append("clear_blocked")
        allow_actions.extend(["restart_driver", "restart_chrome"])
        recommended_actions = [
            "Capture UI evidence before changing runtime state.",
            "Clear any stale blocked marker on the ChatGPT path.",
            "Restart the driver first, then Chrome only if CDP is still unhealthy.",
        ]
        summary = "Runtime CDP/browser failure should be handled by guarded runtime recovery."
        root_cause = (
            "The ask failed before prompt send because the CDP browser/page context disappeared, "
            "so the failure points to runtime driver/Chrome state rather than repository logic."
        )
        rationale = "The error signature already names CDP connect failure / closed browser context, which is a runtime repair case."
    elif "driver blocked: network" in error_l or (status_l == "blocked" and "network" in error_l):
        if is_chatgpt:
            allow_actions.append("clear_blocked")
        allow_actions.append("restart_driver")
        recommended_actions = [
            "Capture UI evidence and blocked state first.",
            "Clear the blocked marker before retrying the driver path.",
            "Restart the driver only if the blocked state persists.",
        ]
        summary = "Blocked network state should be recovered through guarded runtime repair."
        root_cause = "The target job is blocked on driver/network state, not on an application code defect."
        rationale = "ChatgptREST already has a runtime recovery path for blocked/cooldown driver issues."
    elif "attachment contract missing" in error_l:
        return {
            "summary": "Attachment contract mismatch needs a code or caller-contract fix, not a runtime repair.",
            "root_cause": (
                "The request referenced local paths in prompt text without declaring input.file_paths, "
                "so the failure is in request construction / contract enforcement."
            ),
            "route": "repair.open_pr",
            "confidence": confidence,
            "rationale": "Runtime restarts will not change malformed attachment inputs.",
            "recommended_actions": [
                "Patch the caller or request builder to pass input.file_paths explicitly.",
                "Add a regression test for path-like prompt text without attachment metadata.",
            ],
            "gitnexus_queries": [],
            "runtime_fix": {},
            "open_pr": {
                "mode": "p0",
                "instructions": (
                    "Fix the attachment contract path: when prompt text references local files, "
                    "the caller must populate input.file_paths or sanitize path-like tokens."
                ),
                "run_tests": False,
            },
            "notes": ["heuristic_fast_path", "attachment_contract"],
        }
    elif error_type_l in {"waitnoprogresstimeout", "waitnothreadurltimeout"} or "wait no progress" in error_l:
        if is_chatgpt:
            allow_actions.append("refresh")
        allow_actions.append("restart_driver")
        recommended_actions = [
            "Capture UI state for the existing conversation first.",
            "Try a no-prompt refresh on ChatGPT before restart-class actions.",
            "Restart the driver if the wait path still has no progress.",
        ]
        summary = "Wait-stage stall should use no-prompt runtime recovery before any code change."
        root_cause = "The conversation is already in flight; the failure is on the wait/export path rather than request construction."
        rationale = "WaitNoProgress / missing thread URL failures are explicitly covered by the repair playbook runtime path."
    elif is_gemini and error_type_l in {"geminiimportcodeunavailable", "geminiimportcodenotfound"}:
        return {
            "summary": "Gemini repo-import is unavailable on the current UI path and should not trigger runtime autofix.",
            "root_cause": (
                "The failure is on the Gemini repo-import tool surface itself, so restart-class runtime repair is noisy "
                "and usually does not change the channel capability."
            ),
            "route": "manual",
            "confidence": confidence,
            "rationale": (
                "This should be handled by switching review transport/channel or patching the import lane, not by "
                "restarting Chrome/driver and polluting repair history."
            ),
            "recommended_actions": [
                "Capture a minimal UI snapshot for evidence.",
                "Switch the review request to repo-first text/review-pack transport or attachments-first fallback.",
                "Only pursue code repair if the repo-import lane itself is meant to be supported.",
            ],
            "gitnexus_queries": [],
            "runtime_fix": {},
            "open_pr": {},
            "notes": ["heuristic_fast_path", "gemini_import_lane"],
        }
    elif is_gemini and ("cannot find gemini tools button" in error_l or "toolbox-drawer-button" in error_l or "element is not enabled" in error_l):
        allow_actions.extend(["restart_driver", "restart_chrome"])
        recommended_actions = [
            "Capture Gemini UI evidence around the disabled Tools button.",
            "Restart the driver to clear stale page state.",
            "Restart Chrome only if the tool selector remains unavailable.",
        ]
        summary = "Gemini send-path UI drift should be handled as a runtime repair first."
        root_cause = "The Gemini Tools control is present but disabled/unusable, which matches a transient UI/runtime drift rather than a repository code regression."
        rationale = "The selector and error signature already match the known Gemini transient runtime failure mode."
    else:
        return None

    return {
        "summary": summary,
        "root_cause": root_cause,
        "route": "repair.autofix",
        "confidence": confidence,
        "rationale": rationale,
        "recommended_actions": recommended_actions,
        "gitnexus_queries": [],
        "runtime_fix": {
            "allow_actions": allow_actions,
            "max_risk": "medium",
            "reason": summary,
        },
        "open_pr": {},
        "notes": ["heuristic_fast_path"],
    }


def execute_sre_fix_request_controller(
    *,
    db_path: Path,
    artifacts_dir: Path,
    request_job_id: str,
    kind: str,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
    report_path: Path | None = None,
) -> dict[str, Any]:
    input_obj = dict(input_obj or {})
    params_obj = dict(params_obj or {})
    job_id = str(request_job_id)
    requested_issue_id = _string_param(input_obj.get("issue_id")) or None
    incident_id = _string_param(input_obj.get("incident_id")) or None
    requested_target_job_id = _string_param(input_obj.get("job_id")) or None
    symptom = _string_param(input_obj.get("symptom")) or None
    instructions = _string_param(input_obj.get("instructions")) or None
    context_pack = input_obj.get("context_pack")
    lane_id = _lane_id_for_request(
        input_obj,
        issue_id=requested_issue_id,
        incident_id=incident_id,
        job_id=requested_target_job_id,
    )
    if not any(
        [
            requested_issue_id,
            incident_id,
            requested_target_job_id,
            symptom,
            instructions,
            input_obj.get("context") is not None,
            context_pack is not None,
        ]
    ):
        raise ValueError("Missing issue_id / incident_id / job_id / symptom / instructions / context / context_pack")

    timeout_seconds = _int_param(params_obj.get("timeout_seconds"), 600, minimum=30, maximum=3600)
    model = _string_param(params_obj.get("model")) or None
    resume_lane = _bool_param(params_obj.get("resume_lane"), True)
    gitnexus_limit = _int_param(params_obj.get("gitnexus_limit"), 5, minimum=1, maximum=10)
    route_mode = _route_mode(params_obj)
    lane_dir = (_sre_lanes_root() / lane_id).resolve()
    manifest_path = lane_dir / "lane_manifest.json"
    history_path = lane_dir / "decision_history.jsonl"
    requests_dir = lane_dir / "requests"
    codex_dir = lane_dir / "codex"
    reports_dir = lane_dir / "reports"
    request_stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    request_basename = f"{request_stamp}_{job_id}"
    request_path = requests_dir / f"{request_basename}.json"
    prompt_path = codex_dir / f"{request_basename}.prompt.md"
    decision_path = codex_dir / f"{request_basename}.decision.json"
    resume_out_path = codex_dir / f"{request_basename}.resume.txt"

    with _lane_lock(lane_dir):
        manifest = read_json(manifest_path) or {}
        if not isinstance(manifest, dict):
            manifest = {}
        history = _read_history(history_path, limit=3)
        issue_payload: dict[str, Any] | None = None
        issue_events: list[dict[str, Any]] = []
        issue_target_resolution: dict[str, Any] | None = None
        reused_downstream: dict[str, Any] | None = None
        target_job: job_store.JobRecord | None = None
        target_job_context: dict[str, Any] | None = None
        gitnexus_query = symptom or instructions or requested_issue_id or requested_target_job_id or incident_id or job_id

        with connect(db_path) as conn:
            if requested_issue_id:
                issue = client_issues.get_issue(conn, issue_id=requested_issue_id)
                if issue is None:
                    raise KeyError(f"issue not found: {requested_issue_id}")
                issue_payload = _issue_summary(issue)
                issue_events = _recent_issue_events(conn, issue_id=issue.issue_id)
                if not requested_target_job_id:
                    issue_target_resolution = resolve_issue_external_target(
                        conn,
                        issue=issue,
                        issue_events=issue_events,
                    )
                    requested_target_job_id = _string_param(issue_target_resolution.get("resolved_job_id")) or None
            if requested_target_job_id:
                target_job = job_store.get_job(conn, job_id=requested_target_job_id)
                if target_job is None:
                    raise KeyError(f"job not found: {requested_target_job_id}")
                target_job_context = _target_job_context(artifacts_dir=artifacts_dir, target_job=target_job)
                gitnexus_query = (
                    symptom
                    or truncate_text(target_job.last_error, limit=400)
                    or target_job.kind
                    or requested_target_job_id
                )
            reused_downstream = _reused_downstream_from_issue_payload(conn, issue_payload=issue_payload)

        heuristic_error = "\n".join(
            [
                _string_param(issue_payload.get("raw_error")) if isinstance(issue_payload, dict) else "",
                _string_param(issue_payload.get("symptom")) if isinstance(issue_payload, dict) else "",
                _string_param(target_job.last_error) if target_job is not None else "",
                _string_param(target_job.last_error_type) if target_job is not None else "",
            ]
        ).strip()
        heuristic_decision = _heuristic_runtime_fix_decision(
            kind=(target_job.kind if target_job is not None else _string_param(issue_payload.get("kind")) if isinstance(issue_payload, dict) else ""),
            status=(target_job.status.value if target_job is not None else _string_param(issue_payload.get("status")) if isinstance(issue_payload, dict) else ""),
            error_type=(target_job.last_error_type if target_job is not None else _string_param(issue_payload.get("metadata", {}).get("error_type")) if isinstance(issue_payload, dict) and isinstance(issue_payload.get("metadata"), dict) else ""),
            error=heuristic_error,
        )
        if heuristic_decision is None and reused_downstream is not None:
            heuristic_decision = dict(reused_downstream["decision"])

        gitnexus_payload = _gitnexus_query(query=gitnexus_query or job_id, limit=gitnexus_limit)
        playbook_excerpt = read_text((_REPO_ROOT / "docs" / "repair_agent_playbook.md").resolve(), limit=2_000)
        bootstrap_memory = load_maintagent_bootstrap_memory(max_chars=4_000)
        repo_memory = load_maintagent_repo_memory(max_chars=2_500)
        prompt_context_pack = _compact_context_pack_for_prompt(context_pack)
        prompt_lines: list[str] = []
        prompt_section_stats: list[dict[str, Any]] = []
        prompt_lines.append("You are the incident-scoped repair coordinator for ChatgptREST.")
        prompt_lines.append("")
        prompt_lines.append("Goal: diagnose the current request, preserve lane memory, and choose the next action.")
        prompt_lines.append("")
        prompt_lines.append("Hard constraints:")
        prompt_lines.append("- You are a read-only diagnosis step. Do not edit code in this run.")
        prompt_lines.append("- If a low/medium-risk runtime recovery is enough, choose route=`repair.autofix`.")
        prompt_lines.append("- If the repo needs a code change, choose route=`repair.open_pr` and provide concrete patch instructions.")
        prompt_lines.append("- If evidence is insufficient or human judgment is required, choose route=`manual`.")
        prompt_lines.append("- Return JSON only, matching the provided schema.")
        prompt_lines.append("")
        prompt_lines.append(f"Repo root: {_REPO_ROOT}")
        prompt_lines.append(f"Lane dir: {lane_dir}")
        prompt_lines.append(f"Current job_id: {job_id}")
        prompt_lines.append(f"Current issue_id: {requested_issue_id or ''}")
        prompt_lines.append(f"Current target_job_id: {requested_target_job_id or ''}")
        prompt_lines.append("")

        _append_section_with_stats(
            prompt_lines,
            prompt_section_stats,
            title="Current request",
            body=_json_preview(
                {
                    "job_id": job_id,
                    "lane_id": lane_id,
                    "kind": kind,
                    "input": input_obj,
                    "params": params_obj,
                },
                limit=4_000,
            ),
        )
        _append_section_with_stats(
            prompt_lines,
            prompt_section_stats,
            title="Lane history",
            body=_json_preview(history, limit=3_000),
        )
        if manifest:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Lane manifest",
                body=_json_preview(manifest, limit=2_500),
            )
        _append_section_with_stats(
            prompt_lines,
            prompt_section_stats,
            title="Maintagent bootstrap memory",
            body=truncate_text(str(bootstrap_memory.get("text") or ""), limit=4_000),
        )
        _append_section_with_stats(
            prompt_lines,
            prompt_section_stats,
            title="Maintagent repo memory",
            body=truncate_text(str(repo_memory.get("text") or ""), limit=2_000),
        )
        if issue_payload is not None:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Issue summary",
                body=_json_preview(issue_payload, limit=3_500),
            )
        if issue_events:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Recent issue events",
                body=_json_preview(issue_events, limit=4_000),
            )
        if prompt_context_pack is not None:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Provided context pack",
                body=_json_preview(prompt_context_pack, limit=5_000),
            )
        if target_job_context is not None:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Target job summary",
                body=_json_preview(target_job_context.get("summary"), limit=2_500),
            )
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Target result.json",
                body=truncate_text(str(target_job_context.get("result_json") or ""), limit=2_500),
            )
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Target run_meta.json",
                body=truncate_text(str(target_job_context.get("run_meta_json") or ""), limit=2_500),
            )
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Target events tail",
                body=truncate_text(str(target_job_context.get("events_tail") or ""), limit=2_000),
            )
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="Target answer excerpt",
                body=truncate_text(str(target_job_context.get("answer_text") or ""), limit=2_500),
            )
        if gitnexus_payload:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="GitNexus query result",
                body=_json_preview(gitnexus_payload, limit=4_000),
            )
        if playbook_excerpt:
            _append_section_with_stats(
                prompt_lines,
                prompt_section_stats,
                title="repair_agent_playbook.md excerpt",
                body=truncate_text(playbook_excerpt, limit=1_500),
            )

        prompt = "\n".join(prompt_lines).strip()
        prompt_stats = {
            "prompt_chars": len(prompt),
            "estimated_tokens": max(1, len(prompt) // 4) if prompt else 0,
            "sections": prompt_section_stats,
        }
        requests_dir.mkdir(parents=True, exist_ok=True)
        codex_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        run_kind = _controller_run_kind(
            input_obj=input_obj,
            issue_id=requested_issue_id,
            incident_id=incident_id,
            target_job_id=requested_target_job_id,
        )
        escalation_source = _controller_escalation_source(input_obj=input_obj, incident_id=incident_id)
        operator_attachable = _bool_param(params_obj.get("operator_attachable"), False)
        acceptance_criteria = _controller_acceptance_criteria(input_obj=input_obj, params_obj=params_obj)
        decision_override = _controller_decision_override(params_obj)
        requested_allowed_actions = _normalize_actions_list(params_obj.get("runtime_allow_actions"))
        requested_max_risk = _string_param(params_obj.get("runtime_max_risk"), "low")
        memory_snapshot_path = (
            _string_param((context_pack or {}).get("global_memory_snapshot_path")) if isinstance(context_pack, dict) else ""
        ) or _string_param(bootstrap_memory.get("source_path"))

        atomic_write_json(
            request_path,
            {
                "ts": now_iso(),
                "job_id": job_id,
                "lane_id": lane_id,
                "kind": kind,
                "input": input_obj,
                "params": params_obj,
                "controller": {
                    "kind": "codex_maint",
                    "run_kind": run_kind,
                    "escalation_source": escalation_source,
                    "operator_attachable": operator_attachable,
                    "acceptance_criteria": acceptance_criteria,
                    "allowed_actions": requested_allowed_actions,
                    "max_risk": requested_max_risk,
                    "memory_snapshot_path": memory_snapshot_path or None,
                    "decision_override": decision_override,
                },
                "bootstrap_memory": {
                    "status": bootstrap_memory.get("status"),
                    "source_path": bootstrap_memory.get("source_path"),
                    "generated_at": bootstrap_memory.get("generated_at"),
                    "age_seconds": bootstrap_memory.get("age_seconds"),
                    "stale": bootstrap_memory.get("stale"),
                },
                "repo_memory": {
                    "status": repo_memory.get("status"),
                    "source_path": repo_memory.get("source_path"),
                    "checkout_root": repo_memory.get("checkout_root"),
                    "shared_state_root": repo_memory.get("shared_state_root"),
                    "canonical_docs": repo_memory.get("canonical_docs"),
                    "key_state_paths": repo_memory.get("key_state_paths"),
                },
                "issue_target_resolution": issue_target_resolution,
                "issue": issue_payload,
                "issue_events": issue_events,
                "target_job": target_job_context.get("summary") if target_job_context else None,
                "gitnexus": gitnexus_payload,
                "context_pack": context_pack,
                "prompt_stats": prompt_stats,
            },
        )
        prompt_path.write_text(prompt + "\n", encoding="utf-8")

        use_resume = bool(resume_lane and manifest.get("completed_runs"))
        run_mode = "fresh"
        resume_error: dict[str, Any] | None = None
        if decision_override is not None:
            run_mode = "override"
            prompt_path.write_text(
                "Controller decision override used.\n\n"
                + _json_preview(
                    {
                        "decision": decision_override,
                        "reason": "Upstream maintenance control plane explicitly selected the next route.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            decision = _normalize_decision(decision_override)
        elif heuristic_decision is not None:
            run_mode = "heuristic"
            prompt_path.write_text(
                "Heuristic fast path used.\n\n"
                + _json_preview(
                    {
                        "decision": heuristic_decision,
                        "reason": "Known ChatgptREST runtime failure signature matched before Codex escalation.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            decision = _normalize_decision(heuristic_decision)
        elif use_resume:
            run_mode = "resume"
            result = codex_resume_last_message_json(
                prompt=prompt,
                out_text=resume_out_path,
                model=model,
                timeout_seconds=timeout_seconds,
                cwd=lane_dir,
            )
            if not result.ok:
                resume_error = {
                    "returncode": result.returncode,
                    "error_type": result.error_type,
                    "error": result.error,
                }
                run_mode = "resume_fallback_fresh"
            else:
                decision = _normalize_decision(result.output or {})
        if decision_override is None and heuristic_decision is None and (not use_resume or run_mode == "resume_fallback_fresh"):
            result = codex_exec_with_schema(
                prompt=prompt,
                schema_path=_SCHEMA_PATH,
                out_json=decision_path,
                model=model,
                timeout_seconds=timeout_seconds,
                cd=lane_dir,
                sandbox="read-only",
            )
            if not result.ok:
                raise RuntimeError(str(result.error or result.stderr or "codex exec failed"))
            decision = _normalize_decision(result.output or {})

        downstream: dict[str, Any] | None = None
        target_job_id = requested_target_job_id or (target_job.job_id if target_job is not None else None)
        decision_fingerprint = _decision_hash(decision, lane_id=lane_id, target_job_id=target_job_id)

        with connect(db_path) as conn:
            if decision["route"] == "repair.autofix" and target_job_id and _should_submit_runtime_fix(route_mode):
                if reused_downstream is not None and dict(reused_downstream.get("downstream") or {}).get("kind") == "repair.autofix":
                    downstream = {**dict(reused_downstream["downstream"]), "route_mode": route_mode}
                else:
                    allow_actions = params_obj.get("runtime_allow_actions")
                    if allow_actions is None:
                        allow_actions = decision.get("runtime_fix", {}).get("allow_actions")
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        repair_job = create_repair_autofix_job(
                            conn=conn,
                            artifacts_dir=artifacts_dir,
                            idempotency_key=f"sre-runtime-{lane_id}-{decision_fingerprint}",
                            client_name="sre.fix_request",
                            requested_by=_requested_by_payload(lane_id=lane_id, parent_job_id=job_id),
                            job_id=target_job_id,
                            symptom=(symptom or decision["summary"] or decision["root_cause"]),
                            timeout_seconds=timeout_seconds,
                            model=model,
                            max_risk=_string_param(params_obj.get("runtime_max_risk"), "low"),
                            allow_actions=allow_actions,
                            apply_actions=_bool_param(params_obj.get("runtime_apply_actions"), True),
                        )
                        downstream = {
                            "kind": repair_job.kind,
                            "job_id": repair_job.job_id,
                            "status": repair_job.status.value,
                            "route_mode": route_mode,
                        }
                    except IdempotencyCollision as exc:
                        reused = _reuse_existing_downstream_job(conn, exc=exc, expected_kind="repair.autofix")
                        if reused is None:
                            raise
                        downstream = {**reused, "route_mode": route_mode, "collision": str(exc)}
            elif decision["route"] == "repair.open_pr" and target_job_id and _should_submit_open_pr(route_mode):
                open_pr_obj = decision.get("open_pr") or {}
                open_pr_mode = _string_param(params_obj.get("open_pr_mode"), _string_param(open_pr_obj.get("mode"), "p0"))
                if reused_downstream is not None and dict(reused_downstream.get("downstream") or {}).get("kind") == "repair.open_pr":
                    downstream = {**dict(reused_downstream["downstream"]), "mode": open_pr_mode, "route_mode": route_mode}
                else:
                    open_pr_input = {"job_id": target_job_id}
                    if symptom or decision["summary"]:
                        open_pr_input["symptom"] = symptom or decision["summary"]
                    merged_instructions = _merge_open_pr_instructions(
                        request_instructions=_string_param(instructions),
                        decision_instructions=_string_param(open_pr_obj.get("instructions")),
                    )
                    if merged_instructions:
                        open_pr_input["instructions"] = merged_instructions
                    open_pr_params: dict[str, Any] = {
                        "mode": open_pr_mode,
                        "timeout_seconds": timeout_seconds,
                        "base_ref": "HEAD",
                        "base_branch": "master",
                    }
                    if model:
                        open_pr_params["model"] = model
                    if "open_pr_run_tests" in params_obj:
                        open_pr_params["run_tests"] = bool(params_obj.get("open_pr_run_tests"))
                    elif "run_tests" in open_pr_obj:
                        open_pr_params["run_tests"] = bool(open_pr_obj.get("run_tests"))
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        pr_job = job_store.create_job(
                            conn,
                            artifacts_dir=artifacts_dir,
                            idempotency_key=f"sre-open-pr-{lane_id}-{decision_fingerprint}",
                            kind="repair.open_pr",
                            input=open_pr_input,
                            params=open_pr_params,
                            max_attempts=1,
                            parent_job_id=job_id,
                            client={"name": "sre.fix_request"},
                            requested_by=_requested_by_payload(lane_id=lane_id, parent_job_id=job_id),
                            enforce_conversation_single_flight=False,
                        )
                        downstream = {
                            "kind": pr_job.kind,
                            "job_id": pr_job.job_id,
                            "status": pr_job.status.value,
                            "mode": open_pr_mode,
                            "route_mode": route_mode,
                        }
                    except IdempotencyCollision as exc:
                        reused = _reuse_existing_downstream_job(conn, exc=exc, expected_kind="repair.open_pr")
                        if reused is None:
                            raise
                        downstream = {**reused, "mode": open_pr_mode, "route_mode": route_mode, "collision": str(exc)}
            if requested_issue_id:
                if report_path is None:
                    report_ref = ""
                else:
                    try:
                        report_ref = report_path.relative_to(artifacts_dir).as_posix()
                    except ValueError:
                        report_ref = report_path.as_posix()
                if conn.in_transaction is False:
                    conn.execute("BEGIN IMMEDIATE")
                client_issues.link_issue_evidence(
                    conn,
                    issue_id=requested_issue_id,
                    artifacts_path=report_ref,
                    note=f"sre.fix_request lane={lane_id} route={decision['route']}",
                    metadata={
                        "evidence_job_id": job_id,
                        "lane_id": lane_id,
                        "route": decision["route"],
                        "downstream": downstream,
                    },
                )
                conn.commit()

        atomic_write_json(decision_path, decision)
        effective_allowed_actions = _normalize_actions_list(
            decision.get("runtime_fix", {}).get("allow_actions") or params_obj.get("runtime_allow_actions")
        )
        effective_max_risk = _string_param(
            decision.get("runtime_fix", {}).get("max_risk"),
            _string_param(params_obj.get("runtime_max_risk"), "low"),
        )
        target_conversation_url = None
        if isinstance(target_job_context, dict) and isinstance(target_job_context.get("summary"), dict):
            target_conversation_url = _string_param(target_job_context["summary"].get("conversation_url")) or None
        taskpack_paths = _write_taskpack_projection(
            lane_dir=lane_dir,
            lane_id=lane_id,
            run_kind=run_kind,
            escalation_source=escalation_source,
            issue_id=requested_issue_id,
            incident_id=incident_id,
            target_job_id=target_job_id,
            target_conversation_url=target_conversation_url,
            symptom=symptom,
            context_pack=context_pack,
            prompt=prompt,
            memory_snapshot_path=memory_snapshot_path or None,
            allowed_actions=effective_allowed_actions,
            max_risk=effective_max_risk,
            acceptance_criteria=acceptance_criteria,
            resume_allowed=bool(resume_lane),
            operator_attachable=operator_attachable,
            runbook_excerpt=playbook_excerpt,
        )
        controller_phase = _controller_phase(decision=decision, downstream=downstream)
        operator_attach = _operator_attach_payload(lane_id=lane_id, lane_dir=lane_dir)
        final_report_path = report_path or (reports_dir / f"{request_basename}.report.json")
        report = {
            "ts": now_iso(),
            "job_id": job_id,
            "kind": kind,
            "lane_id": lane_id,
            "runner_mode": run_mode,
            "resume_error": resume_error,
            "timeout_seconds": timeout_seconds,
            "issue_id": requested_issue_id,
            "incident_id": incident_id,
            "issue_target_resolution": issue_target_resolution,
            "target_job_id": target_job_id,
            "route_mode": route_mode,
            "context_pack": context_pack,
            "decision": decision,
            "downstream": downstream,
            "request_path": request_path.as_posix(),
            "prompt_path": prompt_path.as_posix(),
            "decision_path": decision_path.as_posix(),
            "lane_dir": lane_dir.as_posix(),
            "lane_manifest_path": manifest_path.as_posix(),
            "task_pack_projection_path": taskpack_paths["dir"],
            "taskpack": taskpack_paths,
            "gitnexus": gitnexus_payload,
            "prompt_stats": prompt_stats,
            "controller": {
                "kind": "codex_maint",
                "phase": controller_phase,
                "run_kind": run_kind,
                "escalation_source": escalation_source,
                "operator_attachable": operator_attachable,
                "last_resume_mode": run_mode if run_mode.startswith("resume") else None,
                "decision_source": run_mode,
                "current_downstream_kind": downstream.get("kind") if downstream else None,
                "current_downstream_job_id": downstream.get("job_id") if downstream else None,
                "memory_snapshot_path": memory_snapshot_path or None,
                "acceptance_criteria": acceptance_criteria,
                "allowed_actions": effective_allowed_actions,
                "max_risk": effective_max_risk,
                "operator_attach": operator_attach,
            },
            "repo": {
                "root": _REPO_ROOT.as_posix(),
                "git_head": _git_cmd("rev-parse", "HEAD"),
                "git_branch": _git_cmd("rev-parse", "--abbrev-ref", "HEAD"),
            },
        }
        atomic_write_json(final_report_path, report)
        manifest_update = dict(manifest)
        manifest_update.update(
            {
                "lane_id": lane_id,
                "completed_runs": int(manifest.get("completed_runs") or 0) + 1,
                "last_job_id": job_id,
                "last_issue_id": requested_issue_id,
                "last_incident_id": incident_id,
                "last_target_job_id": target_job_id,
                "last_route": decision["route"],
                "last_runner_mode": run_mode,
                "last_report_path": final_report_path.as_posix(),
                "updated_at": now_iso(),
                "controller_kind": "codex_maint",
                "controller_phase": controller_phase,
                "run_kind": run_kind,
                "escalation_source": escalation_source,
                "operator_attachable": operator_attachable,
                "last_resume_mode": run_mode if run_mode.startswith("resume") else None,
                "last_decision_source": run_mode,
                "current_downstream_kind": downstream.get("kind") if downstream else None,
                "current_downstream_job_id": downstream.get("job_id") if downstream else None,
                "memory_snapshot_path": memory_snapshot_path or None,
                "task_pack_projection_path": taskpack_paths["dir"],
                "operator_attach_command": " ".join(operator_attach["argv"]),
            }
        )
        atomic_write_json(manifest_path, manifest_update)
        _append_history(
            history_path,
            {
                "ts": report["ts"],
                "job_id": job_id,
                "route": decision["route"],
                "confidence": decision["confidence"],
                "summary": decision["summary"],
                "downstream": downstream,
                "controller_phase": controller_phase,
            },
        )

    return {
        "report": report,
        "decision": decision,
        "downstream": downstream,
        "run_mode": run_mode,
        "lane_id": lane_id,
        "lane_dir": lane_dir.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "history_path": history_path.as_posix(),
        "request_path": request_path.as_posix(),
        "prompt_path": prompt_path.as_posix(),
        "decision_path": decision_path.as_posix(),
        "report_path": final_report_path.as_posix(),
        "taskpack": taskpack_paths,
    }


class SreFixRequestExecutor(BaseExecutor):
    def __init__(self, *, cfg: AppConfig) -> None:
        self._cfg = cfg

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        if kind not in {"sre.fix_request", "sre.diagnose"}:
            return ExecutorResult(status="error", answer=f"Unknown kind: {kind}", meta={"error_type": "ValueError"})
        report_relpath = _job_relpath(job_id, "sre_fix_report.json")
        report_path = (self._cfg.artifacts_dir / report_relpath).resolve()
        try:
            controller = execute_sre_fix_request_controller(
                db_path=self._cfg.db_path,
                artifacts_dir=self._cfg.artifacts_dir,
                request_job_id=job_id,
                kind=kind,
                input_obj=input,
                params_obj=params,
                report_path=report_path,
            )
        except KeyError as exc:
            return ExecutorResult(status="error", answer=str(exc), meta={"error_type": "KeyError"})
        except ValueError as exc:
            return ExecutorResult(status="error", answer=str(exc), meta={"error_type": "ValueError"})
        except RuntimeError as exc:
            return ExecutorResult(status="error", answer=str(exc), meta={"error_type": "RuntimeError"})

        report = dict(controller["report"])
        decision = dict(controller["decision"])
        downstream = controller.get("downstream")
        gitnexus_payload = dict(report.get("gitnexus") or {})
        run_mode = str(controller.get("run_mode") or "")
        lane_id = str(controller.get("lane_id") or "")
        requested_issue_id = _string_param(report.get("issue_id")) or None
        incident_id = _string_param(report.get("incident_id")) or None
        target_job_id = _string_param(report.get("target_job_id")) or None
        route_mode = _string_param(report.get("route_mode"))

        lines: list[str] = []
        lines.append("# sre.fix_request report")
        lines.append("")
        lines.append(f"- request_job_id: `{job_id}`")
        lines.append(f"- lane_id: `{lane_id}`")
        lines.append(f"- runner_mode: `{run_mode}`")
        lines.append(f"- report_path: `{report_relpath}`")
        if requested_issue_id:
            lines.append(f"- issue_id: `{requested_issue_id}`")
        if incident_id:
            lines.append(f"- incident_id: `{incident_id}`")
        if target_job_id:
            lines.append(f"- target_job_id: `{target_job_id}`")
        lines.append("")
        lines.append("## Decision")
        lines.append(f"- route: `{decision['route']}`")
        lines.append(f"- confidence: `{decision['confidence']}`")
        lines.append(f"- summary: {decision['summary']}")
        lines.append(f"- root_cause: {decision['root_cause']}")
        lines.append(f"- rationale: {decision['rationale']}")
        if decision["recommended_actions"]:
            for item in decision["recommended_actions"]:
                lines.append(f"- action: {item}")
        lines.append("")
        lines.append("## Routing")
        lines.append(f"- route_mode: `{route_mode}`")
        if downstream is None:
            lines.append("- downstream: none")
        else:
            lines.append(f"- downstream_kind: `{downstream.get('kind')}`")
            lines.append(f"- downstream_job_id: `{downstream.get('job_id')}`")
            lines.append(f"- downstream_status: `{downstream.get('status')}`")
            if downstream.get("mode"):
                lines.append(f"- downstream_mode: `{downstream.get('mode')}`")
        lines.append("")
        lines.append("## GitNexus")
        lines.append(f"- enabled: `{bool(gitnexus_payload.get('enabled'))}` ok=`{bool(gitnexus_payload.get('ok'))}`")
        if gitnexus_payload.get("query"):
            lines.append(f"- query: {gitnexus_payload.get('query')}")
        if gitnexus_payload.get("error"):
            lines.append(f"- error: {gitnexus_payload.get('error')}")
        if gitnexus_payload.get("reason"):
            lines.append(f"- reason: {gitnexus_payload.get('reason')}")
        if gitnexus_payload.get("markdown"):
            lines.append("")
            lines.append("```text")
            lines.append(str(gitnexus_payload.get("markdown")))
            lines.append("```")
        if decision["notes"]:
            lines.append("")
            lines.append("## Notes")
            for item in decision["notes"]:
                lines.append(f"- {item}")

        meta = {
            "lane_id": lane_id,
            "runner_mode": run_mode,
            "route": decision["route"],
            "confidence": decision["confidence"],
            "report_path": report_relpath,
            "downstream": downstream,
            "issue_id": requested_issue_id,
            "target_job_id": target_job_id,
            "controller": report.get("controller"),
            "taskpack": report.get("taskpack"),
        }
        return ExecutorResult(status="completed", answer="\n".join(lines), answer_format="markdown", meta=meta)
