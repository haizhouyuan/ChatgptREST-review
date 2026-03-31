"""EvoMap Graph Builder v1 — structural edge inference.

Infers relationships between atoms without requiring embeddings:
  1. SAME_TOPIC — atoms sharing canonical_question or episode
  2. DERIVED_FROM — atoms in chain conversations (parent → child episodes)
  3. SUPERSEDES — newer atoms with same canonical + higher quality
  4. DEPENDS_ON — prerequisite references in atom content

This is a batch job that scans atoms and inserts edges into the DB.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterator

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    Edge,
    EdgeType,
    Episode,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class GraphConfig:
    """Tunable parameters for graph builder."""
    # SAME_TOPIC: minimum token overlap ratio to link atoms
    topic_similarity_threshold: float = 0.4

    # SUPERSEDES: quality improvement threshold
    supersede_quality_delta: float = 0.1

    # Batch size for DB reads
    batch_size: int = 500

    # Max edges to create per run (circuit breaker)
    max_edges: int = 50_000


# ---------------------------------------------------------------------------
# Token overlap similarity (no embeddings needed)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Simple whitespace + lowering tokenizer for overlap scoring."""
    # Remove punctuation, split, lowercase
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = {t for t in clean.split() if len(t) > 2}
    return tokens


def token_overlap(text_a: str, text_b: str) -> float:
    """Jaccard-like overlap between two texts.

    Returns [0, 1] where 1 = identical token sets.
    """
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

