"""
KB Artifact Registry – SQLite-based metadata store for all KB artifacts.

This is the canonical "single index entry point" that unifies
existing directories without moving files.  Artifacts are registered
by reference, not by relocation.

Design (from KB DR):
- artifact_id: stable (content_hash + path_salt)
- source_system: agent/tool name
- PARA bucket: project / area / resource / archive
- structural_role: evidence / analysis / spec / plan / decision / runbook / code
- quality_score: provenance + freshness + consensus + structure + validation

Event-driven indexing:
- After registering an artifact, emits 'kb.artifact_registered' event
- Subscribers (like KBHub) can subscribe to auto-index the artifact
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PARABucket(str, Enum):
    PROJECT = "project"
    AREA = "area"
    RESOURCE = "resource"
    ARCHIVE = "archive"
    UNCLASSIFIED = "unclassified"


class StructuralRole(str, Enum):
    EVIDENCE = "evidence"
    ANALYSIS = "analysis"
    SPEC = "spec"
    PLAN = "plan"
    DECISION = "decision"
    RUNBOOK = "runbook"
    CODE = "code"
    LOG = "log"
    RAW = "raw"


class ContentType(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    YAML = "yaml"
    CSV = "csv"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    LOG = "log"
    OTHER = "other"


class DupStatus(str, Enum):
    UNIQUE = "unique"
    EXACT_DUP = "exact_dup"
    NEAR_DUP = "near_dup"
    MERGED = "merged"


class Stability:
    """Stability lifecycle states.

    State machine transitions:
        draft → candidate → approved → deprecated → archived
        candidate → draft  (reject back)
    """
    DRAFT = "draft"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

    # Valid transitions: {from_state: [to_states]}
    TRANSITIONS = {
        "draft":      ["candidate"],
        "candidate":  ["approved", "draft"],
        "approved":   ["deprecated"],
        "deprecated": ["archived"],
        "archived":   [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_id(path: str, content_hash: str) -> str:
    """Stable artifact ID = hash(path+content_hash)."""
    raw = f"{path}::{content_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _detect_content_type(path: str) -> str:
    """Detect content type from file extension."""
    ext = Path(path).suffix.lower()
    mapping = {
        ".md": ContentType.MARKDOWN.value,
        ".json": ContentType.JSON.value,
        ".py": ContentType.PYTHON.value,
        ".ts": ContentType.TYPESCRIPT.value,
        ".tsx": ContentType.TYPESCRIPT.value,
        ".yaml": ContentType.YAML.value,
        ".yml": ContentType.YAML.value,
        ".csv": ContentType.CSV.value,
        ".pdf": ContentType.PDF.value,
        ".docx": ContentType.DOCX.value,
        ".xlsx": ContentType.XLSX.value,
        ".pptx": ContentType.PPTX.value,
        ".log": ContentType.LOG.value,
    }
    return mapping.get(ext, ContentType.OTHER.value)


# ---------------------------------------------------------------------------
# Artifact data model
# ---------------------------------------------------------------------------

@dataclass
class Artifact:
    """Canonical artifact record in the registry."""
    artifact_id: str = ""
    source_system: str = ""            # "agent-codex" / "manual" / "deep-research"
    source_path: str = ""              # absolute path
    project_id: str = ""               # project this belongs to
    content_hash: str = ""             # SHA-256 of content
    content_type: str = "other"        # ContentType value
    file_size: int = 0
    created_at: str = ""
    modified_at: str = ""
    indexed_at: str = ""

    # Classification
    para_bucket: str = "unclassified"  # PARABucket value
    structural_role: str = "raw"       # StructuralRole value
    domain_tags: list[str] = field(default_factory=list)

    # Quality & governance
    quality_score: float = 0.0         # 0-1
    dup_status: str = "unique"         # DupStatus value
    dup_of: str = ""                   # artifact_id of duplicate target
    is_promoted: bool = False          # graduated to knowledge note
    review_due: str = ""               # ISO timestamp
    stability: str = "draft"           # Stability state machine
    quarantine_weight: float = 1.0     # 1.0=trusted, 0.3=hypothetical, 0.0=blocked

    # Metadata
    title: str = ""
    summary: str = ""
    word_count: int = 0
    capture_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id     TEXT PRIMARY KEY,
    source_system   TEXT NOT NULL DEFAULT '',
    source_path     TEXT NOT NULL,
    project_id      TEXT NOT NULL DEFAULT '',
    content_hash    TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'other',
    file_size       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT '',
    modified_at     TEXT NOT NULL DEFAULT '',
    indexed_at      TEXT NOT NULL DEFAULT '',
    para_bucket     TEXT NOT NULL DEFAULT 'unclassified',
    structural_role TEXT NOT NULL DEFAULT 'raw',
    domain_tags     TEXT NOT NULL DEFAULT '[]',
    quality_score   REAL NOT NULL DEFAULT 0.0,
    dup_status      TEXT NOT NULL DEFAULT 'unique',
    dup_of          TEXT NOT NULL DEFAULT '',
    is_promoted     INTEGER NOT NULL DEFAULT 0,
    review_due      TEXT NOT NULL DEFAULT '',
    stability       TEXT NOT NULL DEFAULT 'draft',
    quarantine_weight REAL NOT NULL DEFAULT 1.0,
    title           TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    word_count      INTEGER NOT NULL DEFAULT 0,
    capture_context TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_artifacts_path
    ON artifacts(source_path);
CREATE INDEX IF NOT EXISTS idx_artifacts_hash
    ON artifacts(content_hash);
CREATE INDEX IF NOT EXISTS idx_artifacts_para
    ON artifacts(para_bucket);
CREATE INDEX IF NOT EXISTS idx_artifacts_role
    ON artifacts(structural_role);
CREATE INDEX IF NOT EXISTS idx_artifacts_quality
    ON artifacts(quality_score);
CREATE INDEX IF NOT EXISTS idx_artifacts_project
    ON artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_dup
    ON artifacts(dup_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_stability
    ON artifacts(stability);

-- Dedup index: fast lookup by content_hash
CREATE INDEX IF NOT EXISTS idx_artifacts_dedup
    ON artifacts(content_hash, source_path);
"""


