"""EvoMap Light Sandbox — isolated experimentation environment.

Creates isolated copies of EvoMap state for experiments without
polluting active truth. Uses SQLite file copy for isolation.

References:
- Issue #99 WP6
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.relations import RelationManager
from chatgptrest.evomap.knowledge.schema import Atom, Document, Edge, Entity, Episode, Evidence, PromotionStatus

logger = logging.getLogger(__name__)


def _hash_file(path: str) -> str:
    """Compute SHA256 hash of a file."""
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires_at(ttl_hours: int) -> str:
    dt = datetime.now(timezone.utc).timestamp() + (ttl_hours * 3600)
    return datetime.fromtimestamp(dt, timezone.utc).isoformat()


@dataclass
class SandboxInfo:
    """Metadata for a sandbox."""
    name: str
    description: str
    created_at: str
    expires_at: str
    db_path: str
    base_snapshot_hash: str


@dataclass
class SandboxDiff:
    """Diff between sandbox and production DB."""
    added_atoms: list[str]
    modified_atoms: list[str]
    added_entities: list[str]
    added_edges: int


@dataclass
class MergeResult:
    """Result of merging atoms back to production."""
    ok: bool
    merged_atom_ids: list[str]
    conflicts: list[str]
    message: str


class EvoMapSandbox:
    """Lightweight sandbox for EvoMap experiments.

    Creates isolated copies of the production KnowledgeDB for
    experimentation without affecting active truth.

    Usage::

        sandbox = EvoMapSandbox(
            base_db_path="/data/evomap_knowledge.db",
            sandbox_dir="/data/sandboxes"
        )

        # Create a new sandbox
        info = sandbox.create("experiment-001", description="Test new promotion logic")

        # Get sandbox DB for experimentation
        db = sandbox.get("experiment-001")

        # Make changes in sandbox...
        db.put_atom(new_atom)

        # Compute diff
        diff = sandbox.diff("experiment-001")

        # Merge specific atoms back to production
        result = sandbox.merge_back("experiment-001", atom_ids=["at_xxx"])

        # Clean up expired sandboxes
        cleaned = sandbox.cleanup_expired()
    """

    def __init__(self, base_db_path: str, sandbox_dir: str):
        self.base_db_path = base_db_path
        self.sandbox_dir = sandbox_dir
        self._metadata_path = os.path.join(sandbox_dir, "sandboxes.json")
        self._sandboxes: dict[str, SandboxInfo] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load sandbox metadata from JSON file."""
        if os.path.exists(self._metadata_path):
            try:
                with open(self._metadata_path) as f:
                    data = json.load(f)
                    for name, info in data.items():
                        self._sandboxes[name] = SandboxInfo(**info)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Failed to load sandbox metadata: %s", e)

    def _save_metadata(self) -> None:
        """Save sandbox metadata to JSON file."""
        os.makedirs(self.sandbox_dir, exist_ok=True)
        data = {name: asdict(info) for name, info in self._sandboxes.items()}
        with open(self._metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    def _get_sandbox_path(self, name: str) -> str:
        """Get path to sandbox database."""
        return os.path.join(self.sandbox_dir, name, "knowledge.db")

    def create(self, name: str, *, description: str = "", ttl_hours: int = 72) -> SandboxInfo:
        """Create a new sandbox by copying the production KnowledgeDB.

        Args:
            name: Unique name for the sandbox
            description: Optional description
            ttl_hours: Time-to-live in hours (default 72)

        Returns:
            SandboxInfo with metadata
        """
        if name in self._sandboxes:
            raise ValueError(f"Sandbox '{name}' already exists")

        if not os.path.exists(self.base_db_path):
            raise FileNotFoundError(f"Base database not found: {self.base_db_path}")

        sandbox_path = self._get_sandbox_path(name)
        sandbox_dir = os.path.dirname(sandbox_path)
        os.makedirs(sandbox_dir, exist_ok=True)

        base_hash = _hash_file(self.base_db_path)
        shutil.copy2(self.base_db_path, sandbox_path)

        info = SandboxInfo(
            name=name,
            description=description,
            created_at=_now_iso(),
            expires_at=_expires_at(ttl_hours),
            db_path=sandbox_path,
            base_snapshot_hash=base_hash,
        )
        self._sandboxes[name] = info
        self._save_metadata()

        logger.info("Created sandbox '%s' at %s (TTL: %dh)", name, sandbox_path, ttl_hours)
        return info

    def get(self, name: str) -> KnowledgeDB | None:
        """Get a sandbox KnowledgeDB instance for experimentation.

        Args:
            name: Sandbox name

        Returns:
            KnowledgeDB instance connected to sandbox, or None if not found
        """
        if name not in self._sandboxes:
            return None

        info = self._sandboxes[name]
        if not os.path.exists(info.db_path):
            logger.warning("Sandbox '%s' DB not found at %s", name, info.db_path)
            return None

        db = KnowledgeDB(db_path=info.db_path)
        db.connect()
        return db

    def list_sandboxes(self) -> list[SandboxInfo]:
        """List all sandboxes with metadata.

        Returns:
            List of SandboxInfo objects
        """
        return list(self._sandboxes.values())

    def diff(self, name: str) -> SandboxDiff | None:
        """Compute diff between sandbox and production DB.

        Args:
            name: Sandbox name

        Returns:
            SandboxDiff with changed atoms/entities/edges, or None if sandbox not found
        """
        if name not in self._sandboxes:
            return None

        info = self._sandboxes[name]
        sandbox_db = KnowledgeDB(db_path=info.db_path)
        sandbox_db.connect()

        production_db = None
        if os.path.exists(self.base_db_path):
            production_db = KnowledgeDB(db_path=self.base_db_path)
            production_db.connect()

        try:
            conn = sandbox_db.connect()
            rows = conn.execute("SELECT * FROM atoms").fetchall()
            sandbox_atoms = [Atom.from_row(dict(r)) for r in rows]

            sandbox_atom_ids = {a.atom_id for a in sandbox_atoms}

            if production_db:
                prod_conn = production_db.connect()
                prod_rows = prod_conn.execute("SELECT * FROM atoms").fetchall()
                prod_atoms = [Atom.from_row(dict(r)) for r in prod_rows]
                prod_atom_ids = {a.atom_id for a in prod_atoms}
                added_atoms = list(sandbox_atom_ids - prod_atom_ids)

                modified_atoms = []
                for atom_id in sandbox_atom_ids & prod_atom_ids:
                    prod_atom = production_db.get_atom(atom_id)
                    sandbox_atom = sandbox_db.get_atom(atom_id)
                    if prod_atom and sandbox_atom and prod_atom.hash != sandbox_atom.hash:
                        modified_atoms.append(atom_id)

                prod_stats = production_db.stats()
            else:
                added_atoms = list(sandbox_atom_ids)
                modified_atoms = []
                prod_stats = {"entities": 0, "edges": 0}

            sandbox_stats = sandbox_db.stats()

            added_entities = []
            if sandbox_stats["entities"] > prod_stats["entities"]:
                added_entities = ["entity_diff_not_implemented"]

            added_edges = max(0, sandbox_stats["edges"] - prod_stats["edges"])

            return SandboxDiff(
                added_atoms=added_atoms,
                modified_atoms=modified_atoms,
                added_entities=added_entities,
                added_edges=added_edges,
            )
        finally:
            sandbox_db.close()
            if production_db:
                production_db.close()

    def _get_entity(self, db: KnowledgeDB, entity_id: str) -> Entity | None:
        row = db.connect().execute(
            "SELECT * FROM entities WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        return Entity.from_row(dict(row)) if row else None

    def _get_evidence(self, db: KnowledgeDB, evidence_id: str) -> Evidence | None:
        row = db.connect().execute(
            "SELECT * FROM evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        return Evidence.from_row(dict(row)) if row else None

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _copy_document_if_needed(self, sandbox_db: KnowledgeDB, production_db: KnowledgeDB, doc_id: str) -> None:
        if not doc_id:
            return
        sandbox_doc = sandbox_db.get_document(doc_id)
        if sandbox_doc is None:
            raise ValueError(f"Document {doc_id} missing in sandbox")
        production_doc = production_db.get_document(doc_id)
        if production_doc is None:
            production_db.put_document(sandbox_doc, commit=False)
            return
        if production_doc.to_row() != sandbox_doc.to_row():
            raise ValueError(f"Document {doc_id} has conflicting version in production")

    def _copy_episode_if_needed(self, sandbox_db: KnowledgeDB, production_db: KnowledgeDB, episode_id: str) -> None:
        if not episode_id:
            return
        sandbox_episode = sandbox_db.get_episode(episode_id)
        if sandbox_episode is None:
            raise ValueError(f"Episode {episode_id} missing in sandbox")
        self._copy_document_if_needed(sandbox_db, production_db, sandbox_episode.doc_id)
        production_episode = production_db.get_episode(episode_id)
        if production_episode is None:
            production_db.put_episode(sandbox_episode, commit=False)
            return
        if production_episode.to_row() != sandbox_episode.to_row():
            raise ValueError(f"Episode {episode_id} has conflicting version in production")

    def _copy_entity_if_needed(self, sandbox_db: KnowledgeDB, production_db: KnowledgeDB, entity_id: str) -> None:
        if not entity_id:
            return
        sandbox_entity = self._get_entity(sandbox_db, entity_id)
        if sandbox_entity is None:
            raise ValueError(f"Entity {entity_id} missing in sandbox")
        production_entity = self._get_entity(production_db, entity_id)
        if production_entity is None:
            production_db.put_entity(sandbox_entity, commit=False)
            return
        if production_entity.to_row() != sandbox_entity.to_row():
            raise ValueError(f"Entity {entity_id} has conflicting version in production")

    def _copy_evidence_if_needed(self, sandbox_db: KnowledgeDB, production_db: KnowledgeDB, evidence: Evidence) -> None:
        self._copy_document_if_needed(sandbox_db, production_db, evidence.doc_id)
        existing = self._get_evidence(production_db, evidence.evidence_id)
        if existing is None:
            production_db.put_evidence(evidence, commit=False)
            return
        if existing.to_row() != evidence.to_row():
            raise ValueError(f"Evidence {evidence.evidence_id} has conflicting version in production")

    def _ensure_edge_endpoint(
        self,
        sandbox_db: KnowledgeDB,
        production_db: KnowledgeDB,
        *,
        kind: str,
        node_id: str,
        current_atom_id: str,
    ) -> bool:
        if not node_id or kind == "atom" and node_id == current_atom_id:
            return True
        if kind == "atom":
            return production_db.get_atom(node_id) is not None
        if kind == "entity":
            self._copy_entity_if_needed(sandbox_db, production_db, node_id)
            return True
        if kind == "document":
            self._copy_document_if_needed(sandbox_db, production_db, node_id)
            return True
        if kind == "episode":
            self._copy_episode_if_needed(sandbox_db, production_db, node_id)
            return True
        return False

    def _copy_provenance_if_needed(
        self,
        sandbox_rel: RelationManager,
        production_rel: RelationManager,
        atom_id: str,
    ) -> None:
        provenance = sandbox_rel.get_provenance(atom_id)
        if provenance is not None:
            production_rel.add_provenance(atom_id, provenance, commit=False)

    def _merge_atom_bundle(
        self,
        sandbox_db: KnowledgeDB,
        production_db: KnowledgeDB,
        sandbox_rel: RelationManager,
        production_rel: RelationManager,
        atom_id: str,
    ) -> None:
        atom = sandbox_db.get_atom(atom_id)
        if atom is None:
            raise ValueError(f"Atom {atom_id} not found in sandbox")

        existing = production_db.get_atom(atom_id)
        if existing is not None:
            if existing.hash != atom.hash:
                raise ValueError(f"Atom {atom_id} has conflicting version in production")
            return

        self._copy_episode_if_needed(sandbox_db, production_db, atom.episode_id)

        atom.promotion_status = PromotionStatus.STAGED.value
        atom.promotion_reason = "sandbox_merge"
        production_db.put_atom(atom, commit=False)

        for evidence in sandbox_db.list_evidence_for_atom(atom.atom_id):
            self._copy_evidence_if_needed(sandbox_db, production_db, evidence)

        edges = sandbox_db.get_edges_from(atom.atom_id) + sandbox_db.get_edges_to(atom.atom_id)
        for edge in edges:
            if not self._ensure_edge_endpoint(
                sandbox_db,
                production_db,
                kind=edge.from_kind,
                node_id=edge.from_id,
                current_atom_id=atom.atom_id,
            ):
                logger.warning(
                    "Skipping edge %s -> %s (%s) during sandbox merge because source endpoint is missing",
                    edge.from_id,
                    edge.to_id,
                    edge.edge_type,
                )
                continue
            if not self._ensure_edge_endpoint(
                sandbox_db,
                production_db,
                kind=edge.to_kind,
                node_id=edge.to_id,
                current_atom_id=atom.atom_id,
            ):
                logger.warning(
                    "Skipping edge %s -> %s (%s) during sandbox merge because target endpoint is missing",
                    edge.from_id,
                    edge.to_id,
                    edge.edge_type,
                )
                continue
            production_db.put_edge(edge, commit=False)

        self._copy_provenance_if_needed(sandbox_rel, production_rel, atom.atom_id)

    def merge_back(self, name: str, *, atom_ids: list[str] | None = None) -> MergeResult:
        """Merge specific atoms from sandbox back to production.

        Merged atoms get promotion_status = 'staged', requiring normal promotion flow.

        Args:
            name: Sandbox name
            atom_ids: Specific atom IDs to merge (None = all new atoms)

        Returns:
            MergeResult with merged atom IDs and any conflicts
        """
        if name not in self._sandboxes:
            return MergeResult(ok=False, merged_atom_ids=[], conflicts=[], message="Sandbox not found")

        info = self._sandboxes[name]
        sandbox_db = KnowledgeDB(db_path=info.db_path)
        sandbox_db.connect()
        sandbox_rel = RelationManager(db=sandbox_db)
        sandbox_rel.connect()

        production_db = None
        if os.path.exists(self.base_db_path):
            production_db = KnowledgeDB(db_path=self.base_db_path)
            production_db.connect()

        if production_db is None:
            return MergeResult(ok=False, merged_atom_ids=[], conflicts=[], message="Production DB not found")
        production_rel = RelationManager(db=production_db)
        production_rel.connect()

        try:
            if atom_ids is None:
                prod_conn = production_db.connect()
                prod_rows = prod_conn.execute("SELECT * FROM atoms").fetchall()
                prod_atoms = [Atom.from_row(dict(r)) for r in prod_rows]
                prod_atom_ids = {a.atom_id for a in prod_atoms}

                sandbox_conn = sandbox_db.connect()
                sandbox_rows = sandbox_conn.execute("SELECT * FROM atoms").fetchall()
                sandbox_atoms = [Atom.from_row(dict(r)) for r in sandbox_rows]

                atom_ids = [a.atom_id for a in sandbox_atoms if a.atom_id not in prod_atom_ids]

            merged_atom_ids = []
            conflicts = []
            prod_conn = production_db.connect()

            for atom_id in atom_ids:
                savepoint = f"merge_{atom_id.replace('-', '_')}"
                try:
                    prod_conn.execute(f"SAVEPOINT {savepoint}")
                    self._merge_atom_bundle(sandbox_db, production_db, sandbox_rel, production_rel, atom_id)
                    prod_conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                    if production_db.get_atom(atom_id) is not None:
                        merged_atom_ids.append(atom_id)
                except ValueError as e:
                    prod_conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    prod_conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                    conflicts.append(str(e))

            production_db.commit()

            message = f"Merged {len(merged_atom_ids)} atoms"
            if conflicts:
                message += f", {len(conflicts)} conflicts"

            logger.info("Merge back '%s': %s", name, message)
            return MergeResult(
                ok=len(conflicts) == 0,
                merged_atom_ids=merged_atom_ids,
                conflicts=conflicts,
                message=message,
            )
        finally:
            sandbox_db.close()
            production_db.close()

    def destroy(self, name: str) -> bool:
        """Delete a sandbox and its database file.

        Args:
            name: Sandbox name

        Returns:
            True if sandbox was destroyed, False if not found
        """
        if name not in self._sandboxes:
            return False

        info = self._sandboxes[name]
        if os.path.exists(info.db_path):
            os.unlink(info.db_path)

        sandbox_dir = os.path.dirname(info.db_path)
        if os.path.exists(sandbox_dir):
            try:
                os.rmdir(sandbox_dir)
            except OSError:
                pass

        del self._sandboxes[name]
        self._save_metadata()

        logger.info("Destroyed sandbox '%s'", name)
        return True

    def cleanup_expired(self) -> int:
        """Remove sandboxes that exceeded their TTL.

        Returns:
            Count of removed sandboxes
        """
        now = datetime.now(timezone.utc).timestamp()
        to_remove = []

        for name, info in self._sandboxes.items():
            try:
                expires = datetime.fromisoformat(info.expires_at).timestamp()
                if expires < now:
                    to_remove.append(name)
            except (ValueError, TypeError):
                pass

        for name in to_remove:
            self.destroy(name)

        if to_remove:
            logger.info("Cleaned up %d expired sandboxes", len(to_remove))

        return len(to_remove)
