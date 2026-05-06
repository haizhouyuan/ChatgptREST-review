"""Content-addressable artifact storage with provenance tracking.

Adapted from planning/aios kernel for ChatgptREST conventions.

Design principles:
  - artifact_id = SHA256(content) — automatic deduplication
  - artifacts table = content metadata (INSERT OR IGNORE keeps first writer)
  - artifact_productions table = every production event (always INSERT)
  - Atomic writes via temp file + os.replace()
  - Thread-safe SQLite with WAL mode
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union


@dataclass
class Artifact:
    """Immutable artifact metadata snapshot."""

    artifact_id: str          # SHA256(content)
    content_type: str         # "text/markdown" | "application/json" | …
    content_path: str         # filesystem path (hash-named)
    task_id: str
    step_id: str
    producer: str             # module / capability name
    evidence_refs: list[str] = field(default_factory=list)
    security_label: str = "internal"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ArtifactStore:
    """Content-addressable artifact storage with atomic writes."""

    def __init__(self, base_dir: str | Path, db_path: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    # ── Connection management ─────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id   TEXT PRIMARY KEY,
                content_type  TEXT NOT NULL,
                content_path  TEXT NOT NULL,
                evidence_refs TEXT DEFAULT '[]',
                security_label TEXT DEFAULT 'internal',
                created_at    TEXT NOT NULL,
                metadata      TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifact_productions (
                production_id TEXT PRIMARY KEY,
                artifact_id   TEXT NOT NULL,
                task_id       TEXT NOT NULL,
                step_id       TEXT NOT NULL,
                producer      TEXT NOT NULL,
                security_label TEXT DEFAULT 'internal',
                created_at    TEXT NOT NULL,
                metadata      TEXT DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_task ON artifact_productions(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_artifact ON artifact_productions(artifact_id)")

    def close(self) -> None:
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

    # ── Core operations ───────────────────────────────────────────

    @staticmethod
    def compute_id(content: Union[str, bytes]) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def _content_path(self, artifact_id: str) -> Path:
        return self.base_dir / artifact_id[:2] / artifact_id

    def store(
        self,
        content: Union[str, bytes],
        *,
        task_id: str,
        step_id: str,
        producer: str,
        content_type: str = "text/markdown",
        evidence_refs: Optional[list[str]] = None,
        security_label: str = "internal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Artifact:
        """Store content with atomic write; returns Artifact with provenance."""
        artifact_id = self.compute_id(content)
        content_path = self._content_path(artifact_id)
        content_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        evidence_refs = evidence_refs or []
        metadata = metadata or {}

        # Atomic write: temp → rename
        raw = content.encode("utf-8") if isinstance(content, str) else content
        tmp = content_path.with_suffix(".tmp")
        try:
            tmp.write_bytes(raw)
            os.replace(tmp, content_path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

        conn = self._get_conn()

        # INSERT OR IGNORE: first writer wins for metadata
        conn.execute(
            """INSERT OR IGNORE INTO artifacts
               (artifact_id, content_type, content_path, evidence_refs,
                security_label, created_at, metadata)
               VALUES (?,?,?,?,?,?,?)""",
            (
                artifact_id,
                content_type,
                str(content_path),
                json.dumps(evidence_refs),
                security_label,
                now,
                json.dumps(metadata),
            ),
        )

        # Always record production event
        conn.execute(
            """INSERT INTO artifact_productions
               (production_id, artifact_id, task_id, step_id, producer,
                security_label, created_at, metadata)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                uuid.uuid4().hex,
                artifact_id,
                task_id,
                step_id,
                producer,
                security_label,
                now,
                json.dumps(metadata),
            ),
        )

        # Explicit commit to ensure persistence
        conn.commit()

        return Artifact(
            artifact_id=artifact_id,
            content_type=content_type,
            content_path=str(content_path),
            task_id=task_id,
            step_id=step_id,
            producer=producer,
            evidence_refs=evidence_refs,
            security_label=security_label,
            created_at=now,
            metadata=metadata,
        )

    def get(self, artifact_id: str) -> Optional[Artifact]:
        conn = self._get_conn()
        row = conn.execute(
            """SELECT a.artifact_id, a.content_type, a.content_path,
                      p.task_id, p.step_id, p.producer,
                      a.evidence_refs, a.security_label, a.created_at, a.metadata
               FROM artifacts a
               LEFT JOIN artifact_productions p ON a.artifact_id = p.artifact_id
               WHERE a.artifact_id = ?
               ORDER BY p.created_at ASC
               LIMIT 1""",
            (artifact_id,),
        ).fetchone()
        if not row:
            return None
        return Artifact(
            artifact_id=row[0],
            content_type=row[1],
            content_path=row[2],
            task_id=row[3] or "",
            step_id=row[4] or "",
            producer=row[5] or "",
            evidence_refs=json.loads(row[6]),
            security_label=row[7],
            created_at=row[8],
            metadata=json.loads(row[9]),
        )

    def get_content(self, artifact_id: str) -> Optional[Union[str, bytes]]:
        """Read and integrity-verify content."""
        artifact = self.get(artifact_id)
        if not artifact:
            return None
        path = Path(artifact.content_path)
        if not path.exists():
            return None
        raw = path.read_bytes()
        if self.compute_id(raw) != artifact_id:
            raise ValueError(f"Artifact {artifact_id} content hash mismatch")
        if artifact.content_type.startswith("text/") or artifact.content_type == "application/json":
            return raw.decode("utf-8")
        return raw

    def get_productions(self, artifact_id: str) -> list[dict[str, Any]]:
        """Get all production records for an artifact (preserves provenance history)."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT production_id, artifact_id, task_id, step_id, producer,
                      security_label, created_at, metadata
               FROM artifact_productions
               WHERE artifact_id = ?
               ORDER BY created_at ASC""",
            (artifact_id,),
        ).fetchall()
        return [
            {
                "production_id": r[0],
                "artifact_id": r[1],
                "task_id": r[2],
                "step_id": r[3],
                "producer": r[4],
                "security_label": r[5],
                "created_at": r[6],
                "metadata": json.loads(r[7]),
            }
            for r in rows
        ]

    def get_production_history(self, task_id: str) -> list[dict[str, Any]]:
        """Get full production history for a task."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT production_id, artifact_id, task_id, step_id, producer,
                      security_label, created_at, metadata
               FROM artifact_productions
               WHERE task_id = ?
               ORDER BY created_at DESC""",
            (task_id,),
        ).fetchall()
        return [
            {
                "production_id": r[0],
                "artifact_id": r[1],
                "task_id": r[2],
                "step_id": r[3],
                "producer": r[4],
                "security_label": r[5],
                "created_at": r[6],
                "metadata": json.loads(r[7]),
            }
            for r in rows
        ]

    def list_by_task(self, task_id: str) -> list[Artifact]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT a.artifact_id, a.content_type, a.content_path,
                      p.task_id, p.step_id, p.producer,
                      a.evidence_refs, a.security_label, a.created_at, a.metadata
               FROM artifacts a
               INNER JOIN artifact_productions p ON a.artifact_id = p.artifact_id
               WHERE p.task_id = ?
               ORDER BY p.created_at DESC""",
            (task_id,),
        ).fetchall()
        return [
            Artifact(
                artifact_id=r[0], content_type=r[1], content_path=r[2],
                task_id=r[3], step_id=r[4], producer=r[5],
                evidence_refs=json.loads(r[6]), security_label=r[7],
                created_at=r[8], metadata=json.loads(r[9]),
            )
            for r in rows
        ]
