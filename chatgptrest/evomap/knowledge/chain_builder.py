"""P1 Chain Builder — valid_from backfill + canonical_question evolution chains.

Implements:
1. valid_from backfill from episode/document timestamps
2. Canonical question normalization and chain construction
3. Supersession marking for older atoms in multi-atom chains

Safety: does not delete atoms, does not overwrite answer text,
does not mark anything 'active'. Migration is idempotent.

Reference: docs/2026-03-07_chatgptrest_evomap_p1_design.md
GitHub: ChatgptREST #93
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatgptrest.evomap.knowledge.db import KnowledgeDB

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical question normalization
# ---------------------------------------------------------------------------

def normalize_question(q: str) -> str:
    """Normalize a canonical question for chain grouping.

    Steps:
    - strip whitespace
    - lowercase
    - collapse internal whitespace
    - strip trailing punctuation noise (?, !, .)
    """
    if not q:
        return ""
    q = q.strip().lower()
    q = re.sub(r"\s+", " ", q)
    q = re.sub(r"[?!.]+$", "", q)
    return q.strip()


def _chain_id_from_question(normalized_q: str) -> str:
    """Generate a stable chain_id from a normalized canonical question."""
    return "ch_" + hashlib.sha256(normalized_q.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# valid_from backfill
# ---------------------------------------------------------------------------

@dataclass
class BackfillStats:
    total: int = 0
    already_set: int = 0
    from_episode_end: int = 0
    from_episode_start: int = 0
    from_doc_updated: int = 0
    from_doc_created: int = 0
    still_missing: int = 0


def backfill_valid_from(db: KnowledgeDB) -> BackfillStats:
    """Populate valid_from for atoms that have valid_from == 0.

    Precedence:
    1. atom.valid_from (keep if already > 0)
    2. episode.time_end
    3. episode.time_start
    4. document.updated_at
    5. document.created_at
    """
    conn = db.connect()
    stats = BackfillStats()

    rows = conn.execute("SELECT atom_id, episode_id, valid_from FROM atoms").fetchall()
    stats.total = len(rows)

    # Pre-fetch episode and document timestamps
    episode_cache: dict[str, dict] = {}
    for r in conn.execute("SELECT episode_id, doc_id, time_start, time_end FROM episodes").fetchall():
        episode_cache[r[0]] = {"doc_id": r[1], "time_start": r[2], "time_end": r[3]}

    doc_cache: dict[str, dict] = {}
    for r in conn.execute("SELECT doc_id, created_at, updated_at FROM documents").fetchall():
        doc_cache[r[0]] = {"created_at": r[1], "updated_at": r[2]}

    updates = []
    for row in rows:
        atom_id, episode_id, valid_from = row[0], row[1], row[2]

        if valid_from and valid_from > 0:
            stats.already_set += 1
            continue

        ts = 0.0
        source = ""

        ep = episode_cache.get(episode_id)
        if ep:
            if ep["time_end"] and ep["time_end"] > 0:
                ts = ep["time_end"]
                source = "episode_end"
            elif ep["time_start"] and ep["time_start"] > 0:
                ts = ep["time_start"]
                source = "episode_start"
            else:
                doc = doc_cache.get(ep["doc_id"])
                if doc:
                    if doc["updated_at"] and doc["updated_at"] > 0:
                        ts = doc["updated_at"]
                        source = "doc_updated"
                    elif doc["created_at"] and doc["created_at"] > 0:
                        ts = doc["created_at"]
                        source = "doc_created"

        if ts > 0:
            updates.append((ts, atom_id))
            if source == "episode_end":
                stats.from_episode_end += 1
            elif source == "episode_start":
                stats.from_episode_start += 1
            elif source == "doc_updated":
                stats.from_doc_updated += 1
            elif source == "doc_created":
                stats.from_doc_created += 1
        else:
            stats.still_missing += 1
            # Mark atoms with missing timestamps
            conn.execute(
                "UPDATE atoms SET promotion_reason = 'missing_valid_from' WHERE atom_id = ?",
                (atom_id,),
            )

    if updates:
        conn.executemany(
            "UPDATE atoms SET valid_from = ? WHERE atom_id = ?", updates
        )
        conn.commit()

    logger.info(
        "valid_from backfill: total=%d, already=%d, ep_end=%d, ep_start=%d, "
        "doc_upd=%d, doc_cre=%d, missing=%d",
        stats.total, stats.already_set, stats.from_episode_end,
        stats.from_episode_start, stats.from_doc_updated,
        stats.from_doc_created, stats.still_missing,
    )
    return stats


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------

@dataclass
class ChainStats:
    total_atoms: int = 0
    atoms_with_canonical: int = 0
    atoms_without_canonical: int = 0
    total_chains: int = 0
    singleton_chains: int = 0
    multi_atom_chains: int = 0
    superseded_count: int = 0
    candidate_count: int = 0
    staged_count: int = 0


def build_chains(db: KnowledgeDB) -> ChainStats:
    """Build canonical_question evolution chains and assign supersession.

    Rules:
    - Group atoms by normalized canonical_question
    - Sort within group by valid_from ASC, tie-break by atom_id
    - Assign chain_id, chain_rank (1..N), is_chain_head
    - In multi-atom chains: newest = candidate, older = superseded
    - Singletons: candidate, is_chain_head=1
    - Empty canonical_question: stay staged
    - Atoms with valid_from=0 are not promoted above atoms with valid timestamps
    """
    conn = db.connect()
    stats = ChainStats()

    rows = conn.execute(
        "SELECT atom_id, canonical_question, valid_from FROM atoms"
    ).fetchall()
    stats.total_atoms = len(rows)

    # Group by normalized canonical_question
    groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        atom_id, cq, vf = row[0], row[1], row[2]
        norm = normalize_question(cq)
        if not norm:
            stats.atoms_without_canonical += 1
            continue
        stats.atoms_with_canonical += 1
        groups[norm].append((atom_id, vf or 0.0))

    # Build chains
    batch_updates = []
    for norm_q, atoms in groups.items():
        chain_id = _chain_id_from_question(norm_q)
        # Sort by valid_from ASC, then atom_id for stable ordering
        atoms.sort(key=lambda x: (x[1], x[0]))
        n = len(atoms)
        stats.total_chains += 1

        if n == 1:
            # Singleton chain
            stats.singleton_chains += 1
            atom_id = atoms[0][0]
            batch_updates.append((
                chain_id,        # chain_id
                1,               # chain_rank
                1,               # is_chain_head
                "candidate",     # promotion_status
                "",              # superseded_by
                "",              # promotion_reason
                atom_id,         # WHERE atom_id =
            ))
            stats.candidate_count += 1
        else:
            # Multi-atom chain
            stats.multi_atom_chains += 1
            head_id = atoms[-1][0]  # newest

            for rank, (atom_id, vf) in enumerate(atoms, 1):
                is_head = 1 if rank == n else 0

                if is_head:
                    promo = "candidate"
                    superseded_by = ""
                    reason = ""
                    stats.candidate_count += 1
                else:
                    promo = "superseded"
                    superseded_by = head_id
                    reason = "newer_in_chain"
                    stats.superseded_count += 1

                batch_updates.append((
                    chain_id, rank, is_head, promo,
                    superseded_by, reason, atom_id,
                ))

    # Mark atoms without canonical_question as staged
    if stats.atoms_without_canonical > 0:
        conn.execute(
            "UPDATE atoms SET promotion_status = 'staged', promotion_reason = 'no_canonical_question' "
            "WHERE canonical_question = '' OR canonical_question IS NULL"
        )
        stats.staged_count = stats.atoms_without_canonical

    # Apply chain updates in batch
    if batch_updates:
        conn.executemany(
            "UPDATE atoms SET chain_id = ?, chain_rank = ?, is_chain_head = ?, "
            "promotion_status = ?, superseded_by = ?, promotion_reason = ? "
            "WHERE atom_id = ?",
            batch_updates,
        )

    conn.commit()

    logger.info(
        "Chain build: atoms=%d (with_cq=%d, without=%d), "
        "chains=%d (singleton=%d, multi=%d), "
        "candidate=%d, superseded=%d, staged=%d",
        stats.total_atoms, stats.atoms_with_canonical, stats.atoms_without_canonical,
        stats.total_chains, stats.singleton_chains, stats.multi_atom_chains,
        stats.candidate_count, stats.superseded_count, stats.staged_count,
    )
    return stats


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@dataclass
class P1Report:
    """Summary report for one P1 migration run."""
    backfill: BackfillStats | None = None
    chains: ChainStats | None = None
    elapsed_ms: float = 0.0
    run_at: float = 0.0


def run_p1_migration(db: KnowledgeDB) -> P1Report:
    """Execute full P1 pipeline: backfill → chains → report."""
    report = P1Report(run_at=time.time())
    t0 = time.time()

    logger.info("P1 migration: starting")

    # Step 1: backfill valid_from
    report.backfill = backfill_valid_from(db)

    # Step 2: build chains & assign supersession
    report.chains = build_chains(db)

    report.elapsed_ms = (time.time() - t0) * 1000
    logger.info("P1 migration: complete in %.1fms", report.elapsed_ms)

    return report
