"""Behavior-driven issue detection and closed-loop promotion for maint_daemon.

This module intentionally stays out of the hot path.  It mines recent jobs and
events in the maint daemon, then promotes high-confidence behavior patterns into:

behavior signal -> incident -> issue ledger -> sre.fix_request
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues
from chatgptrest.core import incidents as incident_db
from chatgptrest.core.completion_contract import (
    canonical_answer_from_job_like,
    completion_contract_from_job_like,
)
from chatgptrest.core.sre_jobs import create_sre_fix_request_job, requested_by_transport
from chatgptrest.ops_shared.infra import atomic_write_json, truncate_text
from chatgptrest.ops_shared.subsystem import Observation, TickContext
from chatgptrest.providers.registry import is_web_ask_kind, provider_id_for_kind

logger = logging.getLogger("maint.behavior_issues")

_PROMPT_FIELD_CANDIDATES = (
    "question",
    "text",
    "message",
    "prompt",
    "raw_question",
    "query",
)
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\u3000，。！？；：、“”‘’,.!?;:()\[\]{}<>\"'`]+")
_CJK_OR_ALPHA_RE = re.compile(r"[\u4e00-\u9fffA-Za-z]")
_INCIDENT_REL_RE = re.compile(r"^monitor/maint_daemon/incidents/([^/]+)/summary\.md$")


@dataclass(frozen=True)
class BehaviorIssueCandidate:
    detector_id: str
    provider: str
    kind: str
    title: str
    severity: str
    symptom: str
    issue_fingerprint: str
    incident_signature: str
    instructions: str
    primary_job_id: str | None
    conversation_url: str | None
    sample_job_ids: list[str] = field(default_factory=list)
    sample_prompts: list[str] = field(default_factory=list)
    sample_clients: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _JobSnapshot:
    job_id: str
    kind: str
    provider: str
    status: str
    created_at: float
    updated_at: float
    parent_job_id: str | None
    conversation_url: str | None
    conversation_id: str | None
    prompt_text: str
    prompt_hash: str
    client_name: str
    answer_chars: int | None
    params: dict[str, Any]


def _loads_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(str(raw))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _normalize_prompt_text(text: str | None) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    raw = _PUNCT_RE.sub(" ", raw)
    raw = _WS_RE.sub(" ", raw).strip()
    return raw


def _is_human_prompt(text: str) -> bool:
    if len(text) < 8:
        return False
    return bool(_CJK_OR_ALPHA_RE.search(text))


def _extract_prompt_text(input_payload: dict[str, Any]) -> str:
    for key in _PROMPT_FIELD_CANDIDATES:
        value = input_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _prompt_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(str(text).encode("utf-8", errors="replace")).hexdigest()[:16]


def _client_name(client_payload: dict[str, Any]) -> str:
    for key in ("name", "project", "client_name"):
        value = client_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _bool_param(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _deep_research_enabled(params: dict[str, Any]) -> bool:
    if _bool_param(params.get("deep_research")):
        return True
    preset = str(params.get("preset") or "").strip().lower()
    return preset in {"deep_research", "research"}


def _recent_jobs(conn: Any, *, since_ts: float, limit: int) -> list[_JobSnapshot]:
    rows = conn.execute(
        """
        SELECT job_id, kind, status, created_at, updated_at, parent_job_id,
               conversation_url, conversation_id, input_json, params_json,
               client_json, answer_chars
        FROM jobs
        WHERE (updated_at >= ? OR created_at >= ?)
        ORDER BY created_at ASC, job_id ASC
        LIMIT ?
        """,
        (float(since_ts), float(since_ts), int(max(1, limit))),
    ).fetchall()
    out: list[_JobSnapshot] = []
    for row in rows:
        kind = str(row["kind"] or "").strip()
        if not is_web_ask_kind(kind):
            continue
        input_payload = _loads_dict(str(row["input_json"]) if row["input_json"] is not None else None)
        prompt_raw = _extract_prompt_text(input_payload)
        prompt_norm = _normalize_prompt_text(prompt_raw)
        params = _loads_dict(str(row["params_json"]) if row["params_json"] is not None else None)
        client = _loads_dict(str(row["client_json"]) if row["client_json"] is not None else None)
        out.append(
            _JobSnapshot(
                job_id=str(row["job_id"] or "").strip(),
                kind=kind,
                provider=(provider_id_for_kind(kind) or "unknown"),
                status=str(row["status"] or "").strip(),
                created_at=float(row["created_at"] or 0.0),
                updated_at=float(row["updated_at"] or 0.0),
                parent_job_id=(str(row["parent_job_id"]).strip() if row["parent_job_id"] is not None else None) or None,
                conversation_url=(str(row["conversation_url"]).strip() if row["conversation_url"] is not None else None) or None,
                conversation_id=(str(row["conversation_id"]).strip() if row["conversation_id"] is not None else None) or None,
                prompt_text=prompt_raw,
                prompt_hash=_prompt_hash(prompt_norm) if prompt_norm else "",
                client_name=_client_name(client),
                answer_chars=(int(row["answer_chars"]) if row["answer_chars"] is not None else None),
                params=params,
            )
        )
    return out


def _load_job_result_payload(*, artifacts_dir: Path | None, job_id: str) -> dict[str, Any] | None:
    if artifacts_dir is None:
        return None
    result_path = artifacts_dir / "jobs" / str(job_id) / "result.json"
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _job_like_with_result(job: _JobSnapshot, result_payload: dict[str, Any] | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "answer_chars": job.answer_chars,
        "params_json": job.params,
    }
    if isinstance(result_payload, dict):
        data.update(result_payload)
    return data


def _recent_event_types(conn: Any, *, job_ids: list[str], since_ts: float) -> dict[str, set[str]]:
    if not job_ids:
        return {}
    out: dict[str, set[str]] = {}
    chunk_size = 200
    for idx in range(0, len(job_ids), chunk_size):
        chunk = job_ids[idx : idx + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""
            SELECT job_id, type
            FROM job_events
            WHERE ts >= ?
              AND job_id IN ({placeholders})
            """,
            (float(since_ts), *chunk),
        ).fetchall()
        for row in rows:
            job_id = str(row["job_id"] or "").strip()
            event_type = str(row["type"] or "").strip()
            if not job_id or not event_type:
                continue
            out.setdefault(job_id, set()).add(event_type)
    return out


