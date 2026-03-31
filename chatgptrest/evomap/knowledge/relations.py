"""EvoMap Knowledge — Relation Layer.

WP4: Internal KG contract for tracking provenance and relations.
"""

from __future__ import annotations

import enum
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "evomap_knowledge.db"
)

_PROVENANCE_DDL = """
-- Provenance: full traceability for atoms
CREATE TABLE IF NOT EXISTS provenance (
    atom_id TEXT PRIMARY KEY,
    task_id TEXT,
    run_id TEXT,
    commit_hash TEXT,
    branch TEXT,
    agent_id TEXT,
    artifact_path TEXT,
    plan_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (atom_id) REFERENCES atoms(atom_id)
);
CREATE INDEX IF NOT EXISTS idx_provenance_commit ON provenance(commit_hash);
CREATE INDEX IF NOT EXISTS idx_provenance_agent ON provenance(agent_id);
CREATE INDEX IF NOT EXISTS idx_provenance_task ON provenance(task_id);
"""


class RelationType(str, enum.Enum):
    """Relation types connecting EvoMap graph nodes."""
    PRODUCED_BY = "produced_by"       # atom ← task/run
    DERIVED_FROM = "derived_from"     # atom ← source commit/file
    SUPERSEDES = "supersedes"         # atom → older atom
    REFERENCES = "references"         # atom ← entity
    APPROVED_IN = "approved_in"       # atom ← plan
    OBSERVED_BY = "observed_by"       # signal ← agent
    TRIGGERED_BY = "triggered_by"     # plan ← signal
    COMMIT_SOURCE = "commit_source"   # atom ← commit hash
    BRANCH_SOURCE = "branch_source"   # atom ← branch name
    AGENT_AUTHORED = "agent_authored" # atom ← agent id


def _now_iso() -> str:
    """Return current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProvenanceChain:
    """Full provenance trace for an atom."""
    atom_id: str
    task_id: str | None = None
    run_id: str | None = None
    commit_hash: str | None = None
    branch: str | None = None
    agent_id: str | None = None
    artifact_path: str | None = None
    plan_id: str | None = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ProvenanceChain:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RelationManager:
    """Manage relations and provenance in the knowledge graph."""

    def __init__(self, db_path: str | None = None, db=None):
        self.db_path = db_path or resolve_evomap_knowledge_runtime_db_path()
        self._external_db = db
        self._conn: sqlite3.Connection | None = None
        self._schema_initialized = False
        if db is not None:
            self._conn = db._conn

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            if not self._schema_initialized:
                self._init_schema()
                self._schema_initialized = True
            return self._conn
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        self._schema_initialized = True
        return self._conn

    def close(self):
        if self._conn and not self._external_db:
            self._conn.close()
            self._conn = None
        self._schema_initialized = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        if not self._external_db:
            self.close()

    def _init_schema(self):
        """Initialize provenance table if not exists."""
        try:
            self._conn.executescript(_PROVENANCE_DDL)
            self._conn.commit()
        except Exception as e:
            logger.debug("Provenance table check: %s", e)

    def add_provenance(self, atom_id: str, chain: ProvenanceChain, *, commit: bool = True) -> None:
        """Add provenance for an atom without overwriting the first audit record."""
        conn = self.connect()
        cursor = conn.execute(
            """INSERT OR IGNORE INTO provenance
               (atom_id, task_id, run_id, commit_hash, branch, agent_id, artifact_path, plan_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                atom_id,
                chain.task_id,
                chain.run_id,
                chain.commit_hash,
                chain.branch,
                chain.agent_id,
                chain.artifact_path,
                chain.plan_id,
                chain.created_at,
            ),
        )
        if commit:
            conn.commit()
        if cursor.rowcount:
            logger.info("Added provenance for atom %s", atom_id)
        else:
            logger.info("Preserved existing provenance for atom %s", atom_id)

    def get_provenance(self, atom_id: str) -> ProvenanceChain | None:
        """Get provenance chain for an atom."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM provenance WHERE atom_id = ?",
            (atom_id,),
        ).fetchone()
        return ProvenanceChain(**dict(row)) if row else None

    def get_supersession_chain(self, atom_id: str) -> list[str]:
        """Follow supersedes edges to get full supersession chain."""
        chain = []
        current_id = atom_id
        visited = set()
        conn = self.connect()

        while True:
            if current_id in visited:
                logger.warning("Detected supersession cycle while traversing atom %s", atom_id)
                break
            visited.add(current_id)
            row = conn.execute(
                "SELECT to_id FROM edges WHERE from_id = ? AND edge_type = ?",
                (current_id, RelationType.SUPERSEDES.value),
            ).fetchone()

            if not row:
                break
            chain.append(row[0])
            current_id = row[0]

        return chain

    def find_by_commit(self, commit_hash: str) -> list[str]:
        """Find atom IDs originating from a specific commit."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT atom_id FROM provenance WHERE commit_hash = ?",
            (commit_hash,),
        ).fetchall()
        return [r[0] for r in rows]

    def find_by_agent(self, agent_id: str) -> list[str]:
        """Find atom IDs authored by a specific agent."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT atom_id FROM provenance WHERE agent_id = ?",
            (agent_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def find_by_task(self, task_id: str) -> list[str]:
        """Find atom IDs from a specific task."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT atom_id FROM provenance WHERE task_id = ?",
            (task_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: RelationType,
        from_kind: str = "atom",
        to_kind: str = "atom",
        weight: float = 1.0,
    ) -> None:
        """Add a relation edge between two nodes."""
        from chatgptrest.evomap.knowledge.schema import Edge
        edge = Edge(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type.value,
            from_kind=from_kind,
            to_kind=to_kind,
            weight=weight,
        )
        conn = self.connect()
        conn.execute(
            """INSERT OR REPLACE INTO edges (from_id, to_id, edge_type, weight, from_kind, to_kind, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (edge.from_id, edge.to_id, edge.edge_type, edge.weight, edge.from_kind, edge.to_kind, edge.meta_json),
        )
        conn.commit()
        logger.info("Added edge %s -> %s (%s)", from_id, to_id, edge_type.value)
