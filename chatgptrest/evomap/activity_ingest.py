"""Agent Activity Live Ingest — real-time event ingestion into EvoMap.

Connects to the existing EventBus and receives closeout/commit/activity
events, routing them into KnowledgeDB.

References:
- Issue #99 WP5
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Edge,
    Entity,
    Episode,
    Evidence,
    PromotionStatus,
)
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.telemetry_contract import compact_identity, extract_identity_fields

logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _parse_ts(ts_str: Any) -> float:
    """Parse ISO timestamp to unix seconds."""
    if not ts_str:
        return time.time()
    try:
        dt = datetime.fromisoformat(str(ts_str))
        return dt.timestamp()
    except (ValueError, TypeError):
        return time.time()


def _normalize_entity_name(name: str) -> str:
    """Normalize entity name for matching."""
    return name.lower().strip().replace("/", "_").replace("-", "_")


def _json_blob(data: dict[str, Any]) -> str:
    """Serialize metadata in a stable JSON form."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop empty-ish keys to keep metadata compact and stable."""
    return {
        key: value
        for key, value in data.items()
        if value not in ("", None, [], {}, ())
    }


def _as_text_list(value: Any) -> list[str]:
    """Coerce a mixed value into a list[str] for previews."""
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple | set):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _stable_event_hash(kind: str, identity: dict[str, Any]) -> str:
    """Build a stable fingerprint from normalized event identity."""
    return _hash(_json_blob({"kind": kind, **_compact(identity)}))