def _is_short_completion(
    job: _JobSnapshot,
    *,
    event_types: set[str],
    short_answer_chars_max: int,
    result_payload: dict[str, Any] | None = None,
) -> bool:
    if job.status != "completed":
        return False
    job_like = _job_like_with_result(job, result_payload)
    contract = completion_contract_from_job_like(job_like)
    if str(contract.get("answer_state") or "").strip().lower() != "final":
        return True
    if "completion_guard_completed_under_min_chars" in event_types:
        return True
    canonical_answer = canonical_answer_from_job_like(job_like)
    chars = int(canonical_answer.get("answer_chars") or job.answer_chars or 0)
    return 0 < chars <= int(max(1, short_answer_chars_max))


def _sampled(values: list[str], *, limit: int = 4) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw = str(value or "").strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
        if len(out) >= int(limit):
            break
    return out


def _detect_completed_short_resubmit(
    jobs: list[_JobSnapshot],
    *,
    artifacts_dir: Path | None,
    event_types_by_job: dict[str, set[str]],
    short_answer_chars_max: int,
    resubmit_window_seconds: int,
    min_occurrences: int,
) -> list[BehaviorIssueCandidate]:
    by_key: dict[tuple[str, str, str], list[_JobSnapshot]] = {}
    for job in jobs:
        if not job.prompt_hash or not _is_human_prompt(job.prompt_text):
            continue
        by_key.setdefault((job.kind, job.client_name, job.prompt_hash), []).append(job)

    occurrences: list[dict[str, Any]] = []
    for sequence in by_key.values():
        sequence.sort(key=lambda item: (item.created_at, item.job_id))
        for first, second in zip(sequence, sequence[1:]):
            first_result_payload = _load_job_result_payload(artifacts_dir=artifacts_dir, job_id=first.job_id)
            if not _is_short_completion(
                first,
                event_types=event_types_by_job.get(first.job_id, set()),
                short_answer_chars_max=short_answer_chars_max,
                result_payload=first_result_payload,
            ):
                continue
            if second.created_at <= first.updated_at:
                continue
            if (second.created_at - first.updated_at) > float(max(30, int(resubmit_window_seconds))):
                continue
            if second.status == "canceled":
                continue
            occurrences.append(
                {
                    "provider": first.provider,
                    "kind": first.kind,
                    "client_name": first.client_name,
                    "prompt_text": first.prompt_text,
                    "job_ids": [first.job_id, second.job_id],
                    "conversation_url": second.conversation_url or first.conversation_url,
                    "answer_chars": int(first.answer_chars or 0),
                }
            )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for occ in occurrences:
        grouped.setdefault((str(occ["provider"]), str(occ["kind"])), []).append(occ)

    out: list[BehaviorIssueCandidate] = []
    for (provider, kind), occs in grouped.items():
        if len(occs) < int(max(1, min_occurrences)):
            continue
        prompt_examples = _sampled([str(x["prompt_text"]) for x in occs], limit=2)
        sample_job_ids = _sampled([jid for x in occs for jid in x["job_ids"]], limit=6)
        sample_clients = _sampled([str(x["client_name"]) for x in occs], limit=4)
        title = f"Behavior detector: repeated short completions trigger human resubmits on {kind}"
        symptom = (
            f"Detected {len(occs)} human re-submit patterns on {kind}: a job completed with a very short answer "
            f"and the same client quickly asked the same question again."
        )
        out.append(
            BehaviorIssueCandidate(
                detector_id="completed_short_resubmit",
                provider=provider,
                kind=kind,
                title=title,
                severity="P1",
                symptom=symptom,
                issue_fingerprint=f"behavior:completed_short_resubmit:{provider}:{kind}:v1",
                incident_signature=f"behavior:completed_short_resubmit:{provider}:{kind}",
                instructions=(
                    "Investigate why human-language prompts are reaching completed with very short answers, then "
                    "being resubmitted. Check completion classification, answer guard thresholds, and result/export "
                    "reconciliation for false-positive completion."
                ),
                primary_job_id=(sample_job_ids[-1] if sample_job_ids else None),
                conversation_url=(str(occs[-1]["conversation_url"]) if occs and occs[-1].get("conversation_url") else None),
                sample_job_ids=sample_job_ids,
                sample_prompts=prompt_examples,
                sample_clients=sample_clients,
                metadata={
                    "occurrences": len(occs),
                    "short_answer_chars_max": int(short_answer_chars_max),
                },
            )
        )
    return out


