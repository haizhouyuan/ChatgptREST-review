"""EvoMap Knowledge DB — SQLite + FTS5 database layer.

Manages the knowledge store with:
- 6 core tables (documents, episodes, atoms, evidence, entities, edges)
- FTS5 virtual table for full-text search on atoms
- Incremental hash-based change detection
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover - non-posix fallback
    import fcntl
except Exception:  # pragma: no cover - non-posix fallback
    fcntl = None

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path

from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Edge,
    Entity,
    Episode,
    Evidence,
)

logger = logging.getLogger(__name__)

_SQLITE_TIMEOUT_SECONDS = 30.0
_SQLITE_BUSY_TIMEOUT_MS = 30000
_SQLITE_WRITE_RETRY_COUNT = 3
_SQLITE_WRITE_RETRY_SLEEP_SECONDS = 0.2
_INIT_LOCK = threading.Lock()
_INITIALIZED_DB_PATHS: set[str] = set()

# Default DB path
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "evomap_knowledge.db"
)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
-- Documents: raw carriers
CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    source       TEXT NOT NULL DEFAULT '',
    project      TEXT NOT NULL DEFAULT '',
    raw_ref      TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL DEFAULT 0,
    updated_at   REAL NOT NULL DEFAULT 0,
    hash         TEXT NOT NULL DEFAULT '',
    meta_json    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash);

-- Episodes: event units
CREATE TABLE IF NOT EXISTS episodes (
    episode_id        TEXT PRIMARY KEY,
    doc_id            TEXT NOT NULL DEFAULT '',
    episode_type      TEXT NOT NULL DEFAULT '',
    title             TEXT NOT NULL DEFAULT '',
    summary           TEXT NOT NULL DEFAULT '',
    start_ref         TEXT NOT NULL DEFAULT '',
    end_ref           TEXT NOT NULL DEFAULT '',
    time_start        REAL NOT NULL DEFAULT 0,
    time_end          REAL NOT NULL DEFAULT 0,
    turn_count        INTEGER NOT NULL DEFAULT 0,
    source_ext        TEXT NOT NULL DEFAULT '{}',
    followup_depth    INTEGER NOT NULL DEFAULT 0,
    constraint_growth INTEGER NOT NULL DEFAULT 0,
    reversal_count    INTEGER NOT NULL DEFAULT 0,
    convergence_score REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
CREATE INDEX IF NOT EXISTS idx_episodes_doc ON episodes(doc_id);
CREATE INDEX IF NOT EXISTS idx_episodes_type ON episodes(episode_type);

-- Atoms: knowledge units
CREATE TABLE IF NOT EXISTS atoms (
    atom_id            TEXT PRIMARY KEY,
    episode_id         TEXT NOT NULL DEFAULT '',
    atom_type          TEXT NOT NULL DEFAULT 'qa',
    question           TEXT NOT NULL DEFAULT '',
    answer             TEXT NOT NULL DEFAULT '',
    canonical_question TEXT NOT NULL DEFAULT '',
    alt_questions      TEXT NOT NULL DEFAULT '[]',
    constraints        TEXT NOT NULL DEFAULT '[]',
    prerequisites      TEXT NOT NULL DEFAULT '[]',
    intent             TEXT NOT NULL DEFAULT '',
    format             TEXT NOT NULL DEFAULT 'plain',
    applicability      TEXT NOT NULL DEFAULT '{}',
    scope_project      TEXT NOT NULL DEFAULT '',
    scope_component    TEXT NOT NULL DEFAULT '',
    stability          TEXT NOT NULL DEFAULT 'versioned',
    status             TEXT NOT NULL DEFAULT 'candidate',
    valid_from         REAL NOT NULL DEFAULT 0,
    valid_to           REAL NOT NULL DEFAULT 0,
    quality_auto       REAL NOT NULL DEFAULT 0,
    value_auto         REAL NOT NULL DEFAULT 0,
    novelty            REAL NOT NULL DEFAULT 0,
    groundedness       REAL NOT NULL DEFAULT 0,
    confidence         REAL NOT NULL DEFAULT 0,
    reusability        REAL NOT NULL DEFAULT 0,
    scores_json        TEXT NOT NULL DEFAULT '{}',
    source_quality     REAL NOT NULL DEFAULT 0,
    hash               TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_atoms_episode ON atoms(episode_id);
CREATE INDEX IF NOT EXISTS idx_atoms_type ON atoms(atom_type);
CREATE INDEX IF NOT EXISTS idx_atoms_status ON atoms(status);
CREATE INDEX IF NOT EXISTS idx_atoms_stability ON atoms(stability);
CREATE INDEX IF NOT EXISTS idx_atoms_hash ON atoms(hash);

-- FTS5 virtual table for full-text search on atoms
CREATE VIRTUAL TABLE IF NOT EXISTS atoms_fts USING fts5(
    question,
    answer,
    canonical_question,
    content='atoms',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS atoms_ai AFTER INSERT ON atoms BEGIN
    INSERT INTO atoms_fts(rowid, question, answer, canonical_question)
    VALUES (new.rowid, new.question, new.answer, new.canonical_question);
END;

CREATE TRIGGER IF NOT EXISTS atoms_ad AFTER DELETE ON atoms BEGIN
    INSERT INTO atoms_fts(atoms_fts, rowid, question, answer, canonical_question)
    VALUES ('delete', old.rowid, old.question, old.answer, old.canonical_question);
END;

CREATE TRIGGER IF NOT EXISTS atoms_au AFTER UPDATE ON atoms BEGIN
    INSERT INTO atoms_fts(atoms_fts, rowid, question, answer, canonical_question)
    VALUES ('delete', old.rowid, old.question, old.answer, old.canonical_question);
    INSERT INTO atoms_fts(rowid, question, answer, canonical_question)
    VALUES (new.rowid, new.question, new.answer, new.canonical_question);
END;

-- Evidence: links atoms to source material
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id    TEXT PRIMARY KEY,
    atom_id        TEXT NOT NULL DEFAULT '',
    doc_id         TEXT NOT NULL DEFAULT '',
    span_ref       TEXT NOT NULL DEFAULT '',
    excerpt        TEXT NOT NULL DEFAULT '',
    excerpt_hash   TEXT NOT NULL DEFAULT '',
    evidence_role  TEXT NOT NULL DEFAULT '',
    weight         REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (atom_id) REFERENCES atoms(atom_id),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_atom ON evidence(atom_id);
CREATE INDEX IF NOT EXISTS idx_evidence_doc ON evidence(doc_id);

-- Entities: named things (repos, skills, components)
CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    normalized_name TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_norm ON entities(normalized_name);

-- Edges: relationships between objects
CREATE TABLE IF NOT EXISTS edges (
    from_id   TEXT NOT NULL,
    to_id     TEXT NOT NULL,
    edge_type TEXT NOT NULL DEFAULT '',
    weight    REAL NOT NULL DEFAULT 1.0,
    from_kind TEXT NOT NULL DEFAULT '',
    to_kind   TEXT NOT NULL DEFAULT '',
    meta_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (from_id, to_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_from_kind ON edges(from_kind);
CREATE INDEX IF NOT EXISTS idx_edges_to_kind ON edges(to_kind);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO _schema_version (version, applied_at) VALUES (1, 0);

-- Groundedness audit trail (WP1)
CREATE TABLE IF NOT EXISTS groundedness_audit (
    audit_id TEXT PRIMARY KEY,
    atom_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    overall_score REAL NOT NULL DEFAULT 0,
    path_score REAL NOT NULL DEFAULT 0,
    service_score REAL NOT NULL DEFAULT 0,
    staleness_score REAL NOT NULL DEFAULT 0,
    code_symbol_score REAL NOT NULL DEFAULT 0,
    evidence_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_groundedness_audit_atom ON groundedness_audit(atom_id);
CREATE INDEX IF NOT EXISTS idx_groundedness_audit_timestamp ON groundedness_audit(timestamp);

-- Promotion audit trail (WP2)
CREATE TABLE IF NOT EXISTS promotion_audit (
    audit_id TEXT PRIMARY KEY,
    atom_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    groundedness_result TEXT,
    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_promotion_audit_atom ON promotion_audit(atom_id);
CREATE INDEX IF NOT EXISTS idx_promotion_audit_created ON promotion_audit(created_at);
"""


