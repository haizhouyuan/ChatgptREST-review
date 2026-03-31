"""Agent Activity Extractor — ingest JSONL closeout/commit events into EvoMap.

Processes agent activity JSONL files and creates:
- Document: one per JSONL file (per day)
- Episode: one per event
- Atom: one per meaningful event (closeout, commit)

Skips head_change events (low signal, covered by commits).

Reference: docs/2026-03-07_evomap_agent_evolution_ingestion_plan.md
GitHub: ChatgptREST #95
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from chatgptrest.evomap.knowledge.extractors.base import BaseExtractor
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    Document,
    Episode,
    Evidence,
)
from chatgptrest.telemetry_contract import compact_identity, extract_identity_fields

logger = logging.getLogger(__name__)

# Default search paths for event JSONL files
DEFAULT_EVENT_DIRS = [
    "/vol1/maint/state/agent_activity",
    os.path.expanduser("~/projects/openmind/exports"),
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _parse_ts(ts_str: str) -> float:
    """Parse ISO timestamp to unix seconds."""
    try:
        # Handle timezone offset format like 2026-03-07T18:37:46+08:00
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Event-to-Atom mappers
# ---------------------------------------------------------------------------

def _closeout_to_atom(event: dict, episode_id: str) -> Atom | None:
    """Map agent.task.closeout event to an Atom."""
    closeout = event.get("closeout", {})
    agent = event.get("agent", {})
    repo = event.get("repo", {})

    summary = closeout.get("summary", "")
    if not summary:
        return None

    agent_name = agent.get("name", "unknown")
    repo_name = repo.get("name", "unknown")
    task_ref = event.get("task_ref", "")
    branch = repo.get("branch", "")
    status = closeout.get("status", "unknown")
    head = repo.get("head", "")[:8]
    identity = extract_identity_fields(event)

    question = f"What was done in task '{task_ref}' by {agent_name} on {repo_name}?"
    answer_parts = [
        f"**Agent**: {agent_name}",
        f"**Repository**: {repo_name} ({branch})",
        f"**Status**: {status}",
        f"**Summary**: {summary}",
    ]
    if closeout.get("pending_reason"):
        answer_parts.append(f"**Pending**: {closeout['pending_reason']}")
    if head:
        answer_parts.append(f"**HEAD**: {head}")

    ts = _parse_ts(event.get("ts", ""))
    content = "\n".join(answer_parts)

    return Atom(
        atom_id=f"at_act_{_hash(json.dumps(event, sort_keys=True))}",
        episode_id=episode_id,
        atom_type="lesson",
        question=question,
        answer="\n".join(answer_parts),
        canonical_question=f"task result: {task_ref} by {agent_name}" if task_ref else "",
        stability="versioned",
        status="candidate",
        valid_from=ts,
        promotion_status="staged",
        promotion_reason="activity_ingest",
        applicability=json.dumps(
            compact_identity(
                {
                    "repo": identity.get("repo_name"),
                    "repo_path": identity.get("repo_path"),
                    "branch": identity.get("repo_branch") or branch,
                    "source": identity.get("source"),
                    "agent": identity.get("agent_name") or agent_name,
                    "status": status,
                    "trace_id": identity.get("trace_id"),
                    "task_ref": identity.get("task_ref") or task_ref,
                    "lane_id": identity.get("lane_id"),
                    "role_id": identity.get("role_id"),
                    "adapter_id": identity.get("adapter_id"),
                    "profile_id": identity.get("profile_id"),
                    "executor_kind": identity.get("executor_kind"),
                }
            ),
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


def _commit_to_atom(event: dict, episode_id: str) -> Atom | None:
    """Map agent.git.commit event to an Atom."""
    repo = event.get("repo", {})
    agent = event.get("agent", {})
    commit = event.get("commit", {})

    sha_full = commit.get("commit") or commit.get("sha") or repo.get("head", "")
    sha = sha_full[:12]
    message = commit.get("subject") or commit.get("message", "")
    if not sha:
        return None

    agent_name = agent.get("name", "unknown")
    repo_name = repo.get("name", "unknown")
    branch = repo.get("branch", "")
    files = commit.get("touched_paths_preview")
    if files in (None, "", []):
        files = commit.get("files_changed", [])
    identity = extract_identity_fields(event)

    question = f"What was committed to {repo_name} at {sha}?"
    answer_parts = [
        f"**Agent**: {agent_name}",
        f"**Repository**: {repo_name} ({branch})",
        f"**Commit**: {sha}",
    ]
    if message:
        answer_parts.append(f"**Message**: {message}")
    if files:
        if isinstance(files, list):
            answer_parts.append(f"**Files**: {', '.join(str(f) for f in files[:10])}")
        elif isinstance(files, int):
            answer_parts.append(f"**Files changed**: {files}")

    ts = _parse_ts(event.get("ts", ""))

    return Atom(
        atom_id=f"at_act_{_hash(json.dumps(event, sort_keys=True))}",
        episode_id=episode_id,
        atom_type="procedure",
        question=question,
        answer="\n".join(answer_parts),
        canonical_question=f"commit {sha[:8]} on {repo_name}",
        stability="versioned",
        status="candidate",
        valid_from=ts,
        promotion_status="staged",
        promotion_reason="activity_ingest",
        applicability=json.dumps(
            compact_identity(
                {
                    "repo": identity.get("repo_name") or repo_name,
                    "repo_path": identity.get("repo_path"),
                    "branch": identity.get("repo_branch") or branch,
                    "source": identity.get("source"),
                    "agent": identity.get("agent_name") or agent_name,
                    "trace_id": identity.get("trace_id"),
                    "task_ref": identity.get("task_ref"),
                    "commit_sha": identity.get("commit_sha") or sha_full,
                    "lane_id": identity.get("lane_id"),
                    "role_id": identity.get("role_id"),
                    "adapter_id": identity.get("adapter_id"),
                    "profile_id": identity.get("profile_id"),
                    "executor_kind": identity.get("executor_kind"),
                }
            ),
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

@dataclass
class IngestStats:
    files_processed: int = 0
    events_read: int = 0
    atoms_created: int = 0
    atoms_skipped: int = 0
    duplicates: int = 0
    elapsed_ms: float = 0.0


class ActivityExtractor(BaseExtractor):
    """Extract agent activity events from JSONL into EvoMap."""

    source_name = "agent_activity"

    def __init__(self, db, event_dirs: list[str] | None = None):
        super().__init__(db)
        self.event_dirs = event_dirs or DEFAULT_EVENT_DIRS
        self.stats = IngestStats()

    def find_jsonl_files(self) -> list[str]:
        """Find all agent activity JSONL files."""
        files = []
        for d in self.event_dirs:
            pattern = os.path.join(d, "agent_activity_events_*.jsonl")
            files.extend(sorted(glob.glob(pattern)))
        return files

    def extract_documents(self) -> Iterator[Document]:
        """Yield one Document per JSONL file."""
        for path in self.find_jsonl_files():
            basename = os.path.basename(path)
            doc_id = f"doc_act_{_hash(path)}"
            yield Document(
                doc_id=doc_id,
                source="agent_activity",
                project="evomap",
                raw_ref=path,
                title=basename,
                created_at=os.path.getmtime(path) if os.path.exists(path) else 0.0,
                updated_at=os.path.getmtime(path) if os.path.exists(path) else 0.0,
                hash=_hash(f"{path}:{os.path.getsize(path) if os.path.exists(path) else 0}"),
            )

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        """Yield one Episode per event in the JSONL file."""
        path = doc.raw_ref
        if not os.path.exists(path):
            return

        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Bad JSON at %s:%d", path, line_num)
                    continue

                self.stats.events_read += 1
                event_type = event.get("event_type", "")

                # Skip head_change — low signal
                if event_type == "agent.git.head_change":
                    self.stats.atoms_skipped += 1
                    continue

                # Skip unknown types
                if event_type not in ("agent.task.closeout", "agent.git.commit"):
                    self.stats.atoms_skipped += 1
                    continue

                ts = _parse_ts(event.get("ts", ""))
                ep_id = f"ep_act_{_hash(json.dumps(event, sort_keys=True))}"

                identity = extract_identity_fields(event)
                ep = Episode(
                    episode_id=ep_id,
                    doc_id=doc.doc_id,
                    episode_type=event_type,
                    title=f"{event_type} by {event.get('agent', {}).get('name', '?')}",
                    summary=event.get("closeout", {}).get("summary", "")
                    or event.get("commit", {}).get("subject", "")
                    or event.get("commit", {}).get("message", ""),
                    time_start=ts,
                    time_end=ts,
                    source_ext=json.dumps(identity, ensure_ascii=False, sort_keys=True),
                )
                # Stash event data for atom extraction
                ep._event = event  # type: ignore[attr-defined]
                yield ep

    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Yield one Atom per event episode."""
        event = getattr(episode, "_event", None)
        if not event:
            return

        event_type = event.get("event_type", "")

        if event_type == "agent.task.closeout":
            atom = _closeout_to_atom(event, episode.episode_id)
        elif event_type == "agent.git.commit":
            atom = _commit_to_atom(event, episode.episode_id)
        else:
            return

        if atom is None:
            self.stats.atoms_skipped += 1
            return

        # Dedup check
        if self.db.atom_exists_by_hash(atom.compute_hash()):
            self.stats.duplicates += 1
            return

        self.stats.atoms_created += 1
        yield atom

    def extract_all(self) -> IngestStats:
        """Override to return stats."""
        t0 = time.time()
        for doc in self.extract_documents():
            self.db.put_document(doc)
            self.stats.files_processed += 1

            for episode in self.extract_episodes(doc):
                self.db.put_episode(episode)

                for atom in self.extract_atoms(episode):
                    self.db.put_atom(atom)

        self.db.commit()
        self.stats.elapsed_ms = (time.time() - t0) * 1000

        logger.info(
            "Activity ingest: files=%d, events=%d, atoms=%d, "
            "skipped=%d, dupes=%d (%.0fms)",
            self.stats.files_processed, self.stats.events_read,
            self.stats.atoms_created, self.stats.atoms_skipped,
            self.stats.duplicates, self.stats.elapsed_ms,
        )
        return self.stats