def _followup_group_key(job: _JobSnapshot, *, by_job_id: dict[str, _JobSnapshot]) -> str | None:
    if job.conversation_id:
        return f"conversation_id:{job.conversation_id}"
    if job.conversation_url:
        return f"conversation_url:{job.conversation_url}"
    current = job
    visited: set[str] = set()
    while current.parent_job_id:
        parent_id = str(current.parent_job_id)
        if parent_id in visited:
            break
        visited.add(parent_id)
        parent = by_job_id.get(parent_id)
        if parent is None:
            return f"parent_job_id:{parent_id}"
        if parent.conversation_id:
            return f"conversation_id:{parent.conversation_id}"
        if parent.conversation_url:
            return f"conversation_url:{parent.conversation_url}"
        current = parent
    if job.parent_job_id:
        return f"parent_job_id:{job.parent_job_id}"
    return None


def _detect_needs_followup_loop_exhaustion(
    jobs: list[_JobSnapshot],
    *,
    min_chain: int,
) -> list[BehaviorIssueCandidate]:
    by_job_id = {job.job_id: job for job in jobs}
    groups: dict[tuple[str, str, str], list[_JobSnapshot]] = {}
    for job in jobs:
        if job.status != "needs_followup":
            continue
        key = _followup_group_key(job, by_job_id=by_job_id)
        if not key:
            continue
        groups.setdefault((job.provider, job.kind, key), []).append(job)

    grouped_occurrences: dict[tuple[str, str], list[list[_JobSnapshot]]] = {}
    for (provider, kind, _group_key), chain in groups.items():
        chain.sort(key=lambda item: (item.created_at, item.job_id))
        if len(chain) < int(max(2, min_chain)):
            continue
        grouped_occurrences.setdefault((provider, kind), []).append(chain)

    out: list[BehaviorIssueCandidate] = []
    for (provider, kind), chains in grouped_occurrences.items():
        sample_job_ids = _sampled([job.job_id for chain in chains for job in chain], limit=8)
        prompt_examples = _sampled([job.prompt_text for chain in chains for job in chain if job.prompt_text], limit=2)
        sample_clients = _sampled([job.client_name for chain in chains for job in chain], limit=4)
        longest_chain = max(len(chain) for chain in chains)
        out.append(
            BehaviorIssueCandidate(
                detector_id="needs_followup_loop_exhaustion",
                provider=provider,
                kind=kind,
                title=f"Behavior detector: needs_followup loops exhaust human retries on {kind}",
                severity="P1",
                symptom=(
                    f"Detected {len(chains)} conversation chains on {kind} that cycled into needs_followup "
                    f"at least {min_chain} times without converging."
                ),
                issue_fingerprint=f"behavior:needs_followup_loop_exhaustion:{provider}:{kind}:v1",
                incident_signature=f"behavior:needs_followup_loop_exhaustion:{provider}:{kind}",
                instructions=(
                    "Investigate why follow-up chains are not progressing to a final answer. Check provider-specific "
                    "follow-up prompts, send/wait transitions, and whether UI or classification logic is trapping "
                    "the chain in repeated needs_followup states."
                ),
                primary_job_id=(sample_job_ids[-1] if sample_job_ids else None),
                conversation_url=(chains[-1][-1].conversation_url if chains and chains[-1] else None),
                sample_job_ids=sample_job_ids,
                sample_prompts=prompt_examples,
                sample_clients=sample_clients,
                metadata={
                    "chains": len(chains),
                    "longest_chain": longest_chain,
                    "min_chain": int(min_chain),
                },
            )
        )
    return out