# ---------------------------------------------------------------------------
# KnowledgeDB
# ---------------------------------------------------------------------------

class KnowledgeDB:
    """SQLite-backed knowledge store with FTS5 search."""

    SCHEMA_VERSION = 3

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or resolve_evomap_knowledge_runtime_db_path()
        self._conn: sqlite3.Connection | None = None
        self._write_lock = threading.RLock()

    # -- Connection management --

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=_SQLITE_TIMEOUT_SECONDS,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
        self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    # -- Schema --

    def init_schema(self):
        """Create all tables and indices, with forward-compatible migrations."""
        conn = self.connect()
        cacheable = self.db_path != ":memory:"
        db_key = str(Path(self.db_path).expanduser().resolve()) if cacheable else ":memory:"

        with _INIT_LOCK:
            if cacheable and db_key in _INITIALIZED_DB_PATHS:
                return

            fd: int | None = None
            try:
                if cacheable and fcntl is not None:
                    lock_path = Path(str(db_key) + ".init.lock")
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    if db_key in _INITIALIZED_DB_PATHS:
                        return

                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_DDL)

                # Migration: align atom scope columns with runtime retrieval shape.
                try:
                    atom_cols = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
                    scope_columns = [
                        ("scope_project", "TEXT NOT NULL DEFAULT ''"),
                        ("scope_component", "TEXT NOT NULL DEFAULT ''"),
                    ]
                    added = []
                    for col_name, col_def in scope_columns:
                        if col_name not in atom_cols:
                            conn.execute(f"ALTER TABLE atoms ADD COLUMN {col_name} {col_def}")
                            added.append(col_name)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_scope_project ON atoms(scope_project)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_scope_component ON atoms(scope_component)")
                    if added:
                        logger.info("Migrated atoms table: added scope columns %s", added)
                except Exception as e:
                    logger.debug("Atom scope migration check: %s", e)

                # Migration: add from_kind/to_kind to edges for pre-Phase 7 databases
                try:
                    cols = {r[1] for r in conn.execute("PRAGMA table_info(edges)").fetchall()}
                    if "from_kind" not in cols:
                        conn.execute('ALTER TABLE edges ADD COLUMN from_kind TEXT NOT NULL DEFAULT "atom"')
                        conn.execute('ALTER TABLE edges ADD COLUMN to_kind TEXT NOT NULL DEFAULT "atom"')
                        logger.info("Migrated edges table: added from_kind/to_kind columns")
                except Exception as e:
                    logger.debug("Edge migration check: %s", e)

                # P1 Migration: add evolution chain & promotion columns (Issue #93)
                try:
                    atom_cols = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
                    p1_columns = [
                        ("promotion_status", "TEXT NOT NULL DEFAULT 'staged'"),
                        ("superseded_by", "TEXT NOT NULL DEFAULT ''"),
                        ("chain_id", "TEXT NOT NULL DEFAULT ''"),
                        ("chain_rank", "INTEGER NOT NULL DEFAULT 0"),
                        ("is_chain_head", "INTEGER NOT NULL DEFAULT 0"),
                        ("promotion_reason", "TEXT NOT NULL DEFAULT ''"),
                    ]
                    added = []
                    for col_name, col_def in p1_columns:
                        if col_name not in atom_cols:
                            conn.execute(f"ALTER TABLE atoms ADD COLUMN {col_name} {col_def}")
                            added.append(col_name)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_promotion ON atoms(promotion_status)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_chain ON atoms(chain_id)")
                    if added:
                        logger.info("P1 migration: added columns %s to atoms", added)
                except Exception as e:
                    logger.debug("P1 migration check: %s", e)

                # WP1/WP2 Migration: add groundedness_audit and promotion_audit tables
                try:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS groundedness_audit (
                            audit_id TEXT PRIMARY KEY,
                            atom_id TEXT NOT NULL,
                            timestamp REAL NOT NULL,
                            passed INTEGER NOT NULL DEFAULT 0,
                            overall_score REAL NOT NULL DEFAULT 0,
                            path_score REAL NOT NULL DEFAULT 0,
                            service_score REAL NOT NULL DEFAULT 0,
                            staleness_score REAL NOT NULL DEFAULT 0,
                            code_symbol_score REAL NOT NULL DEFAULT 0,
                            evidence_json TEXT NOT NULL DEFAULT '[]'
                        )
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_groundedness_audit_atom ON groundedness_audit(atom_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_groundedness_audit_timestamp ON groundedness_audit(timestamp)")
                except Exception as e:
                    logger.debug("Groundedness audit table check: %s", e)

                try:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS promotion_audit (
                            audit_id TEXT PRIMARY KEY,
                            atom_id TEXT NOT NULL,
                            from_status TEXT NOT NULL,
                            to_status TEXT NOT NULL,
                            reason TEXT NOT NULL,
                            actor TEXT NOT NULL DEFAULT 'system',
                            groundedness_result TEXT,
                            created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
                        )
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_promotion_audit_atom ON promotion_audit(atom_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_promotion_audit_created ON promotion_audit(created_at)")
                except Exception as e:
                    logger.debug("Promotion audit table check: %s", e)

                conn.commit()
                if cacheable:
                    _INITIALIZED_DB_PATHS.add(db_key)
                logger.info("EvoMap knowledge DB initialized at %s", self.db_path)
            finally:
                if fd is not None:
                    try:
                        if fcntl is not None:
                            fcntl.flock(fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                    try:
                        os.close(fd)
                    except Exception:
                        pass

    # -- Generic CRUD --

    def _execute_write_with_retry(
        self,
        *,
        table: str,
        sql: str,
        params: list[Any],
        commit: bool = True,
    ) -> sqlite3.Cursor | None:
        with self._write_lock:
            conn = self.connect()
            last_error: sqlite3.OperationalError | None = None

            for attempt in range(_SQLITE_WRITE_RETRY_COUNT + 1):
                try:
                    cur = conn.execute(sql, params)
                    if commit:
                        conn.commit()
                    return cur
                except sqlite3.OperationalError as exc:
                    if "database is locked" not in str(exc).lower():
                        raise
                    last_error = exc
                    if attempt >= _SQLITE_WRITE_RETRY_COUNT:
                        raise
                    logger.warning(
                        "KnowledgeDB write locked on %s (attempt %s/%s); retrying",
                        table,
                        attempt + 1,
                        _SQLITE_WRITE_RETRY_COUNT + 1,
                    )
                    try:
                        conn.rollback()
                    except sqlite3.Error:
                        pass
                    time.sleep(_SQLITE_WRITE_RETRY_SLEEP_SECONDS * (attempt + 1))

            if last_error is not None:
                raise last_error

        return None

    def _insert(self, table: str, row: dict, *, commit: bool = True):
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        self._execute_write_with_retry(table=table, sql=sql, params=list(row.values()), commit=commit)

    def _insert_if_absent(self, table: str, row: dict, *, commit: bool = True) -> bool:
        """INSERT OR IGNORE — keeps existing row if PK already exists.

        Returns True if a new row was inserted, False if it already existed.
        """
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        cur = self._execute_write_with_retry(
            table=table,
            sql=f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
            params=list(row.values()),
            commit=commit,
        )
        return bool(cur and cur.rowcount > 0)

    def _get(self, table: str, pk_col: str, pk_val: str) -> dict | None:
        conn = self.connect()
        cur = conn.execute(f"SELECT * FROM {table} WHERE {pk_col} = ?", (pk_val,))
        row = cur.fetchone()
        return dict(row) if row else None

    def _count(self, table: str) -> int:
        conn = self.connect()
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # -- Documents --

    def put_document(self, doc: Document, *, commit: bool = True):
        self._insert("documents", doc.to_row(), commit=commit)

    def put_document_if_absent(self, doc: Document) -> bool:
        """Insert document only if doc_id doesn't already exist."""
        return self._insert_if_absent("documents", doc.to_row())

    def get_document(self, doc_id: str) -> Document | None:
        row = self._get("documents", "doc_id", doc_id)
        return Document.from_row(row) if row else None

    def doc_exists_by_hash(self, hash_val: str) -> bool:
        conn = self.connect()
        cur = conn.execute("SELECT 1 FROM documents WHERE hash = ? LIMIT 1", (hash_val,))
        return cur.fetchone() is not None

    # -- Episodes --

    def put_episode(self, ep: Episode, *, commit: bool = True):
        self._insert("episodes", ep.to_row(), commit=commit)

    def put_episode_if_absent(self, ep: Episode) -> bool:
        """Insert episode only if episode_id doesn't already exist."""
        return self._insert_if_absent("episodes", ep.to_row())

    def get_episode(self, episode_id: str) -> Episode | None:
        row = self._get("episodes", "episode_id", episode_id)
        return Episode.from_row(row) if row else None

    def list_episodes_by_doc(self, doc_id: str) -> list[Episode]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM episodes WHERE doc_id = ? ORDER BY time_start", (doc_id,)
        ).fetchall()
        return [Episode.from_row(dict(r)) for r in rows]

    def _parse_atom_applicability(self, atom: Atom) -> dict[str, Any]:
        try:
            applicability = getattr(atom, "applicability", "")
            payload = json.loads(applicability) if applicability else {}
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _derive_atom_scope_project(self, atom: Atom) -> str:
        scope_project = getattr(atom, "scope_project", "")
        if scope_project:
            return str(scope_project).strip()
        app = self._parse_atom_applicability(atom)
        project = app.get("project")
        if isinstance(project, str) and project.strip():
            return project.strip()
        episode_id = getattr(atom, "episode_id", "")
        if episode_id:
            conn = self.connect()
            row = conn.execute(
                """
                SELECT d.project
                FROM episodes e
                JOIN documents d ON d.doc_id = e.doc_id
                WHERE e.episode_id = ?
                LIMIT 1
                """,
                (episode_id,),
            ).fetchone()
            if row:
                project = row[0]
                if isinstance(project, str) and project.strip():
                    return project.strip()
        return ""

    def _derive_atom_scope_component(self, atom: Atom) -> str:
        scope_component = getattr(atom, "scope_component", "")
        if scope_component:
            return str(scope_component).strip()
        app = self._parse_atom_applicability(atom)
        for key in ("component", "scope_component"):
            component = app.get(key)
            if isinstance(component, str) and component.strip():
                return component.strip()
        return ""

    def _prepare_atom_for_write(self, atom: Atom) -> Atom:
        setattr(atom, "scope_project", self._derive_atom_scope_project(atom))
        setattr(atom, "scope_component", self._derive_atom_scope_component(atom))
        if not getattr(atom, "hash", ""):
            atom.compute_hash()
        return atom

    # -- Atoms --

    def put_atom(self, atom: Atom, *, commit: bool = True):
        self._prepare_atom_for_write(atom)
        self._insert("atoms", atom.to_row(), commit=commit)

    def put_atom_if_absent(self, atom: Atom) -> bool:
        """Insert atom only if atom_id doesn't already exist."""
        self._prepare_atom_for_write(atom)
        return self._insert_if_absent("atoms", atom.to_row())

    def get_atom(self, atom_id: str) -> Atom | None:
        row = self._get("atoms", "atom_id", atom_id)
        return Atom.from_row(row) if row else None

    def atom_exists_by_hash(self, hash_val: str) -> bool:
        conn = self.connect()
        cur = conn.execute("SELECT 1 FROM atoms WHERE hash = ? LIMIT 1", (hash_val,))
        return cur.fetchone() is not None

    def list_atoms_by_status(self, status: str, limit: int = 100) -> list[Atom]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM atoms WHERE status = ? LIMIT ?", (status, limit)
        ).fetchall()
        return [Atom.from_row(dict(r)) for r in rows]

    def list_atoms_by_promotion(self, promotion_status: str, limit: int = 100) -> list[Atom]:
        """List atoms by promotion_status."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM atoms WHERE promotion_status = ? LIMIT ?",
            (promotion_status, limit),
        ).fetchall()
        return [Atom.from_row(dict(r)) for r in rows]

    def list_chain(self, chain_id: str) -> list[Atom]:
        """Get all atoms in a chain ordered by chain_rank."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM atoms WHERE chain_id = ? ORDER BY chain_rank",
            (chain_id,),
        ).fetchall()
        return [Atom.from_row(dict(r)) for r in rows]

    # -- Evidence --

    def put_evidence(self, ev: Evidence, *, commit: bool = True):
        self._insert("evidence", ev.to_row(), commit=commit)

    def list_evidence_for_atom(self, atom_id: str) -> list[Evidence]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM evidence WHERE atom_id = ?", (atom_id,)
        ).fetchall()
        return [Evidence.from_row(dict(r)) for r in rows]

    # -- Entities --

    def put_entity(self, ent: Entity, *, commit: bool = True):
        self._insert("entities", ent.to_row(), commit=commit)

    # -- Edges --

    def put_edge(self, edge: Edge, *, commit: bool = True):
        self._insert("edges", edge.to_row(), commit=commit)

    def get_edges_from(self, from_id: str) -> list[Edge]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM edges WHERE from_id = ?", (from_id,)
        ).fetchall()
        return [Edge.from_row(dict(r)) for r in rows]

    def get_edges_to(self, to_id: str) -> list[Edge]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM edges WHERE to_id = ?", (to_id,)
        ).fetchall()
        return [Edge.from_row(dict(r)) for r in rows]

    # -- FTS5 Search --

    def search_fts(self, query: str, limit: int = 20) -> list[Atom]:
        """Full-text search on atoms using FTS5."""
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT a.* FROM atoms a
            JOIN atoms_fts f ON a.rowid = f.rowid
            WHERE atoms_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [Atom.from_row(dict(r)) for r in rows]

    # -- Stats --

    def stats(self) -> dict:
        """Return counts for all tables."""
        return {
            "documents": self._count("documents"),
            "episodes": self._count("episodes"),
            "atoms": self._count("atoms"),
            "evidence": self._count("evidence"),
            "entities": self._count("entities"),
            "edges": self._count("edges"),
        }

    # -- Batch operations --

    def commit(self):
        if self._conn:
            self._conn.commit()

    def rollback(self):
        if self._conn:
            self._conn.rollback()

    def bulk_put_atoms(self, atoms: list[Atom]):
        """Insert multiple atoms in a single transaction."""
        conn = self.connect()
        for atom in atoms:
            self._prepare_atom_for_write(atom)
            self._insert("atoms", atom.to_row(), commit=False)
        conn.commit()

    # -- Groundedness audit --

    def list_groundedness_audits(self, atom_id: str, limit: int = 10) -> list[dict]:
        """Get groundedness audit records for an atom."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM groundedness_audit WHERE atom_id = ? ORDER BY timestamp DESC LIMIT ?",
            (atom_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Promotion audit --

    def list_promotion_audits(self, atom_id: str, limit: int = 20) -> list[dict]:
        """Get promotion audit trail for an atom."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM promotion_audit WHERE atom_id = ? ORDER BY created_at DESC LIMIT ?",
            (atom_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_promotion_audit(
        self,
        audit_id: str,
        atom_id: str,
        from_status: str,
        to_status: str,
        reason: str,
        actor: str = "system",
        groundedness_result: str | None = None,
        *,
        commit: bool = True,
    ):
        """Add a promotion audit record."""
        conn = self.connect()
        conn.execute(
            """INSERT INTO promotion_audit
               (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result),
        )
        if commit:
            conn.commit()