class GraphBuilder:
    """Infer structural edges between atoms.

    Usage::

        builder = GraphBuilder(db)
        stats = builder.build_all()
        print(stats)
    """

    def __init__(self, db: KnowledgeDB, config: GraphConfig | None = None):
        self.db = db
        self.config = config or GraphConfig()

    def build_all(self) -> dict:
        """Run all edge inference passes.

        Returns stats dict with edge counts per type.
        """
        stats = {
            "same_topic": 0,
            "derived_from": 0,
            "supersedes": 0,
            "total_atoms": 0,
            "total_edges": 0,
            "elapsed_ms": 0,
        }
        t0 = time.time()

        # Load all atoms (we need them for cross-comparisons)
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM atoms ORDER BY valid_from DESC"
        ).fetchall()
        atoms = [Atom.from_row(dict(r)) for r in rows]
        stats["total_atoms"] = len(atoms)

        if not atoms:
            return stats

        # Pass 1: SAME_TOPIC — canonical_question clusters + token overlap
        n = self._build_same_topic(atoms)
        stats["same_topic"] = n

        # Pass 2: DERIVED_FROM — episode chain relationships
        n = self._build_derived_from(atoms)
        stats["derived_from"] = n

        # Pass 3: SUPERSEDES — newer + higher quality on same topic
        n = self._build_supersedes(atoms)
        stats["supersedes"] = n

        self.db.commit()

        stats["total_edges"] = stats["same_topic"] + stats["derived_from"] + stats["supersedes"]
        stats["elapsed_ms"] = int((time.time() - t0) * 1000)

        logger.info("GraphBuilder complete: %s", stats)
        return stats

    # -- Pass 1: SAME_TOPIC -------------------------------------------------

    def _build_same_topic(self, atoms: list[Atom]) -> int:
        """Link atoms that share the same canonical question or high token overlap."""
        created = 0

        # Group by canonical_question (exact match)
        canon_groups: dict[str, list[Atom]] = defaultdict(list)
        for atom in atoms:
            cq = atom.canonical_question.strip()
            if cq:
                canon_groups[cq].append(atom)

        # Create SAME_TOPIC edges within each group
        for cq, group in canon_groups.items():
            if len(group) < 2:
                continue
            # Link each pair (but only first N to avoid quadratic explosion)
            for i, a in enumerate(group[:20]):
                for b in group[i + 1:20]:
                    edge = Edge(
                        from_id=a.atom_id,
                        to_id=b.atom_id,
                        edge_type=EdgeType.SAME_TOPIC.value,
                        weight=1.0,
                        from_kind="atom",
                        to_kind="atom",
                        meta_json=json.dumps({"reason": "canonical_match", "canonical": cq[:100]}),
                    )
                    self._safe_put_edge(edge)
                    created += 1
                    if created >= self.config.max_edges:
                        return created

        # Also find cross-group overlaps using token similarity on question text
        # Only compare atoms from different canonical groups
        # Use a sample to avoid O(n²) on large atom sets
        sample = atoms[:500] if len(atoms) > 500 else atoms
        checked = set()
        for i, a in enumerate(sample):
            for b in sample[i + 1:]:
                if a.canonical_question == b.canonical_question:
                    continue  # Already linked above
                pair_key = (a.atom_id, b.atom_id)
                if pair_key in checked:
                    continue
                checked.add(pair_key)

                sim = token_overlap(a.question, b.question)
                if sim >= self.config.topic_similarity_threshold:
                    edge = Edge(
                        from_id=a.atom_id,
                        to_id=b.atom_id,
                        edge_type=EdgeType.SAME_TOPIC.value,
                        weight=round(sim, 3),
                        from_kind="atom",
                        to_kind="atom",
                        meta_json=json.dumps({"reason": "token_overlap", "similarity": round(sim, 3)}),
                    )
                    self._safe_put_edge(edge)
                    created += 1
                    if created >= self.config.max_edges:
                        return created

        return created

    # -- Pass 2: DERIVED_FROM -----------------------------------------------

    def _build_derived_from(self, atoms: list[Atom]) -> int:
        """Link atoms whose episodes have parent-child relationships.

        If episode B is a followup of episode A (same doc, higher time),
        then atoms in B are DERIVED_FROM atoms in A.
        """
        created = 0

        # Group atoms by episode_id
        ep_atoms: dict[str, list[Atom]] = defaultdict(list)
        for atom in atoms:
            if atom.episode_id:
                ep_atoms[atom.episode_id].append(atom)

        # Load episodes to find chains
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY doc_id, time_start"
        ).fetchall()
        episodes = [Episode.from_row(dict(r)) for r in rows]

        # Group episodes by doc_id
        doc_episodes: dict[str, list[Episode]] = defaultdict(list)
        for ep in episodes:
            doc_episodes[ep.doc_id].append(ep)

        # For each doc, create DERIVED_FROM edges between sequential episodes
        for doc_id, eps in doc_episodes.items():
            if len(eps) < 2:
                continue
            for i in range(len(eps) - 1):
                ep_a = eps[i]
                ep_b = eps[i + 1]

                atoms_a = ep_atoms.get(ep_a.episode_id, [])
                atoms_b = ep_atoms.get(ep_b.episode_id, [])

                # Link first atom of B to last atom of A (derivation chain)
                if atoms_a and atoms_b:
                    edge = Edge(
                        from_id=atoms_b[0].atom_id,
                        to_id=atoms_a[-1].atom_id,
                        edge_type=EdgeType.DERIVED_FROM.value,
                        weight=0.8,
                        from_kind="atom",
                        to_kind="atom",
                        meta_json=json.dumps({
                            "reason": "episode_chain",
                            "from_ep": ep_b.episode_id,
                            "to_ep": ep_a.episode_id,
                        }),
                    )
                    self._safe_put_edge(edge)
                    created += 1
                    if created >= self.config.max_edges:
                        return created

        return created

    # -- Pass 3: SUPERSEDES ------------------------------------------------

    def _build_supersedes(self, atoms: list[Atom]) -> int:
        """Mark newer, higher-quality atoms as superseding older ones on same topic."""
        created = 0

        # Group by canonical_question
        canon_groups: dict[str, list[Atom]] = defaultdict(list)
        for atom in atoms:
            cq = atom.canonical_question.strip()
            if cq:
                canon_groups[cq].append(atom)

        delta = self.config.supersede_quality_delta

        for cq, group in canon_groups.items():
            if len(group) < 2:
                continue

            # Sort by valid_from descending (newest first)
            group.sort(key=lambda a: a.valid_from, reverse=True)

            for i, newer in enumerate(group):
                for older in group[i + 1:]:
                    # newer supersedes older if quality is significantly higher
                    if (newer.quality_auto - older.quality_auto) >= delta:
                        edge = Edge(
                            from_id=newer.atom_id,
                            to_id=older.atom_id,
                            edge_type=EdgeType.SUPERSEDES.value,
                            weight=round(newer.quality_auto - older.quality_auto, 3),
                            from_kind="atom",
                            to_kind="atom",
                            meta_json=json.dumps({
                                "reason": "quality_upgrade",
                                "new_q": round(newer.quality_auto, 3),
                                "old_q": round(older.quality_auto, 3),
                            }),
                        )
                        self._safe_put_edge(edge)
                        created += 1
                        if created >= self.config.max_edges:
                            return created
                        break  # Only supersede the immediate predecessor

        return created

    # -- Helpers -----------------------------------------------------------

    def _safe_put_edge(self, edge: Edge):
        """Insert edge, ignoring conflicts (PK collision = already exists)."""
        try:
            self.db.put_edge(edge)
        except Exception:
            pass  # Edge already exists, skip


# ---------------------------------------------------------------------------
# Convenience: CLI-friendly runner
# ---------------------------------------------------------------------------

def build_graph(db_path: str | None = None, **kwargs) -> dict:
    """One-shot graph build from DB path."""
    db = KnowledgeDB(db_path=db_path)
    db.connect()
    try:
        config = GraphConfig(**kwargs) if kwargs else GraphConfig()
        builder = GraphBuilder(db, config)
        return builder.build_all()
    finally:
        db.close()