def _detect_dr_followup_progression_failure(jobs: list[_JobSnapshot]) -> list[BehaviorIssueCandidate]:
    by_job_id = {job.job_id: job for job in jobs}
    grouped: dict[tuple[str, str], list[tuple[_JobSnapshot, _JobSnapshot]]] = {}
    for child in jobs:
        if not child.parent_job_id:
            continue
        parent = by_job_id.get(str(child.parent_job_id))
        if parent is None:
            continue
        if parent.kind != child.kind:
            continue
        if not _deep_research_enabled(parent.params):
            continue
        if parent.status != "needs_followup":
            continue
        if _deep_research_enabled(child.params):
            continue
        grouped.setdefault((child.provider, child.kind), []).append((parent, child))

    out: list[BehaviorIssueCandidate] = []
    for (provider, kind), pairs in grouped.items():
        sample_job_ids = _sampled([job.job_id for pair in pairs for job in pair], limit=6)
        prompt_examples = _sampled([pair[1].prompt_text or pair[0].prompt_text for pair in pairs], limit=2)
        sample_clients = _sampled([pair[1].client_name for pair in pairs], limit=4)
        out.append(
            BehaviorIssueCandidate(
                detector_id="dr_followup_progression_failure",
                provider=provider,
                kind=kind,
                title=f"Behavior detector: Deep Research follow-ups lose DR intent on {kind}",
                severity="P0",
                symptom=(
                    f"Detected {len(pairs)} Deep Research follow-ups on {kind} where the parent asked for DR, "
                    "the parent ended in needs_followup, and the child no longer carried DR intent."
                ),
                issue_fingerprint=f"behavior:dr_followup_progression_failure:{provider}:{kind}:v1",
                incident_signature=f"behavior:dr_followup_progression_failure:{provider}:{kind}",
                instructions=(
                    "Investigate the follow-up creation path for Deep Research requests. Parent DR intent must survive "
                    "needs_followup transitions into child jobs unless the client explicitly disabled it."
                ),
                primary_job_id=(sample_job_ids[-1] if sample_job_ids else None),
                conversation_url=(pairs[-1][1].conversation_url if pairs else None),
                sample_job_ids=sample_job_ids,
                sample_prompts=prompt_examples,
                sample_clients=sample_clients,
                metadata={"occurrences": len(pairs)},
            )
        )
    return out


def detect_behavior_issue_candidates(
    conn: Any,
    *,
    now: float,
    artifacts_dir: Path | None = None,
    lookback_seconds: int = 7200,
    jobs_limit: int = 1200,
    short_answer_chars_max: int = 120,
    short_resubmit_window_seconds: int = 900,
    short_resubmit_min_occurrences: int = 2,
    needs_followup_min_chain: int = 3,
) -> list[BehaviorIssueCandidate]:
    since_ts = float(now) - float(max(300, int(lookback_seconds)))
    jobs = _recent_jobs(conn, since_ts=since_ts, limit=max(50, int(jobs_limit)))
    if not jobs:
        return []
    event_types_by_job = _recent_event_types(conn, job_ids=[job.job_id for job in jobs], since_ts=since_ts)
    candidates = [
        *_detect_completed_short_resubmit(
            jobs,
            artifacts_dir=artifacts_dir,
            event_types_by_job=event_types_by_job,
            short_answer_chars_max=int(short_answer_chars_max),
            resubmit_window_seconds=int(short_resubmit_window_seconds),
            min_occurrences=int(short_resubmit_min_occurrences),
        ),
        *_detect_needs_followup_loop_exhaustion(
            jobs,
            min_chain=int(needs_followup_min_chain),
        ),
        *_detect_dr_followup_progression_failure(jobs),
    ]
    severity_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(
        candidates,
        key=lambda item: (
            severity_rank.get(str(item.severity).upper(), 9),
            item.detector_id,
            item.kind,
        ),
    )