# ---------------------------------------------------------------------------
# ArtifactRegistry
# ---------------------------------------------------------------------------

# Type alias for registration callbacks
RegistrationCallback = Callable[["Artifact"], None]


class ArtifactRegistry:
    """
    SQLite-backed artifact registry with event-driven indexing.

    Usage::

        reg = ArtifactRegistry("/path/to/kb.db")

        # Auto-index via callback
        def on_registered(artifact):
            content = Path(artifact.source_path).read_text()
            hub.index_document(artifact.artifact_id, artifact.title, content)

        reg.subscribe(on_registered)

        # Register file - automatically triggers callback
        art = reg.register_file("/path/to/doc.md", source_system="manual")

        results = reg.search(para_bucket="project")
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._local = threading.local()
        self._callbacks: list[RegistrationCallback] = []
        with self._conn() as conn:
            conn.executescript(_DDL)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    # ── Event Subscription ───────────────────────────────────────────

    def subscribe(self, callback: RegistrationCallback) -> None:
        """Subscribe to artifact registration events.

        The callback will be invoked after each successful registration
        with the registered Artifact as argument.
        """
        self._callbacks.append(callback)
        logger.debug("Registered callback: %s", callback.__name__ if hasattr(callback, "__name__") else callback)

    def unsubscribe(self, callback: RegistrationCallback) -> None:
        """Unsubscribe from artifact registration events."""
        self._callbacks = [c for c in self._callbacks if c is not callback]

    def close(self) -> None:
        """Close the registry connection for the current thread and drop callbacks."""
        self._callbacks.clear()
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def _notify_registered(self, artifact: Artifact) -> None:
        """Notify all subscribers of a new/updated artifact."""
        for cb in self._callbacks:
            try:
                cb(artifact)
            except Exception:
                logger.exception("Error in registration callback %s", cb)

    # -- Registration --------------------------------------------------------

    def register_file(
        self,
        file_path: str | Path,
        *,
        source_system: str = "manual",
        project_id: str = "",
        para_bucket: str = "unclassified",
        structural_role: str = "raw",
        domain_tags: list[str] | None = None,
        auto_index: bool = True,
    ) -> Artifact:
        """
        Register a file in the artifact registry.
        If already registered with same content_hash, returns existing.
        If content changed, updates the record.

        Args:
            file_path: Path to the file to register
            source_system: Source system (e.g., "manual", "deep-research")
            project_id: Project ID for classification
            para_bucket: PARA bucket (project/area/resource/archive)
            structural_role: Role (evidence/analysis/spec/plan/decision/runbook/code)
            domain_tags: List of domain tags
            auto_index: If True, triggers registered callbacks for auto-indexing
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_bytes()
        c_hash = _content_hash(content)
        aid = _artifact_id(str(path), c_hash)
        stat = path.stat()

        # Check existing
        existing = self.get_by_path(str(path))
        if existing and existing.content_hash == c_hash:
            return existing  # No change

        # Build artifact
        art = Artifact(
            artifact_id=aid,
            source_system=source_system,
            source_path=str(path),
            project_id=project_id,
            content_hash=c_hash,
            content_type=_detect_content_type(str(path)),
            file_size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            indexed_at=_now_iso(),
            para_bucket=para_bucket,
            structural_role=structural_role,
            domain_tags=domain_tags or [],
            title=path.stem,
            word_count=len(content.decode("utf-8", errors="ignore").split()),
        )
        art.quality_score = self.compute_quality(art)

        self._upsert(art, notify=auto_index)
        return art

    def register_artifact(self, art: Artifact, auto_index: bool = True) -> str:
        """Register a pre-built Artifact object.

        Args:
            art: Artifact to register
            auto_index: If True, triggers registered callbacks for auto-indexing
        """
        self._upsert(art, notify=auto_index)
        return art.artifact_id

    def _upsert(self, art: Artifact, notify: bool = True) -> None:
        tags_json = json.dumps(art.domain_tags, ensure_ascii=False)
        ctx_json = json.dumps(art.capture_context, default=str, ensure_ascii=False)

        # Check if this is a new artifact or update
        existing = self.get(art.artifact_id)
        is_new = existing is None

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO artifacts
                   (artifact_id, source_system, source_path, project_id,
                    content_hash, content_type, file_size,
                    created_at, modified_at, indexed_at,
                    para_bucket, structural_role, domain_tags,
                    quality_score, dup_status, dup_of,
                    is_promoted, review_due, stability, quarantine_weight,
                    title, summary, word_count, capture_context)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    art.artifact_id, art.source_system, art.source_path,
                    art.project_id, art.content_hash, art.content_type,
                    art.file_size,
                    art.created_at, art.modified_at, art.indexed_at,
                    art.para_bucket, art.structural_role, tags_json,
                    art.quality_score, art.dup_status, art.dup_of,
                    1 if art.is_promoted else 0, art.review_due,
                    art.stability, art.quarantine_weight,
                    art.title, art.summary, art.word_count, ctx_json,
                ),
            )
            conn.commit()

        # Notify subscribers (only for new artifacts, or explicitly requested)
        if notify and is_new and self._callbacks:
            self._notify_registered(art)

    # -- Queries -------------------------------------------------------------

    def _row_to_artifact(self, row: sqlite3.Row) -> Artifact:
        return Artifact(
            artifact_id=row["artifact_id"],
            source_system=row["source_system"],
            source_path=row["source_path"],
            project_id=row["project_id"],
            content_hash=row["content_hash"],
            content_type=row["content_type"],
            file_size=row["file_size"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
            para_bucket=row["para_bucket"],
            structural_role=row["structural_role"],
            domain_tags=json.loads(row["domain_tags"]),
            quality_score=row["quality_score"],
            dup_status=row["dup_status"],
            dup_of=row["dup_of"],
            is_promoted=bool(row["is_promoted"]),
            review_due=row["review_due"],
            stability=row["stability"],
            quarantine_weight=row["quarantine_weight"],
            title=row["title"],
            summary=row["summary"],
            word_count=row["word_count"],
            capture_context=json.loads(row["capture_context"]),
        )

    def get(self, artifact_id: str) -> Optional[Artifact]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return self._row_to_artifact(row) if row else None

    def get_by_path(self, source_path: str) -> Optional[Artifact]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE source_path = ? ORDER BY indexed_at DESC LIMIT 1",
                (source_path,),
            ).fetchone()
        return self._row_to_artifact(row) if row else None

    def find_by_hash(self, content_hash: str) -> list[Artifact]:
        """Find all artifacts with the same content hash (exact duplicates)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE content_hash = ?",
                (content_hash,),
            ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def search(
        self,
        *,
        para_bucket: str = "",
        structural_role: str = "",
        project_id: str = "",
        min_quality: float = 0.0,
        dup_status: str = "",
        is_promoted: Optional[bool] = None,
        limit: int = 100,
    ) -> list[Artifact]:
        """Search artifacts with filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if para_bucket:
            clauses.append("para_bucket = ?")
            params.append(para_bucket)
        if structural_role:
            clauses.append("structural_role = ?")
            params.append(structural_role)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if min_quality > 0:
            clauses.append("quality_score >= ?")
            params.append(min_quality)
        if dup_status:
            clauses.append("dup_status = ?")
            params.append(dup_status)
        if is_promoted is not None:
            clauses.append("is_promoted = ?")
            params.append(1 if is_promoted else 0)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"""SELECT * FROM artifacts
                  WHERE {where}
                  ORDER BY quality_score DESC, modified_at DESC
                  LIMIT ?"""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def count(self, **kwargs: Any) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        for k, v in kwargs.items():
            if v is not None and v != "":
                clauses.append(f"{k} = ?")
                params.append(v)
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT count(*) as cnt FROM artifacts WHERE {where}",
                params,
            ).fetchone()
        return row["cnt"] if row else 0

    # -- Quality scoring -----------------------------------------------------

    def compute_quality(self, art: Artifact) -> float:
        """
        Compute quality score based on KB DR factors:
        - Provenance (human > agent with citations > agent without)
        - Freshness
        - Structure completeness
        - Content type bonus
        """
        score = 0.0

        # Provenance
        if art.source_system == "manual":
            score += 0.3
        elif art.source_system in ("deep-research", "funnel"):
            score += 0.25
        else:
            score += 0.15

        # Freshness (decay over 90 days)
        if art.modified_at:
            try:
                mod = datetime.fromisoformat(art.modified_at)
                now = datetime.now(timezone.utc)
                age_days = (now - mod).days
                freshness = max(0.0, 1.0 - age_days / 90)
                score += 0.25 * freshness
            except (ValueError, TypeError):
                score += 0.1

        # Structure (word count, content type)
        if art.word_count > 100:
            score += 0.15
        elif art.word_count > 30:
            score += 0.1
        else:
            score += 0.05

        # Content type bonus
        if art.content_type in (ContentType.MARKDOWN.value, ContentType.JSON.value):
            score += 0.15
        else:
            score += 0.1

        # Structural role bonus
        if art.structural_role in (
            StructuralRole.DECISION.value,
            StructuralRole.SPEC.value,
            StructuralRole.RUNBOOK.value,
        ):
            score += 0.15
        elif art.structural_role in (
            StructuralRole.ANALYSIS.value,
            StructuralRole.EVIDENCE.value,
        ):
            score += 0.1
        else:
            score += 0.05

        return min(1.0, round(score, 4))

    def update_quality(self, artifact_id: str) -> float:
        """Recompute and store quality score."""
        art = self.get(artifact_id)
        if not art:
            return 0.0
        score = self.compute_quality(art)
        with self._conn() as conn:
            conn.execute(
                "UPDATE artifacts SET quality_score = ? WHERE artifact_id = ?",
                (score, artifact_id),
            )
            conn.commit()
        return score

    # -- Governance: stability state machine ----------------------------------

    def transition_stability(
        self, artifact_id: str, new_state: str
    ) -> bool:
        """Transition an artifact's stability state.

        Enforces the state machine: draft→candidate→approved→deprecated→archived.
        Returns True on success, raises ValueError on invalid transition.
        """
        art = self.get(artifact_id)
        if not art:
            raise ValueError(f"Artifact not found: {artifact_id}")

        current = art.stability
        valid_next = Stability.TRANSITIONS.get(current, [])

        if new_state not in valid_next:
            raise ValueError(
                f"Invalid transition: {current} → {new_state}. "
                f"Valid next states: {valid_next}"
            )

        with self._conn() as conn:
            conn.execute(
                "UPDATE artifacts SET stability = ? WHERE artifact_id = ?",
                (new_state, artifact_id),
            )
            conn.commit()

        logger.info(
            "Stability transition: %s %s → %s",
            artifact_id, current, new_state,
        )
        return True

    def set_quarantine_weight(
        self, artifact_id: str, weight: float
    ) -> None:
        """Set the quarantine weight for an artifact.

        Weight semantics:
            1.0 = fully trusted (verified by human or agent success)
            0.7 = auto-gated (passed gate but unverified)
            0.3 = hypothetical (funnel intermediate, reduced retrieval weight)
            0.0 = blocked (quarantined, excluded from retrieval)
        """
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"Weight must be 0.0-1.0, got {weight}")

        with self._conn() as conn:
            conn.execute(
                "UPDATE artifacts SET quarantine_weight = ? WHERE artifact_id = ?",
                (weight, artifact_id),
            )
            conn.commit()