def _normalize_commit_payload(commit_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize either flat commit payloads or archive envelopes."""
    repo = commit_data.get("repo") if isinstance(commit_data.get("repo"), dict) else {}
    if not repo:
        repo = _compact(
            {
                "name": commit_data.get("repo_name"),
                "path": commit_data.get("repo_path"),
                "branch": commit_data.get("repo_branch"),
                "head": commit_data.get("repo_head"),
                "upstream": commit_data.get("repo_upstream"),
            }
        )
    commit = commit_data.get("commit") if isinstance(commit_data.get("commit"), dict) else {}
    agent = commit_data.get("agent") if isinstance(commit_data.get("agent"), dict) else {}

    files_value = commit_data.get("files_changed")
    if files_value in (None, "", []):
        files_value = commit.get("touched_paths_preview")
    files_preview = [] if isinstance(files_value, int) else _as_text_list(files_value)
    files_count = (
        files_value
        if isinstance(files_value, int)
        else commit.get("files_changed")
        if isinstance(commit.get("files_changed"), int)
        else len(files_preview)
    )

    return {
        "sha": str(commit_data.get("hash") or commit.get("commit") or "").strip(),
        "branch": str(commit_data.get("branch") or repo.get("branch") or "").strip(),
        "message": str(commit_data.get("message") or commit.get("subject") or "").strip(),
        "author": str(
            commit_data.get("author")
            or commit.get("author_name")
            or commit.get("author")
            or agent.get("name")
            or "unknown"
        ).strip(),
        "timestamp": commit_data.get("timestamp") or commit.get("authored_at") or commit_data.get("ts") or "",
        "files_preview": files_preview,
        "files_count": files_count,
        "task_ref": str(commit_data.get("task_ref") or "").strip(),
        "trace_id": str(commit_data.get("trace_id") or "").strip(),
        "session_id": str(commit_data.get("session_id") or "").strip(),
        "event_id": str(commit_data.get("event_id") or "").strip(),
        "upstream_event_id": str(commit_data.get("upstream_event_id") or "").strip(),
        "run_id": str(commit_data.get("run_id") or "").strip(),
        "parent_run_id": str(commit_data.get("parent_run_id") or "").strip(),
        "job_id": str(commit_data.get("job_id") or "").strip(),
        "issue_id": str(commit_data.get("issue_id") or "").strip(),
        "schema_version": str(commit_data.get("schema_version") or "").strip(),
        "source": str(commit_data.get("source") or "agent_activity").strip(),
        "note": str(commit_data.get("note") or "").strip(),
        "provider": str(commit_data.get("provider") or "").strip(),
        "model": str(commit_data.get("model") or "").strip(),
        "lane_id": str(commit_data.get("lane_id") or "").strip(),
        "role_id": str(commit_data.get("role_id") or "").strip(),
        "adapter_id": str(commit_data.get("adapter_id") or "").strip(),
        "profile_id": str(commit_data.get("profile_id") or "").strip(),
        "executor_kind": str(commit_data.get("executor_kind") or "").strip(),
        "repo_name": str(repo.get("name") or commit_data.get("project") or "evomap").strip(),
        "repo_path": str(repo.get("path") or "").strip(),
        "repo_branch": str(repo.get("branch") or "").strip(),
        "repo_head": str(repo.get("head") or "").strip(),
        "repo_upstream": str(repo.get("upstream") or "").strip(),
        "agent_name": str(agent.get("name") or "").strip(),
    }


def _normalize_closeout_payload(closeout_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize either flat closeout payloads or archive envelopes."""
    repo = closeout_data.get("repo") if isinstance(closeout_data.get("repo"), dict) else {}
    if not repo:
        repo = _compact(
            {
                "name": closeout_data.get("repo_name"),
                "path": closeout_data.get("repo_path"),
                "branch": closeout_data.get("repo_branch"),
                "head": closeout_data.get("repo_head"),
                "upstream": closeout_data.get("repo_upstream"),
            }
        )
    agent = closeout_data.get("agent") if isinstance(closeout_data.get("agent"), dict) else {}
    closeout = closeout_data.get("closeout") if isinstance(closeout_data.get("closeout"), dict) else {}

    return {
        "task_id": str(closeout_data.get("task_id") or closeout_data.get("task_ref") or "").strip(),
        "task_ref": str(closeout_data.get("task_ref") or closeout_data.get("task_id") or "").strip(),
        "agent_id": str(closeout_data.get("agent_id") or agent.get("name") or "unknown").strip(),
        "summary": str(closeout_data.get("summary") or closeout.get("summary") or "").strip(),
        "status": str(closeout_data.get("status") or closeout.get("status") or "").strip(),
        "pending_reason": str(closeout_data.get("pending_reason") or closeout.get("pending_reason") or "").strip(),
        "pending_scope": str(closeout_data.get("pending_scope") or closeout.get("pending_scope") or "").strip(),
        "files_changed": _as_text_list(closeout_data.get("files_changed")),
        "commands_run": _as_text_list(closeout_data.get("commands_run")),
        "duration_s": closeout_data.get("duration_s") or 0,
        "timestamp": closeout_data.get("timestamp") or closeout_data.get("ts") or "",
        "trace_id": str(closeout_data.get("trace_id") or "").strip(),
        "session_id": str(closeout_data.get("session_id") or "").strip(),
        "event_id": str(closeout_data.get("event_id") or "").strip(),
        "upstream_event_id": str(closeout_data.get("upstream_event_id") or "").strip(),
        "run_id": str(closeout_data.get("run_id") or "").strip(),
        "parent_run_id": str(closeout_data.get("parent_run_id") or "").strip(),
        "job_id": str(closeout_data.get("job_id") or "").strip(),
        "issue_id": str(closeout_data.get("issue_id") or "").strip(),
        "schema_version": str(closeout_data.get("schema_version") or "").strip(),
        "source": str(closeout_data.get("source") or "agent_activity").strip(),
        "note": str(closeout_data.get("note") or "").strip(),
        "provider": str(closeout_data.get("provider") or "").strip(),
        "model": str(closeout_data.get("model") or "").strip(),
        "lane_id": str(closeout_data.get("lane_id") or "").strip(),
        "role_id": str(closeout_data.get("role_id") or "").strip(),
        "adapter_id": str(closeout_data.get("adapter_id") or "").strip(),
        "profile_id": str(closeout_data.get("profile_id") or "").strip(),
        "executor_kind": str(closeout_data.get("executor_kind") or "").strip(),
        "repo_name": str(repo.get("name") or closeout_data.get("project") or "evomap").strip(),
        "repo_path": str(repo.get("path") or "").strip(),
        "repo_branch": str(repo.get("branch") or "").strip(),
        "repo_head": str(repo.get("head") or "").strip(),
        "repo_upstream": str(repo.get("upstream") or "").strip(),
    }


def _subscribe_event(event_bus, event_type: str, handler):
    """Support both typed and generic EventBus subscribe contracts."""
    subscribe = getattr(event_bus, "subscribe")
    try:
        subscribe(event_type, handler)
        return handler
    except TypeError:
        pass

    def _filtered(event):
        if getattr(event, "event_type", "") == event_type:
            handler(event)

    subscribe(_filtered)
    return _filtered


@dataclass
class IngestResult:
    """Result of an ingest operation."""
    ok: bool
    atom_ids: list[str]
    entity_ids: list[str]
    edge_ids: list[str]
    message: str


class ActivityIngestService:
    """Live ingest adapter for agent activity events into EvoMap.

    Connects to the existing EventBus and EvoMapObserver to receive
    closeout / commit / activity events and route them into KnowledgeDB.

    Usage::

        db = KnowledgeDB(":memory:")
        db.init_schema()
        observer = EvoMapObserver(db_path=":memory:")
        service = ActivityIngestService(db=db, observer=observer)

        result = service.ingest_commit_event({
            "hash": "abc123",
            "branch": "main",
            "message": "feat: add new feature",
            "author": "claude",
            "files_changed": ["main.py"],
            "timestamp": "2026-03-07T18:37:46+08:00",
        })
    """

    def __init__(self, db: KnowledgeDB, observer: EvoMapObserver):
        self.db = db
        self.observer = observer

    def _ensure_document(self, source: str, project: str = "evomap") -> Document:
        """Get or create a document for the event source."""
        doc_key = f"{source}:{project}"
        doc_id = f"doc_live_{_hash(doc_key)}"
        doc = self.db.get_document(doc_id)
        if doc is None:
            doc = Document(
                doc_id=doc_id,
                source=source,
                project=project,
                raw_ref=f"live_ingest:{doc_key}",
                title=f"Live Ingest: {source} ({project})",
                created_at=time.time(),
                updated_at=time.time(),
                hash=_hash(f"{doc_key}:{time.time()}"),
            )
            self.db.put_document(doc)
        return doc

    def _ensure_entity(self, name: str, entity_type: str) -> Entity:
        """Get or create an entity."""
        normalized = _normalize_entity_name(name)
        entity_id = f"ent_{entity_type}_{_hash(normalized)}"

        conn = self.db.connect()
        entity = Entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            normalized_name=normalized,
        )
        conn.execute(
            """INSERT OR IGNORE INTO entities (entity_id, entity_type, name, normalized_name)
               VALUES (?, ?, ?, ?)""",
            (entity.entity_id, entity.entity_type, entity.name, entity.normalized_name),
        )
        row = conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        return Entity.from_row(dict(row)) if row else entity

    def ingest_commit_event(self, commit_data: dict) -> IngestResult:
        """Process a git commit event into EvoMap knowledge.

        Expected commit_data keys: hash, branch, message, author, files_changed, timestamp
        """
        payload = _normalize_commit_payload(commit_data)
        sha_full = payload["sha"]
        sha = sha_full[:12]
        branch = payload["branch"]
        message = payload["message"]
        author = payload["author"]
        files = payload["files_preview"]
        ts_str = payload["timestamp"]

        if not sha:
            return IngestResult(ok=False, atom_ids=[], entity_ids=[], edge_ids=[], message="Missing commit hash")

        ts = _parse_ts(ts_str)
        source = payload["source"]
        doc = self._ensure_document(source, project=payload["repo_name"])

        identity = _compact(
            {
                "event_type": commit_data.get("event_type", "agent.git.commit"),
                "schema_version": payload["schema_version"],
                "source": source,
                "task_ref": payload["task_ref"],
                "trace_id": payload["trace_id"],
                "session_id": payload["session_id"],
                "event_id": payload["event_id"],
                "upstream_event_id": payload["upstream_event_id"],
                "run_id": payload["run_id"],
                "parent_run_id": payload["parent_run_id"],
                "job_id": payload["job_id"],
                "issue_id": payload["issue_id"],
                "note": payload["note"],
                "provider": payload["provider"],
                "model": payload["model"],
                "repo_name": payload["repo_name"],
                "repo_path": payload["repo_path"],
                "repo_branch": payload["repo_branch"] or branch,
                "repo_head": payload["repo_head"],
                "repo_upstream": payload["repo_upstream"],
                "agent_name": payload["agent_name"],
                "commit_sha": sha_full,
            }
        )

        fingerprint = _stable_event_hash(
            "commit",
            {
                "commit_sha": sha_full,
            },
        )
        ep_id = f"ep_commit_{fingerprint}"
        episode = Episode(
            episode_id=ep_id,
            doc_id=doc.doc_id,
            episode_type="agent.git.commit",
            title=f"commit by {author}",
            summary=message[:200],
            start_ref=f"commit:{sha_full}",
            end_ref=f"commit:{sha_full}",
            time_start=ts,
            time_end=ts,
            source_ext=_json_blob(identity),
        )
        self.db.put_episode(episode)

        repo_label = payload["repo_name"] or "unknown repo"
        question = f"What was committed to branch '{branch or payload['repo_branch'] or 'unknown'}' in {repo_label} at {sha}?"
        answer_parts = [
            f"**Author**: {author}",
            f"**Branch**: {branch or payload['repo_branch'] or 'unknown'}",
            f"**Commit**: {sha}",
        ]
        if payload["repo_name"]:
            answer_parts.append(f"**Repo**: {payload['repo_name']}")
        if message:
            answer_parts.append(f"**Message**: {message}")
        if files:
            answer_parts.append(f"**Files**: {', '.join(str(f) for f in files[:10])}")
        elif payload["files_count"]:
            answer_parts.append(f"**Files changed**: {payload['files_count']}")
        if payload["task_ref"]:
            answer_parts.append(f"**Task Ref**: {payload['task_ref']}")
        if payload["trace_id"]:
            answer_parts.append(f"**Trace**: {payload['trace_id']}")

        atom_id = f"at_act_commit_{fingerprint}"
        atom = Atom(
            atom_id=atom_id,
            episode_id=ep_id,
            atom_type="procedure",
            question=question,
            answer="\n".join(answer_parts),
            canonical_question=f"commit {sha[:8]} in {repo_label}",
            stability="versioned",
            status=AtomStatus.CANDIDATE.value,
            valid_from=ts,
            promotion_status=PromotionStatus.STAGED.value,
            promotion_reason="activity_ingest",
            applicability=_json_blob(
                _compact(
                    {
                        "repo": payload["repo_name"],
                        "repo_path": payload["repo_path"],
                        "branch": payload["repo_branch"] or branch,
                        "source": source,
                        "agent": payload["agent_name"],
                        "provider": payload["provider"],
                        "model": payload["model"],
                        "task_ref": payload["task_ref"],
                        "trace_id": payload["trace_id"],
                        "lane_id": payload.get("lane_id"),
                        "role_id": payload.get("role_id"),
                        "adapter_id": payload.get("adapter_id"),
                        "profile_id": payload.get("profile_id"),
                        "executor_kind": payload.get("executor_kind"),
                    }
                )
            ),
        )
        atom.hash = fingerprint

        if self.db.atom_exists_by_hash(atom.hash):
            return IngestResult(ok=True, atom_ids=[], entity_ids=[], edge_ids=[], message="Duplicate commit, skipped")

        self.db.put_atom(atom)

        evidence_id = f"ev_commit_{_hash(sha)}"
        evidence = Evidence(
            evidence_id=evidence_id,
            atom_id=atom_id,
            doc_id=doc.doc_id,
            span_ref=f"commit:{sha_full}",
            excerpt=message[:500] if message else "",
            evidence_role="supports",
        )
        self.db.put_evidence(evidence)

        entity_ids = []
        author_entity = self._ensure_entity(author, "agent")
        entity_ids.append(author_entity.entity_id)

        if branch:
            branch_entity = self._ensure_entity(branch, "branch")
            entity_ids.append(branch_entity.entity_id)

        edge_ids = []
        author_edge = Edge(
            from_id=author_entity.entity_id,
            to_id=atom_id,
            edge_type="created",
            from_kind="entity",
            to_kind="atom",
        )
        self.db.put_edge(author_edge)
        edge_ids.append(f"{author_edge.from_id}:{author_edge.to_id}:{author_edge.edge_type}")

        branch_edge = Edge(
            from_id=atom_id,
            to_id=branch_entity.entity_id if branch else "",
            edge_type="belongs_to",
            from_kind="atom",
            to_kind="entity",
        )
        if branch:
            self.db.put_edge(branch_edge)
            edge_ids.append(f"{branch_edge.from_id}:{branch_edge.to_id}:{branch_edge.edge_type}")

        self.db.commit()

        if self.observer:
            self.observer.record_event(
                trace_id=ep_id,
                signal_type="evomap.atom.created",
                source="activity_ingest",
                domain="knowledge",
                data={"atom_id": atom_id, "event_type": "commit"},
            )

        return IngestResult(
            ok=True,
            atom_ids=[atom_id],
            entity_ids=entity_ids,
            edge_ids=edge_ids,
            message=f"Ingested commit {sha}",
        )

    def ingest_closeout_event(self, closeout_data: dict) -> IngestResult:
        """Process an agent task closeout event.

        Expected closeout_data keys: task_id, agent_id, summary, files_changed,
        commands_run, duration_s, timestamp
        """
        payload = _normalize_closeout_payload(closeout_data)
        task_id = payload["task_id"] or payload["task_ref"]
        agent_id = payload["agent_id"]
        summary = payload["summary"]
        files = payload["files_changed"]
        commands = payload["commands_run"]
        duration = payload["duration_s"]
        ts_str = payload["timestamp"]

        if not summary:
            return IngestResult(ok=False, atom_ids=[], entity_ids=[], edge_ids=[], message="Missing summary")

        ts = _parse_ts(ts_str)
        source = payload["source"]
        doc = self._ensure_document(source, project=payload["repo_name"])

        identity = _compact(
            {
                "event_type": closeout_data.get("event_type", "agent.task.closeout"),
                "schema_version": payload["schema_version"],
                "source": source,
                "task_ref": payload["task_ref"],
                "trace_id": payload["trace_id"],
                "session_id": payload["session_id"],
                "event_id": payload["event_id"],
                "upstream_event_id": payload["upstream_event_id"],
                "run_id": payload["run_id"],
                "parent_run_id": payload["parent_run_id"],
                "job_id": payload["job_id"],
                "issue_id": payload["issue_id"],
                "status": payload["status"],
                "pending_reason": payload["pending_reason"],
                "pending_scope": payload["pending_scope"],
                "note": payload["note"],
                "provider": payload["provider"],
                "model": payload["model"],
                "repo_name": payload["repo_name"],
                "repo_path": payload["repo_path"],
                "repo_branch": payload["repo_branch"],
                "repo_head": payload["repo_head"],
                "repo_upstream": payload["repo_upstream"],
            }
        )

        fingerprint = _stable_event_hash(
            "closeout",
            {
                "repo_path": payload["repo_path"] or payload["repo_name"],
                "task_id": task_id,
                "summary": summary,
                "timestamp": ts_str or str(int(ts)),
            },
        )
        ep_id = f"ep_closeout_{fingerprint}"
        episode = Episode(
            episode_id=ep_id,
            doc_id=doc.doc_id,
            episode_type="agent.task.closeout",
            title=f"task closeout: {task_id or 'unscoped'}",
            summary=summary[:200],
            time_start=ts,
            time_end=ts,
            source_ext=_json_blob(identity),
        )
        self.db.put_episode(episode)

        repo_label = payload["repo_name"] or "unknown repo"
        task_label = task_id or "unscoped task"
        question = f"What was done in task '{task_label}' for {repo_label}?"
        answer_parts = [
            f"**Agent**: {agent_id}",
            f"**Task**: {task_label}",
            f"**Summary**: {summary}",
        ]
        if payload["status"]:
            answer_parts.append(f"**Status**: {payload['status']}")
        if payload["repo_name"]:
            answer_parts.append(f"**Repo**: {payload['repo_name']}")
        if files:
            answer_parts.append(f"**Files**: {', '.join(str(f) for f in files[:10])}")
        if commands:
            answer_parts.append(f"**Commands**: {len(commands)} run")
        if duration:
            answer_parts.append(f"**Duration**: {duration:.1f}s")
        if payload["pending_reason"]:
            answer_parts.append(f"**Pending Reason**: {payload['pending_reason']}")
        if payload["pending_scope"]:
            answer_parts.append(f"**Pending Scope**: {payload['pending_scope']}")
        if payload["trace_id"]:
            answer_parts.append(f"**Trace**: {payload['trace_id']}")

        atom_id = f"at_act_closeout_{fingerprint}"
        atom = Atom(
            atom_id=atom_id,
            episode_id=ep_id,
            atom_type="lesson",
            question=question,
            answer="\n".join(answer_parts),
            canonical_question=f"task result: {task_label} by {agent_id}",
            stability="versioned",
            status=AtomStatus.CANDIDATE.value,
            valid_from=ts,
            promotion_status=PromotionStatus.STAGED.value,
            promotion_reason="activity_ingest",
            applicability=_json_blob(
                _compact(
                    {
                        "repo": payload["repo_name"],
                        "repo_path": payload["repo_path"],
                        "branch": payload["repo_branch"],
                        "source": source,
                        "agent": agent_id,
                        "status": payload["status"],
                        "provider": payload["provider"],
                        "model": payload["model"],
                        "task_ref": payload["task_ref"],
                        "trace_id": payload["trace_id"],
                        "lane_id": payload.get("lane_id"),
                        "role_id": payload.get("role_id"),
                        "adapter_id": payload.get("adapter_id"),
                        "profile_id": payload.get("profile_id"),
                        "executor_kind": payload.get("executor_kind"),
                    }
                )
            ),
        )
        atom.hash = fingerprint

        if self.db.atom_exists_by_hash(atom.hash):
            return IngestResult(ok=True, atom_ids=[], entity_ids=[], edge_ids=[], message="Duplicate closeout, skipped")

        self.db.put_atom(atom)

        evidence_id = f"ev_closeout_{fingerprint}"
        evidence = Evidence(
            evidence_id=evidence_id,
            atom_id=atom_id,
            doc_id=doc.doc_id,
            span_ref=f"task:{task_label}",
            excerpt=summary[:500],
            evidence_role="supports",
        )
        self.db.put_evidence(evidence)

        entity_ids = []
        agent_entity = self._ensure_entity(agent_id, "agent")
        entity_ids.append(agent_entity.entity_id)

        if task_id:
            task_entity = self._ensure_entity(task_id, "task")
            entity_ids.append(task_entity.entity_id)

        edge_ids = []
        agent_edge = Edge(
            from_id=agent_entity.entity_id,
            to_id=atom_id,
            edge_type="created",
            from_kind="entity",
            to_kind="atom",
        )
        self.db.put_edge(agent_edge)
        edge_ids.append(f"{agent_edge.from_id}:{agent_edge.to_id}:{agent_edge.edge_type}")

        if task_id:
            task_edge = Edge(
                from_id=atom_id,
                to_id=task_entity.entity_id,
                edge_type="describes",
                from_kind="atom",
                to_kind="entity",
            )
            self.db.put_edge(task_edge)
            edge_ids.append(f"{task_edge.from_id}:{task_edge.to_id}:{task_edge.edge_type}")

        self.db.commit()

        if self.observer:
            self.observer.record_event(
                trace_id=ep_id,
                signal_type="evomap.atom.created",
                source="activity_ingest",
                domain="knowledge",
                data={"atom_id": atom_id, "event_type": "closeout"},
            )

        return IngestResult(
            ok=True,
            atom_ids=[atom_id],
            entity_ids=entity_ids,
            edge_ids=edge_ids,
            message=f"Ingested closeout for task {task_label}",
        )

    def ingest_activity_event(self, event_data: dict) -> IngestResult:
        """Process a generic agent activity event (tool use, error, etc).

        Expected event_data keys: event_type, agent_id, session_id, data, timestamp
        """
        event_type = event_data.get("event_type", "")
        session_id = event_data.get("session_id", "")
        data = event_data.get("data", {})
        ts_str = event_data.get("timestamp", "")
        identity = extract_identity_fields(
            {
                **dict(data or {}),
                **event_data,
            },
            event_type=event_type,
            trace_id=str(event_data.get("trace_id") or ""),
            session_id=session_id,
            source=str(event_data.get("source") or ""),
        )
        agent_id = identity.get("agent_name") or event_data.get("agent_id", "unknown")

        relevant_types = {
            "dispatch.task_started",
            "dispatch.task_completed",
            "dispatch.task_failed",
            "task.dispatched",
            "task.completed",
            "task.failed",
            "agent.tool.use",
            "agent.tool.error",
            "agent.error",
            "agent.session.start",
            "agent.session.end",
            "tool.completed",
            "tool.failed",
            "workflow.completed",
            "workflow.failed",
            "user.feedback",
            "team.run.created",
            "team.run.completed",
            "team.run.failed",
            "team.role.completed",
            "team.role.failed",
            "team.output.accepted",
            "team.output.rejected",
        }

        if event_type not in relevant_types:
            return IngestResult(ok=True, atom_ids=[], entity_ids=[], edge_ids=[], message=f"Skipped non-relevant event type: {event_type}")

        ts = _parse_ts(ts_str)
        source = "agent_activity"
        doc = self._ensure_document(source)

        event_fingerprint = _stable_event_hash(
            "activity",
            {
                "event_type": event_type,
                "event_id": identity.get("upstream_event_id") or identity.get("event_id"),
                "trace_id": identity.get("trace_id"),
                "session_id": identity.get("session_id") or session_id,
                "task_ref": identity.get("task_ref"),
                "data": data,
            },
        )
        if self.db.atom_exists_by_hash(event_fingerprint):
            return IngestResult(ok=True, atom_ids=[], entity_ids=[], edge_ids=[], message="Duplicate activity event, skipped")

        ep_id = f"ep_activity_{event_fingerprint}"
        episode = Episode(
            episode_id=ep_id,
            doc_id=doc.doc_id,
            episode_type=event_type,
            title=f"{event_type} by {agent_id}",
            summary=str(data)[:200],
            time_start=ts,
            time_end=ts,
            source_ext=_json_blob(identity),
        )
        self.db.put_episode_if_absent(episode)

        question = f"What {event_type} event occurred?"
        answer_parts = [
            f"**Agent**: {agent_id}",
            f"**Event**: {event_type}",
        ]
        if session_id:
            answer_parts.append(f"**Session**: {session_id}")
        if data:
            answer_parts.append(f"**Data**: {json.dumps(data)[:200]}")
        if identity.get("repo_name"):
            answer_parts.append(f"**Repo**: {identity['repo_name']}")
        if identity.get("task_ref"):
            answer_parts.append(f"**Task Ref**: {identity['task_ref']}")
        if identity.get("trace_id"):
            answer_parts.append(f"**Trace**: {identity['trace_id']}")

        atom_id = f"at_act_{event_fingerprint}"
        atom = Atom(
            atom_id=atom_id,
            episode_id=ep_id,
            atom_type="lesson",
            question=question,
            answer="\n".join(answer_parts),
            canonical_question=f"activity: {event_type}",
            stability="ephemeral",
            status=AtomStatus.CANDIDATE.value,
            valid_from=ts,
            promotion_status=PromotionStatus.STAGED.value,
            promotion_reason="activity_ingest",
            applicability=_json_blob(
                compact_identity(
                    {
                        "repo": identity.get("repo_name"),
                        "repo_path": identity.get("repo_path"),
                        "source": identity.get("source"),
                        "agent": agent_id,
                        "provider": identity.get("provider"),
                        "model": identity.get("model"),
                        "task_ref": identity.get("task_ref"),
                        "trace_id": identity.get("trace_id"),
                        "lane_id": identity.get("lane_id"),
                        "role_id": identity.get("role_id"),
                        "adapter_id": identity.get("adapter_id"),
                        "profile_id": identity.get("profile_id"),
                        "executor_kind": identity.get("executor_kind"),
                    }
                )
            ),
        )
        atom.hash = event_fingerprint

        self.db.put_atom(atom)

        entity_ids = []
        agent_entity = self._ensure_entity(agent_id, "agent")
        entity_ids.append(agent_entity.entity_id)

        edge_ids = []
        agent_edge = Edge(
            from_id=agent_entity.entity_id,
            to_id=atom_id,
            edge_type="created",
            from_kind="entity",
            to_kind="atom",
        )
        self.db.put_edge(agent_edge)
        edge_ids.append(f"{agent_edge.from_id}:{agent_edge.to_id}:{agent_edge.edge_type}")

        self.db.commit()

        if self.observer:
            self.observer.record_event(
                trace_id=ep_id,
                signal_type="evomap.atom.created",
                source="activity_ingest",
                domain="knowledge",
                data={"atom_id": atom_id, "event_type": event_type},
            )

        return IngestResult(
            ok=True,
            atom_ids=[atom_id],
            entity_ids=entity_ids,
            edge_ids=edge_ids,
            message=f"Ingested activity event {event_type}",
        )

    def register_bus_handlers(self, event_bus) -> list[Any]:
        """Register listeners on the EventBus for automatic live ingest.

        Args:
            event_bus: An EventBus instance with subscribe() method
        """
        def on_commit(event):
            raw_payload = dict(event.data or {})
            upstream_event_id = str(raw_payload.get("upstream_event_id") or raw_payload.get("event_id") or "").strip()
            commit_data = {
                **raw_payload,
                "timestamp": event.timestamp,
                "trace_id": event.trace_id,
                "session_id": event.session_id,
                "event_id": event.event_id,
                "upstream_event_id": upstream_event_id,
                "source": event.source,
                "event_type": event.event_type,
            }
            self.ingest_commit_event(commit_data)

        def on_closeout(event):
            raw_payload = dict(event.data or {})
            upstream_event_id = str(raw_payload.get("upstream_event_id") or raw_payload.get("event_id") or "").strip()
            closeout_data = {
                **raw_payload,
                "timestamp": event.timestamp,
                "trace_id": event.trace_id,
                "session_id": event.session_id,
                "event_id": event.event_id,
                "upstream_event_id": upstream_event_id,
                "source": event.source,
                "event_type": event.event_type,
            }
            self.ingest_closeout_event(closeout_data)

        def on_activity(event):
            raw_payload = dict(event.data or {})
            upstream_event_id = str(raw_payload.get("upstream_event_id") or raw_payload.get("event_id") or "").strip()
            raw_agent = raw_payload.get("agent")
            if isinstance(raw_agent, dict):
                raw_agent_name = str(raw_agent.get("name") or "").strip()
            else:
                raw_agent_name = str(raw_agent or "").strip()
            event_data = {
                **raw_payload,
                "event_type": event.event_type,
                "agent_id": raw_payload.get("agent_id") or raw_payload.get("agent_name") or raw_agent_name or "unknown",
                "session_id": event.session_id or event.trace_id,
                "data": {
                    **raw_payload,
                    **({"upstream_event_id": upstream_event_id} if upstream_event_id else {}),
                },
                "timestamp": event.timestamp,
                "trace_id": event.trace_id,
                "event_id": event.event_id,
                "upstream_event_id": upstream_event_id,
                "source": event.source,
            }
            self.ingest_activity_event(event_data)

        handlers = [
            _subscribe_event(event_bus, "agent.git.commit", on_commit),
            _subscribe_event(event_bus, "agent.task.closeout", on_closeout),
            _subscribe_event(event_bus, "dispatch.task_started", on_activity),
            _subscribe_event(event_bus, "dispatch.task_completed", on_activity),
            _subscribe_event(event_bus, "dispatch.task_failed", on_activity),
            _subscribe_event(event_bus, "task.dispatched", on_activity),
            _subscribe_event(event_bus, "task.completed", on_activity),
            _subscribe_event(event_bus, "task.failed", on_activity),
            _subscribe_event(event_bus, "agent.tool.use", on_activity),
            _subscribe_event(event_bus, "agent.tool.error", on_activity),
            _subscribe_event(event_bus, "agent.error", on_activity),
            _subscribe_event(event_bus, "tool.completed", on_activity),
            _subscribe_event(event_bus, "tool.failed", on_activity),
            _subscribe_event(event_bus, "workflow.completed", on_activity),
            _subscribe_event(event_bus, "workflow.failed", on_activity),
            _subscribe_event(event_bus, "user.feedback", on_activity),
            _subscribe_event(event_bus, "team.run.created", on_activity),
            _subscribe_event(event_bus, "team.run.completed", on_activity),
            _subscribe_event(event_bus, "team.run.failed", on_activity),
            _subscribe_event(event_bus, "team.role.completed", on_activity),
            _subscribe_event(event_bus, "team.role.failed", on_activity),
            _subscribe_event(event_bus, "team.output.accepted", on_activity),
            _subscribe_event(event_bus, "team.output.rejected", on_activity),
        ]

        logger.info("ActivityIngestService registered handlers on EventBus")
        return [handler for handler in handlers if handler is not None]