def _incident_id_from_artifacts_path(artifacts_path: str | None) -> str | None:
    raw = str(artifacts_path or "").strip()
    if not raw:
        return None
    match = _INCIDENT_REL_RE.match(raw)
    if not match:
        return None
    incident_id = str(match.group(1) or "").strip()
    return incident_id or None


def _summary_rel_path(*, incident_id: str) -> str:
    return str((Path("monitor") / "maint_daemon" / "incidents" / incident_id / "summary.md").as_posix())


def _copy_job_evidence(*, artifacts_dir: Path, inc_dir: Path, job_id: str, conn: Any) -> None:
    job_pack_dir = inc_dir / "jobs" / job_id
    job_pack_dir.mkdir(parents=True, exist_ok=True)
    job_art_dir = artifacts_dir / "jobs" / job_id
    for name in ("request.json", "events.jsonl", "result.json", "answer.md", "answer.txt", "conversation.json"):
        src = job_art_dir / name
        if src.exists():
            dst = job_pack_dir / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
    row = conn.execute(
        """
        SELECT job_id, kind, status, created_at, updated_at, parent_job_id,
               conversation_url, conversation_id, last_error_type, last_error, answer_chars
        FROM jobs
        WHERE job_id = ?
        """,
        (str(job_id),),
    ).fetchone()
    if row is None:
        return
    result_payload = _load_job_result_payload(artifacts_dir=artifacts_dir, job_id=job_id)
    job_like = dict(result_payload) if isinstance(result_payload, dict) else {}
    if not job_like:
        job_like = {
            "job_id": str(row["job_id"] or ""),
            "kind": str(row["kind"] or ""),
            "status": str(row["status"] or ""),
            "answer_chars": (int(row["answer_chars"]) if row["answer_chars"] is not None else None),
        }
    atomic_write_json(
        job_pack_dir / "job_row.json",
        {
            "job_id": str(row["job_id"] or ""),
            "kind": str(row["kind"] or ""),
            "status": str(row["status"] or ""),
            "created_at": float(row["created_at"] or 0.0),
            "updated_at": float(row["updated_at"] or 0.0),
            "parent_job_id": (str(row["parent_job_id"]).strip() if row["parent_job_id"] is not None else None),
            "conversation_url": (str(row["conversation_url"]).strip() if row["conversation_url"] is not None else None),
            "conversation_id": (str(row["conversation_id"]).strip() if row["conversation_id"] is not None else None),
            "last_error_type": (str(row["last_error_type"]).strip() if row["last_error_type"] is not None else None),
            "last_error": (str(row["last_error"]).strip() if row["last_error"] is not None else None),
            "answer_chars": (int(row["answer_chars"]) if row["answer_chars"] is not None else None),
            "completion_contract": completion_contract_from_job_like(job_like),
            "canonical_answer": canonical_answer_from_job_like(job_like),
        },
    )


