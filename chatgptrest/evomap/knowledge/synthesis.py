"""EvoMap Macro-Atom Synthesis — aggregate related atoms into summary atoms.

Solves: micro-level atoms are accurate but can't answer macro-level questions
like "What's the consensus on database selection over the past 3 months?"

Approach (inspired by LightRAG Community Summaries):
  1. Find clusters of related atoms via edges (SAME_TOPIC, DERIVED_FROM)
  2. Aggregate cluster content into a synthesis prompt
  3. Generate a summary atom (type=SUMMARY) via LLM or heuristic
  4. Link SUMMARY atom to its source atoms via DERIVED_FROM edges

This module handles clustering and preparation.
The actual LLM call is optional — a heuristic fallback is provided.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    AtomType,
    Edge,
    EdgeType,
    Stability,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SynthesisConfig:
    """Tunable parameters for Macro-Atom synthesis."""

    # Minimum cluster size to trigger synthesis
    min_cluster_size: int = 3

    # Maximum atoms per cluster (to keep LLM context manageable)
    max_cluster_size: int = 20

    # Minimum average quality of cluster atoms
    min_avg_quality: float = 0.3

    # Maximum age (days) of atoms to consider fresh enough
    max_age_days: int = 90

    # Edge types that define "related" for clustering
    cluster_edge_types: list[str] = field(default_factory=lambda: [
        EdgeType.SAME_TOPIC.value,
        EdgeType.DERIVED_FROM.value,
        EdgeType.CLARIFIES.value,
    ])

    # Maximum summary length (chars)
    max_summary_length: int = 2000

    # Minimum answer length: atoms with shorter answers are noise
    min_answer_length: int = 50


# ---------------------------------------------------------------------------
# Cluster Detection
# ---------------------------------------------------------------------------

@dataclass
class AtomCluster:
    """A group of related atoms ready for synthesis."""
    cluster_id: str = ""
    canonical_topic: str = ""
    atoms: list[Atom] = field(default_factory=list)
    avg_quality: float = 0.0
    time_span_days: float = 0.0
    edge_count: int = 0

    @property
    def size(self) -> int:
        return len(self.atoms)

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "canonical_topic": self.canonical_topic,
            "size": self.size,
            "avg_quality": round(self.avg_quality, 3),
            "time_span_days": round(self.time_span_days, 1),
            "edge_count": self.edge_count,
            "atom_ids": [a.atom_id for a in self.atoms],
        }


def find_clusters(
    db: KnowledgeDB,
    config: SynthesisConfig | None = None,
) -> list[AtomCluster]:
    """Find clusters of related atoms suitable for synthesis.

    Strategy:
      1. Group atoms by canonical_question
      2. Expand groups via graph edges (BFS 1-hop)
      3. Filter by min_cluster_size and min_avg_quality

    Returns list of AtomCluster, sorted by size descending.
    """
    config = config or SynthesisConfig()
    conn = db.connect()

    cutoff = time.time() - config.max_age_days * 86400

    # Step 1: Group by canonical_question
    rows = conn.execute(
        """SELECT * FROM atoms
           WHERE status != 'gate_x'
             AND quality_auto > 0
             AND valid_from > ?
           ORDER BY canonical_question, valid_from DESC""",
        (cutoff,),
    ).fetchall()
    atoms = [Atom.from_row(dict(r)) for r in rows]

    # Filter noise: exclude prompt templates and short answers
    atoms = [a for a in atoms if not _is_prompt_template(a, config)]

    # Build lookup
    atom_by_id = {a.atom_id: a for a in atoms}

    # Group by canonical
    canon_groups: dict[str, list[Atom]] = defaultdict(list)
    for atom in atoms:
        cq = atom.canonical_question.strip()
        if cq:
            canon_groups[cq].append(atom)

    # Step 2: Expand via edges (1-hop)
    edge_types = set(config.cluster_edge_types)
    edge_rows = conn.execute(
        """SELECT * FROM edges
           WHERE edge_type IN ({})
             AND from_kind = 'atom' AND to_kind = 'atom'""".format(
            ",".join("?" * len(edge_types))
        ),
        list(edge_types),
    ).fetchall()
    edges = [Edge.from_row(dict(r)) for r in edge_rows]

    # Build adjacency
    adjacency: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adjacency[e.from_id].add(e.to_id)
        adjacency[e.to_id].add(e.from_id)

    # Merge canonical groups that share edges
    # Use union-find approach
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Initialize: atoms in same canonical group share parent
    for cq, group in canon_groups.items():
        for atom in group[1:]:
            union(group[0].atom_id, atom.atom_id)

    # Merge across edges
    for e in edges:
        if e.from_id in atom_by_id and e.to_id in atom_by_id:
            union(e.from_id, e.to_id)

    # Collect clusters
    cluster_atoms: dict[str, list[Atom]] = defaultdict(list)
    for atom in atoms:
        root = find(atom.atom_id)
        cluster_atoms[root].append(atom)

    # Step 3: Build AtomCluster objects with filtering
    clusters = []
    for root_id, group in cluster_atoms.items():
        if len(group) < config.min_cluster_size:
            continue
        if len(group) > config.max_cluster_size:
            # Keep top-quality atoms
            group.sort(key=lambda a: a.quality_auto, reverse=True)
            group = group[:config.max_cluster_size]

        avg_q = sum(a.quality_auto for a in group) / len(group)
        if avg_q < config.min_avg_quality:
            continue

        # Determine canonical topic (most common canonical_question)
        canon_counts: dict[str, int] = defaultdict(int)
        for a in group:
            cq = a.canonical_question.strip()
            if cq:
                canon_counts[cq] += 1
        canonical_topic = max(canon_counts, key=canon_counts.get) if canon_counts else ""

        # Time span
        timestamps = [a.valid_from for a in group if a.valid_from > 0]
        span = (max(timestamps) - min(timestamps)) / 86400 if len(timestamps) >= 2 else 0

        # Count edges within cluster
        atom_ids = {a.atom_id for a in group}
        ec = sum(1 for e in edges if e.from_id in atom_ids and e.to_id in atom_ids)

        cluster = AtomCluster(
            cluster_id=hashlib.md5(root_id.encode()).hexdigest()[:12],
            canonical_topic=canonical_topic,
            atoms=group,
            avg_quality=avg_q,
            time_span_days=span,
            edge_count=ec,
        )
        clusters.append(cluster)

    clusters.sort(key=lambda c: c.size, reverse=True)
    logger.info("Found %d synthesis-ready clusters from %d atoms", len(clusters), len(atoms))
    return clusters


def _is_prompt_template(atom: Atom, config: SynthesisConfig) -> bool:
    """Return True if atom looks like a system prompt or template (noise)."""
    ans = atom.answer.strip()
    if len(ans) < config.min_answer_length:
        return True
    # Common prompt-template patterns (system instructions, not knowledge)
    q = atom.question.strip()
    cq = atom.canonical_question.strip()
    for text in (q, cq):
        if text.startswith("你是") and len(text) > 30:
            return True
        if text.startswith("## 任务") or text.startswith("## Task"):
            return True
        if text.startswith("请") and "严格" in text[:30]:
            return True
    return False


# ---------------------------------------------------------------------------
# Heuristic Synthesis (no LLM required)
# ---------------------------------------------------------------------------

def synthesize_heuristic(cluster: AtomCluster) -> Atom:
    """Create a summary atom from a cluster using heuristic extraction.

    No LLM call needed — extracts key points from QA pairs.
    Good enough for v1; can be upgraded to LLM later.
    """
    # Collect all unique questions and answers
    qa_pairs = []
    seen_q = set()
    for atom in sorted(cluster.atoms, key=lambda a: a.quality_auto, reverse=True):
        q = atom.question.strip()
        if q and q not in seen_q:
            seen_q.add(q)
            # Take first ~200 chars of answer
            ans_preview = atom.answer.strip()[:200]
            if len(atom.answer.strip()) > 200:
                ans_preview += "..."
            qa_pairs.append((q, ans_preview))

    # Build summary question
    summary_question = f"Summary: {cluster.canonical_topic}"
    if not cluster.canonical_topic:
        summary_question = f"Summary of {cluster.size} related knowledge atoms"

    # Build summary answer
    lines = [f"**Topic Cluster:** {cluster.canonical_topic}"]
    lines.append(f"**Sources:** {cluster.size} atoms over {cluster.time_span_days:.0f} days")
    lines.append(f"**Average Quality:** {cluster.avg_quality:.2f}")
    lines.append("")
    lines.append("### Key Points")
    for i, (q, a) in enumerate(qa_pairs[:10], 1):
        lines.append(f"{i}. **{q}**")
        lines.append(f"   {a}")
        lines.append("")

    summary_answer = "\n".join(lines)

    # Create summary atom
    summary = Atom(
        atom_id=f"macro_{cluster.cluster_id}",
        episode_id="",  # Macro atoms are cross-episode
        atom_type=AtomType.SUMMARY.value if hasattr(AtomType, "SUMMARY") else "summary",
        question=summary_question,
        answer=summary_answer,
        canonical_question=cluster.canonical_topic,
        stability=Stability.VERSIONED.value,
        status=AtomStatus.CANDIDATE.value,
        valid_from=time.time(),
        quality_auto=min(cluster.avg_quality + 0.1, 1.0),  # Slight boost for synthesis
        value_auto=min(cluster.avg_quality + 0.15, 1.0),
        source_quality=cluster.avg_quality,
        scores_json=json.dumps({
            "extractor": "macro_synthesis",
            "cluster_size": cluster.size,
            "avg_source_quality": round(cluster.avg_quality, 3),
            "time_span_days": round(cluster.time_span_days, 1),
        }),
    )

    return summary


# ---------------------------------------------------------------------------
# Full Synthesis Pipeline
# ---------------------------------------------------------------------------

@dataclass
class SynthesisResult:
    """Result of a synthesis run."""
    clusters_found: int = 0
    atoms_synthesized: int = 0
    atoms_skipped: int = 0
    edges_created: int = 0
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class MacroAtomSynthesizer:
    """Full synthesis pipeline: cluster → synthesize → store → link.

    Usage::

        synth = MacroAtomSynthesizer(db)
        result = synth.run()
        print(result.to_dict())
    """

    def __init__(
        self,
        db: KnowledgeDB,
        config: SynthesisConfig | None = None,
        llm_fn: Callable[[str], str] | None = None,
    ):
        self.db = db
        self.config = config or SynthesisConfig()
        self.llm_fn = llm_fn  # Optional: fn(prompt) -> answer

    def run(self) -> SynthesisResult:
        """Execute full synthesis pipeline.

        1. Find clusters
        2. For each cluster, check if summary already exists
        3. Synthesize (LLM if available, else heuristic)
        4. Store summary atom
        5. Create DERIVED_FROM edges from summary to source atoms
        """
        t0 = time.time()
        result = SynthesisResult()

        clusters = find_clusters(self.db, self.config)
        result.clusters_found = len(clusters)

        for cluster in clusters:
            macro_id = f"macro_{cluster.cluster_id}"

            # Skip if already synthesized
            existing = self.db.get_atom(macro_id)
            if existing:
                result.atoms_skipped += 1
                continue

            # Synthesize
            if self.llm_fn:
                summary_atom = self._synthesize_llm(cluster)
            else:
                summary_atom = synthesize_heuristic(cluster)

            # Store
            self.db.put_atom(summary_atom)

            # Create DERIVED_FROM edges
            for source_atom in cluster.atoms:
                edge = Edge(
                    from_id=summary_atom.atom_id,
                    to_id=source_atom.atom_id,
                    edge_type=EdgeType.DERIVED_FROM.value,
                    weight=source_atom.quality_auto,
                    from_kind="atom",
                    to_kind="atom",
                    meta_json=json.dumps({"reason": "macro_synthesis"}),
                )
                try:
                    self.db.put_edge(edge)
                    result.edges_created += 1
                except Exception:
                    pass  # Edge already exists

            result.atoms_synthesized += 1

        self.db.commit()
        result.elapsed_ms = int((time.time() - t0) * 1000)

        logger.info(
            "Synthesis complete: %d clusters, %d synthesized, %d skipped",
            result.clusters_found, result.atoms_synthesized, result.atoms_skipped,
        )
        return result

    def _synthesize_llm(self, cluster: AtomCluster) -> Atom:
        """Synthesize using LLM (if llm_fn provided)."""
        # Build prompt
        qa_text = ""
        for i, atom in enumerate(cluster.atoms[:15], 1):
            qa_text += f"\n{i}. Q: {atom.question}\n   A: {atom.answer[:300]}\n"

        prompt = (
            f"Below are {cluster.size} related knowledge items about "
            f"'{cluster.canonical_topic}'.\n\n"
            f"Please write a concise synthesis (200-400 words) that:\n"
            f"1. Summarizes the key consensus\n"
            f"2. Notes any contradictions or evolution of understanding\n"
            f"3. Highlights actionable takeaways\n\n"
            f"Knowledge items:{qa_text}"
        )

        try:
            answer = self.llm_fn(prompt)
        except Exception as e:
            logger.warning("LLM synthesis failed, using heuristic: %s", e)
            return synthesize_heuristic(cluster)

        summary = Atom(
            atom_id=f"macro_{cluster.cluster_id}",
            episode_id="",
            atom_type=AtomType.SUMMARY.value if hasattr(AtomType, "SUMMARY") else "summary",
            question=f"Summary: {cluster.canonical_topic}",
            answer=answer[:self.config.max_summary_length],
            canonical_question=cluster.canonical_topic,
            stability=Stability.VERSIONED.value,
            status=AtomStatus.CANDIDATE.value,
            valid_from=time.time(),
            quality_auto=min(cluster.avg_quality + 0.15, 1.0),
            value_auto=min(cluster.avg_quality + 0.2, 1.0),
            source_quality=cluster.avg_quality,
            scores_json=json.dumps({
                "extractor": "macro_synthesis_llm",
                "cluster_size": cluster.size,
                "time_span_days": round(cluster.time_span_days, 1),
            }),
        )
        return summary