def _write_incident_summary(
    *,
    inc_dir: Path,
    candidate: BehaviorIssueCandidate,
    issue_id: str,
    incident_id: str,
    fix_job_id: str | None,
) -> None:
    lines: list[str] = []
    lines.append("# Behavior Issue Incident")
    lines.append("")
    lines.append(f"- incident_id: `{incident_id}`")
    lines.append(f"- issue_id: `{issue_id}`")
    lines.append(f"- detector_id: `{candidate.detector_id}`")
    lines.append(f"- severity: `{candidate.severity}`")
    lines.append(f"- provider: `{candidate.provider}`")
    lines.append(f"- kind: `{candidate.kind}`")
    if fix_job_id:
        lines.append(f"- sre_fix_request_job_id: `{fix_job_id}`")
    lines.append("")
    lines.append("## Symptom")
    lines.append(candidate.symptom)
    lines.append("")
    lines.append("## Suggested investigation")
    lines.append(candidate.instructions)
    lines.append("")
    if candidate.sample_prompts:
        lines.append("## Human-language prompt samples")
        for prompt in candidate.sample_prompts:
            lines.append(f"- {truncate_text(prompt, limit=300)}")
        lines.append("")
    if candidate.sample_job_ids:
        lines.append("## Sample job ids")
        for job_id in candidate.sample_job_ids:
            lines.append(f"- `{job_id}`")
        lines.append("")
    if candidate.sample_clients:
        lines.append("## Client samples")
        for client_name in candidate.sample_clients:
            lines.append(f"- `{client_name}`")
        lines.append("")
    (inc_dir / "summary.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


class BehaviorIssueSubsystem:
    """Promote high-confidence client behavior patterns into issue ledger entries."""

    name = "behavior_issues"
    interval_seconds = 60.0

    def __init__(self, *, interval_seconds: float = 60.0) -> None:
        self.interval_seconds = max(10.0, float(interval_seconds))

    def tick(self, ctx: TickContext) -> list[Observation]:
        conn = ctx.conn
        if conn is None:
            return []
        state = ctx.state
        if not bool(state.get("enable_behavior_issue_detection", False)):
            return []

        candidates = detect_behavior_issue_candidates(
            conn,
            now=float(ctx.now),
            artifacts_dir=Path(state["artifacts_dir"]),
            lookback_seconds=int(state.get("behavior_issue_lookback_seconds", 7200)),
            jobs_limit=int(state.get("behavior_issue_jobs_limit", 1200)),
            short_answer_chars_max=int(state.get("behavior_short_answer_chars_max", 120)),
            short_resubmit_window_seconds=int(state.get("behavior_short_resubmit_window_seconds", 900)),
            short_resubmit_min_occurrences=int(state.get("behavior_short_resubmit_min_occurrences", 2)),
            needs_followup_min_chain=int(state.get("behavior_needs_followup_min_chain", 3)),
        )

        observations: list[Observation] = []
        max_promotions = max(1, int(state.get("behavior_issue_max_promotions_per_tick", 8)))
        for candidate in candidates[:max_promotions]:
            try:
                managed_tx = not bool(getattr(conn, "in_transaction", False))
                if managed_tx:
                    conn.execute("BEGIN IMMEDIATE")
                try:
                    observations.extend(self._promote_candidate(ctx, candidate))
                    if managed_tx:
                        conn.commit()
                except Exception:
                    if managed_tx:
                        conn.rollback()
                    raise
            except Exception as exc:  # pragma: no cover - fault isolation at runner level; keep per-candidate detail too.
                logger.exception("behavior issue promotion failed")
                observations.append(
                    Observation(
                        subsystem=self.name,
                        kind="error",
                        data={
                            "type": "behavior_issue_promotion_error",
                            "detector_id": candidate.detector_id,
                            "kind": candidate.kind,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:800],
                        },
                    )
                )

        try:
            managed_tx = not bool(getattr(conn, "in_transaction", False))
            if managed_tx:
                conn.execute("BEGIN IMMEDIATE")
            try:
                observations.extend(self._auto_mitigate(ctx))
                if managed_tx:
                    conn.commit()
            except Exception:
                if managed_tx:
                    conn.rollback()
                raise
        except Exception as exc:  # pragma: no cover
            logger.exception("behavior issue auto-mitigate failed")
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="error",
                    data={
                        "type": "behavior_issue_auto_mitigate_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:800],
                    },
                )
            )
        return observations

    def _promote_candidate(self, ctx: TickContext, candidate: BehaviorIssueCandidate) -> list[Observation]:
        conn = ctx.conn
        assert conn is not None
        state = ctx.state
        monitor_dir = Path(state["monitor_dir"])
        artifacts_dir = Path(state["artifacts_dir"])
        dedupe_seconds = float(max(60, int(state.get("dedupe_seconds", 1800))))
        fingerprint = incident_db.fingerprint_hash(candidate.incident_signature)
        existing = incident_db.find_active_incident(
            conn,
            fingerprint=fingerprint,
            now=float(ctx.now),
            dedupe_seconds=dedupe_seconds,
        )
        fresh_job_ids = list(candidate.sample_job_ids)
        if existing is None:
            incident_id = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z_{incident_db.fingerprint_short(candidate.incident_signature)}"
            incident = incident_db.create_incident(
                conn,
                incident_id=incident_id,
                fingerprint=fingerprint,
                signature=candidate.incident_signature,
                category="behavior",
                severity=candidate.severity,
                now=float(ctx.now),
                job_ids=list(candidate.sample_job_ids),
                evidence_dir=str((monitor_dir / "incidents" / incident_id).resolve(strict=False)),
            )
            is_new_incident = True
        else:
            seen_job_ids = set(existing.job_ids or [])
            fresh_job_ids = [job_id for job_id in candidate.sample_job_ids if job_id not in seen_job_ids]
            if not fresh_job_ids:
                return []
            incident = existing
            for job_id in fresh_job_ids:
                incident = incident_db.touch_incident(
                    conn,
                    incident_id=incident.incident_id,
                    now=float(ctx.now),
                    add_job_id=job_id,
                    evidence_dir=existing.evidence_dir,
                )
            is_new_incident = False

        inc_dir = Path(str(incident.evidence_dir or (monitor_dir / "incidents" / incident.incident_id)))
        inc_dir.mkdir(parents=True, exist_ok=True)
        snapshots = inc_dir / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)
        summary_rel_path = _summary_rel_path(incident_id=incident.incident_id)
        metadata = {
            **(candidate.metadata or {}),
            "detector_id": candidate.detector_id,
            "provider": candidate.provider,
            "kind": candidate.kind,
            "sample_job_ids": list(candidate.sample_job_ids),
            "sample_clients": list(candidate.sample_clients),
        }
        issue, created, info = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title=candidate.title,
            severity=candidate.severity,
            kind=candidate.kind,
            symptom=candidate.symptom,
            job_id=candidate.primary_job_id,
            conversation_url=candidate.conversation_url,
            artifacts_path=summary_rel_path,
            source="behavior_auto",
            tags=["behavior_auto", candidate.detector_id, candidate.provider],
            metadata=metadata,
            fingerprint=candidate.issue_fingerprint,
            now=float(ctx.now),
        )
        client_issues.link_issue_evidence(
            conn,
            issue_id=issue.issue_id,
            job_id=candidate.primary_job_id,
            conversation_url=candidate.conversation_url,
            artifacts_path=summary_rel_path,
            note="behavior detector evidence bundle refreshed",
            source="behavior_auto",
            metadata={"incident_id": incident.incident_id, "detector_id": candidate.detector_id},
            now=float(ctx.now),
        )

        for job_id in _sampled(candidate.sample_job_ids, limit=6):
            _copy_job_evidence(artifacts_dir=artifacts_dir, inc_dir=inc_dir, job_id=job_id, conn=conn)

        fix_job_id: str | None = None
        auto_sre_enabled = bool(state.get("enable_behavior_auto_sre_fix", False))
        if auto_sre_enabled:
            prior_submits = incident_db.count_actions(
                conn,
                action_type="submit_sre_fix_request",
                since_ts=0.0,
                incident_id=incident.incident_id,
            )
            if int(prior_submits) == 0:
                fix_job = create_sre_fix_request_job(
                    conn=conn,
                    artifacts_dir=artifacts_dir,
                    idempotency_key=f"maint_daemon:behavior_sre_fix_request:{issue.issue_id}",
                    client_name="maint_daemon_behavior_auto",
                    requested_by=requested_by_transport("maint_daemon_behavior_auto"),
                    issue_id=issue.issue_id,
                    incident_id=incident.incident_id,
                    job_id=candidate.primary_job_id,
                    symptom=candidate.symptom,
                    instructions=candidate.instructions,
                    context={
                        "detector_id": candidate.detector_id,
                        "provider": candidate.provider,
                        "kind": candidate.kind,
                        "sample_job_ids": list(candidate.sample_job_ids),
                        "sample_prompts": list(candidate.sample_prompts),
                        "sample_clients": list(candidate.sample_clients),
                        "incident_summary_path": summary_rel_path,
                    },
                    route_mode="auto_best_effort",
                    runtime_apply_actions=True,
                    runtime_max_risk="low",
                    open_pr_mode="p0",
                    open_pr_run_tests=False,
                    gitnexus_limit=5,
                    max_attempts=1,
                )
                fix_job_id = str(fix_job.job_id)
                incident_db.create_action(
                    conn,
                    incident_id=incident.incident_id,
                    action_type="submit_sre_fix_request",
                    status=incident_db.ACTION_STATUS_COMPLETED,
                    risk_level="low",
                    now=float(ctx.now),
                    result={"issue_id": issue.issue_id, "fix_job_id": fix_job_id, "detector_id": candidate.detector_id},
                )
                client_issues.update_issue_status(
                    conn,
                    issue_id=issue.issue_id,
                    status=client_issues.CLIENT_ISSUE_STATUS_IN_PROGRESS,
                    note="behavior detector auto-submitted sre.fix_request",
                    actor="maint_daemon",
                    metadata={"incident_id": incident.incident_id, "fix_job_id": fix_job_id},
                    linked_job_id=fix_job_id,
                    now=float(ctx.now),
                )

        manifest = {
            "incident_id": incident.incident_id,
            "fingerprint_hash": incident.fingerprint_hash,
            "signature": incident.signature,
            "category": "behavior",
            "severity": candidate.severity,
            "detector_id": candidate.detector_id,
            "provider": candidate.provider,
            "kind": candidate.kind,
            "created_at": float(incident.created_at),
            "updated_at": float(incident.updated_at),
            "last_seen_at": float(incident.last_seen_at),
            "job_ids": list(incident.job_ids or []),
            "issue_id": issue.issue_id,
            "sre_fix_request_job_id": (fix_job_id or None),
        }
        atomic_write_json(inc_dir / "manifest.json", manifest)
        _write_incident_summary(
            inc_dir=inc_dir,
            candidate=candidate,
            issue_id=issue.issue_id,
            incident_id=incident.incident_id,
            fix_job_id=fix_job_id,
        )

        observations: list[Observation] = [
            Observation(
                subsystem=self.name,
                kind="incident",
                data={
                    "type": "behavior_issue_promoted",
                    "detector_id": candidate.detector_id,
                    "incident_id": incident.incident_id,
                    "issue_id": issue.issue_id,
                    "created": bool(created),
                    "reopened": bool(info.get("reopened")),
                    "is_new_incident": bool(is_new_incident),
                    "kind": candidate.kind,
                    "provider": candidate.provider,
                    "sample_job_ids": list(candidate.sample_job_ids),
                },
            )
        ]
        if fix_job_id:
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="action",
                    data={
                        "type": "behavior_sre_fix_submitted",
                        "detector_id": candidate.detector_id,
                        "incident_id": incident.incident_id,
                        "issue_id": issue.issue_id,
                        "fix_job_id": fix_job_id,
                    },
                )
            )
        return observations

    def _auto_mitigate(self, ctx: TickContext) -> list[Observation]:
        conn = ctx.conn
        assert conn is not None
        state = ctx.state
        quiet_hours = float(state.get("behavior_issue_auto_mitigate_after_hours", 0))
        if quiet_hours <= 0:
            return []
        cutoff = float(ctx.now) - (quiet_hours * 3600.0)
        max_per_tick = max(1, int(state.get("behavior_issue_auto_mitigate_max_per_tick", 10)))
        rows = conn.execute(
            """
            SELECT issue_id, status, updated_at, latest_artifacts_path
            FROM client_issues
            WHERE source = ?
              AND status IN (?, ?)
              AND updated_at <= ?
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (
                "behavior_auto",
                client_issues.CLIENT_ISSUE_STATUS_OPEN,
                client_issues.CLIENT_ISSUE_STATUS_IN_PROGRESS,
                float(cutoff),
                int(max_per_tick),
            ),
        ).fetchall()
        observations: list[Observation] = []
        for row in rows:
            issue_id = str(row["issue_id"] or "").strip()
            if not issue_id:
                continue
            issue = client_issues.update_issue_status(
                conn,
                issue_id=issue_id,
                status=client_issues.CLIENT_ISSUE_STATUS_MITIGATED,
                note=f"behavior auto-mitigated: no recurrence in {quiet_hours:.1f}h",
                actor="maint_daemon",
                metadata={"quiet_hours": quiet_hours},
                now=float(ctx.now),
            )
            incident_id = _incident_id_from_artifacts_path(
                str(row["latest_artifacts_path"]) if row["latest_artifacts_path"] is not None else None
            )
            if incident_id:
                try:
                    incident_db.set_incident_status(
                        conn,
                        incident_id=incident_id,
                        status=incident_db.INCIDENT_STATUS_RESOLVED,
                        now=float(ctx.now),
                    )
                except Exception:
                    logger.debug("failed to resolve behavior incident %s during auto-mitigate", incident_id, exc_info=True)
            observations.append(
                Observation(
                    subsystem=self.name,
                    kind="action",
                    data={
                        "type": "behavior_issue_auto_mitigated",
                        "issue_id": issue.issue_id,
                        "incident_id": incident_id,
                        "quiet_hours": quiet_hours,
                    },
                )
            )
        return observations
