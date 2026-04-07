"""EvoMap Knowledge Retrieval Pipeline v2.

Pipeline order (from Gemini DeepThink review):
  Pre-filter → FTS5 retrieval → Quality gate → Time decay → Final scoring

Multiplicative scoring model (from Pro review):
  final = relevance × quality × time_decay

This module is designed to be called by ContextAssembler in Phase 6.3.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Stability, PromotionStatus

logger = logging.getLogger(__name__)

# Sentinel: tracks whether auto-rescore has run in this process
_RESCORE_DONE = False


def _ensure_rescored(db: KnowledgeDB) -> None:
    """Lazy one-time rescore if >50% atoms have zero quality.

    Runs once per process. Prevents repeat work on subsequent calls.
    """
    global _RESCORE_DONE
    if _RESCORE_DONE:
        return

    _RESCORE_DONE = True  # Mark early to prevent re-entry

    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN quality_auto=0 THEN 1 ELSE 0 END) FROM atoms"
        ).fetchone()
        total, zero_q = row[0] or 0, row[1] or 0
        if total > 0 and (zero_q / total) > 0.5:
            logger.info("Auto-rescore: %d/%d atoms (%.0f%%) have zero quality, running batch rescore",
                        zero_q, total, zero_q / total * 100)
            rescore_all_atoms(db, batch_size=500)
    except Exception as e:
        logger.warning("Auto-rescore failed: %s", e)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class RetrievalSurface(str, Enum):
    """Runtime-facing retrieval policy surfaces.

    The broad library default still allows ACTIVE+STAGED for backward
    compatibility. Runtime entry points should choose an explicit surface
    instead of relying on that broad default.
    """

    USER_HOT_PATH = "user_hot_path"
    DIAGNOSTIC_PATH = "diagnostic_path"
    SHADOW_EXPERIMENT_PATH = "shadow_experiment_path"
    PROMOTION_REVIEW_PATH = "promotion_review_path"

@dataclass
class RetrievalConfig:
    """Tunable parameters for the retrieval pipeline."""
    # FTS candidate pool size (widen to avoid missing good results)
    fts_limit: int = 60

    # Quality gate (reject below this)
    min_quality: float = 0.15

    # Time decay: half_life in days
    decay_half_life_days: float = 90.0

    # Output limit
    result_limit: int = 10

    # Source diversity: max atoms from same episode
    max_per_episode: int = 3

    # Stability filter: exclude superseded/ephemeral by default
    exclude_stability: tuple[str, ...] = (Stability.SUPERSEDED.value,)

    # Status filter: only scored or higher
    min_status: tuple[str, ...] = (
        AtomStatus.CANDIDATE.value,
        AtomStatus.SCORED.value,
        AtomStatus.GATE_A.value,
        AtomStatus.GATE_B.value,
        AtomStatus.GATE_C.value,
        AtomStatus.REFINED.value,
        AtomStatus.PUBLISHED.value,
    )

    # Promotion status filter: active and staged remain queryable by default.
    # Hot paths that need stricter launch/runtime gating should pass an explicit
    # config rather than relying on the broad library default.
    allowed_promotion_status: tuple[str, ...] = (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
    )

    # Optional hard scope filter. Empty string preserves existing behavior.
    project_id: str = ""


_SURFACE_ALLOWED_PROMOTION_STATUS: dict[RetrievalSurface, tuple[str, ...]] = {
    RetrievalSurface.USER_HOT_PATH: (PromotionStatus.ACTIVE.value,),
    RetrievalSurface.DIAGNOSTIC_PATH: (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
    ),
    RetrievalSurface.SHADOW_EXPERIMENT_PATH: (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
    ),
    RetrievalSurface.PROMOTION_REVIEW_PATH: (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
        PromotionStatus.CANDIDATE.value,
    ),
}


def runtime_retrieval_config(
    *,
    surface: str | RetrievalSurface,
    **overrides: Any,
) -> RetrievalConfig:
    """Build an explicit runtime retrieval config for a known surface."""

    if isinstance(surface, RetrievalSurface):
        surface_value = surface.value
    else:
        surface_value = str(surface or RetrievalSurface.USER_HOT_PATH.value).strip().lower()
    try:
        resolved_surface = RetrievalSurface(surface_value)
    except ValueError as exc:
        raise ValueError(f"unknown retrieval surface: {surface_value}") from exc

    cfg = replace(
        RetrievalConfig(),
        allowed_promotion_status=_SURFACE_ALLOWED_PROMOTION_STATUS[resolved_surface],
    )
    if overrides:
        unknown = [key for key in overrides if not hasattr(cfg, key)]
        if unknown:
            raise TypeError(f"unknown RetrievalConfig override(s): {', '.join(sorted(unknown))}")
        cfg = replace(cfg, **overrides)
    return cfg


def summarize_promotion_statuses(scored_atoms: list["ScoredAtom"]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in scored_atoms:
        status = str(getattr(item.atom, "promotion_status", "") or "").strip().lower() or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Scored result container
# ---------------------------------------------------------------------------

@dataclass
class ScoredAtom:
    """An atom with retrieval scores attached."""
    atom: Atom
    fts_rank: float = 0.0       # Raw FTS5 rank (lower = better)
    relevance: float = 0.0      # Normalized relevance [0, 1]
    quality: float = 0.0        # From atom.quality_auto
    time_decay: float = 1.0     # Freshness factor [0, 1]
    final_score: float = 0.0    # Multiplicative composite

    def to_context_dict(self) -> dict:
        """Format for ContextAssembler consumption."""
        return {
            "atom_id": self.atom.atom_id,
            "question": self.atom.question,
            "answer": self.atom.answer,
            "atom_type": self.atom.atom_type,
            "quality": round(self.quality, 3),
            "relevance": round(self.relevance, 3),
            "final_score": round(self.final_score, 3),
            "source_quality": self.atom.source_quality,
        }


# ---------------------------------------------------------------------------
# Time decay
# ---------------------------------------------------------------------------

def compute_time_decay(valid_from: float, half_life_days: float = 90.0) -> float:
    """Exponential decay based on age.

    Returns [0, 1] where 1 = brand new, 0.5 = one half-life old.
    Evergreen atoms should have valid_from = 0 → returns 1.0 (no decay).
    """
    if valid_from <= 0:
        return 1.0  # No timestamp → treat as fresh

    age_seconds = time.time() - valid_from
    if age_seconds <= 0:
        return 1.0

    age_days = age_seconds / 86400.0
    return math.pow(0.5, age_days / half_life_days)


# ---------------------------------------------------------------------------
# Retrieval functions
# ---------------------------------------------------------------------------

def _normalize_fts_ranks(atoms_with_ranks: list[tuple[Atom, float]]) -> list[tuple[Atom, float]]:
    """Normalize FTS5 ranks to [0, 1] relevance scores.

    FTS5 rank is negative (lower = more relevant).
    We convert to positive relevance where 1.0 = best match.
    """
    if not atoms_with_ranks:
        return []

    ranks = [r for _, r in atoms_with_ranks]
    min_rank = min(ranks)  # Most relevant (most negative)
    max_rank = max(ranks)  # Least relevant
    span = max_rank - min_rank

    result = []
    for atom, rank in atoms_with_ranks:
        if span > 0:
            # Invert and normalize: most negative → 1.0, least negative → 0.1
            relevance = 1.0 - 0.9 * (rank - min_rank) / span
        else:
            relevance = 1.0
        result.append((atom, relevance))

    return result


def retrieve(
    db: KnowledgeDB,
    query: str,
    config: RetrievalConfig | None = None,
) -> list[ScoredAtom]:
    """Main retrieval entry point.

    Pipeline: FTS5 search → pre-filter → quality gate → time decay → score → diversify

    Args:
        db: KnowledgeDB connection
        query: User query string
        config: Optional retrieval configuration

    Returns:
        List of ScoredAtom, sorted by final_score descending
    """
    if not query or not query.strip():
        return []

    cfg = config or RetrievalConfig()

    # Auto-rescore: if >50% zero-quality atoms, bulk backfill once per process
    _ensure_rescored(db)

    # Step 1: FTS5 retrieval (widened candidate pool)
    conn = db.connect()
    try:
        # Sanitize FTS5 query: escape special characters
        fts_query = _sanitize_fts_query(query)
        rows = conn.execute(
            """
            SELECT a.*, rank as fts_rank
            FROM atoms a
            JOIN atoms_fts f ON a.rowid = f.rowid
            WHERE atoms_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, cfg.fts_limit),
        ).fetchall()
    except Exception as e:
        logger.warning("FTS5 search failed for query=%r: %s", query[:50], e)
        return []

    if not rows:
        return []

    # Parse into (Atom, fts_rank) pairs
    raw_results = []
    for row in rows:
        row_dict = dict(row)
        fts_rank = row_dict.pop("fts_rank", 0)
        atom = Atom.from_row(row_dict)
        raw_results.append((atom, fts_rank))

    logger.debug("FTS5 returned %d candidates for query=%r", len(raw_results), query[:50])

    # Step 2: Pre-filter (stability, status, promotion_status)
    filtered = []
    for atom, rank in raw_results:
        if cfg.project_id and str(getattr(atom, "scope_project", "") or "").strip() != cfg.project_id:
            continue
        if atom.stability in cfg.exclude_stability:
            continue
        if atom.status not in cfg.min_status:
            continue
        if atom.promotion_status and atom.promotion_status not in cfg.allowed_promotion_status:
            continue
        filtered.append((atom, rank))

    if not filtered:
        return []

    # Step 3: Normalize FTS ranks to relevance scores
    normalized = _normalize_fts_ranks(filtered)

    # Step 4: Quality gate + multiplicative scoring
    scored: list[ScoredAtom] = []
    for atom, relevance in normalized:
        quality = atom.quality_auto

        # Quality gate
        if quality < cfg.min_quality:
            continue

        # Time decay
        decay = compute_time_decay(atom.valid_from, cfg.decay_half_life_days)

        # Multiplicative final score
        final = relevance * quality * decay

        scored.append(ScoredAtom(
            atom=atom,
            fts_rank=0,  # Raw rank not needed after normalization
            relevance=relevance,
            quality=quality,
            time_decay=decay,
            final_score=final,
        ))

    if not scored:
        return []

    # Step 5: Sort by final score
    scored.sort(key=lambda s: s.final_score, reverse=True)

    # Step 6: Source diversification (max N per episode)
    diversified = _diversify(scored, cfg.max_per_episode)

    # Step 7: Limit results
    return diversified[:cfg.result_limit]


def _diversify(scored: list[ScoredAtom], max_per_episode: int) -> list[ScoredAtom]:
    """Limit atoms per episode to promote source diversity."""
    counts: dict[str, int] = {}
    result = []
    for sa in scored:
        ep_id = sa.atom.episode_id
        current = counts.get(ep_id, 0)
        if current >= max_per_episode:
            continue
        counts[ep_id] = current + 1
        result.append(sa)
    return result


def _sanitize_fts_query(query: str) -> str:
    """Sanitize query for FTS5 MATCH syntax.

    FTS5 uses special operators: AND, OR, NOT, NEAR, quotes.
    For safety, we wrap each token in double-quotes.
    """
    # Remove FTS5 special characters
    import re
    # Split on whitespace, quote each token
    tokens = query.strip().split()
    if not tokens:
        return '""'

    # If query is short, just use it as-is with OR between tokens
    if len(tokens) <= 3:
        return " OR ".join(f'"{t}"' for t in tokens if t)

    # For longer queries, use first 5 tokens to avoid too broad matching
    return " OR ".join(f'"{t}"' for t in tokens[:5] if t)


# ---------------------------------------------------------------------------
# Batch scoring (for backfill / re-scoring existing atoms)
# ---------------------------------------------------------------------------

def rescore_all_atoms(db: KnowledgeDB, batch_size: int = 500) -> dict:
    """Re-score all atoms using the unified Score Contract.

    For Phase 6.1 backfill: re-compute quality/value for atoms
    that were extracted before the Score Contract was introduced.

    Returns stats dict with counts.
    """
    from chatgptrest.evomap.knowledge.scoring.contract import (
        ScoreComponents,
        compute_quality,
        compute_value,
        score_structure,
        score_information_density,
        score_completeness,
        score_specificity,
        SOURCE_QUALITY,
    )

    conn = db.connect()
    cursor = conn.execute("SELECT COUNT(*) FROM atoms")
    total = cursor.fetchone()[0]

    updated = 0
    skipped = 0
    offset = 0

    while offset < total:
        rows = conn.execute(
            "SELECT * FROM atoms LIMIT ? OFFSET ?",
            (batch_size, offset),
        ).fetchall()

        if not rows:
            break

        for row in rows:
            atom = Atom.from_row(dict(row))

            # Skip if already scored with Score Contract
            try:
                existing = json.loads(atom.scores_json) if atom.scores_json else {}
                if existing.get("extractor"):
                    skipped += 1
                    continue
            except Exception:
                pass

            # Determine extractor type from atom metadata
            extractor = _guess_extractor(atom)

            # Compute scores
            sc = ScoreComponents(
                extractor=extractor,
                structure_score=score_structure(atom.answer),
                information_density=score_information_density(atom.answer),
                completeness=score_completeness(atom.answer),
                specificity=score_specificity(atom.question),
                evidence_quality=SOURCE_QUALITY.get(extractor, 0.5),
                doc_value=atom.value_auto if atom.value_auto > 0 else 0.5,
                type_prior=0.6,
                actionability=0.5,
                uniqueness=0.6,
            )
            sc.final_quality = compute_quality(sc)
            sc.final_value = compute_value(sc)

            # Update atom
            conn.execute(
                """UPDATE atoms
                   SET quality_auto = ?, value_auto = ?,
                       source_quality = ?, scores_json = ?
                   WHERE atom_id = ?""",
                (sc.final_quality, sc.final_value,
                 SOURCE_QUALITY.get(extractor, 0.5),
                 sc.to_json(), atom.atom_id),
            )
            updated += 1

        offset += batch_size
        conn.commit()

    conn.commit()
    stats = {"total": total, "updated": updated, "skipped": skipped}
    logger.info("Rescore complete: %s", stats)
    return stats


def _guess_extractor(atom: Atom) -> str:
    """Guess which extractor produced an atom based on metadata."""
    try:
        app = json.loads(atom.applicability) if atom.applicability else {}
    except Exception:
        app = {}

    source = app.get("source", "")
    if "note" in source or "lifeos" in source:
        return "note_section"
    elif "chat" in source:
        return "chat_followup"
    elif "maint" in source:
        return "maint_runbook"
    elif "commit" in source:
        return "commit_kd0"

    # Fallback: guess from atom_id prefix
    aid = atom.atom_id
    if "commit" in aid:
        return "commit_kd0"
    elif "distill" in aid:
        return "chat_followup"
    elif "sec" in aid:
        return "note_section"
    elif "maint" in aid:
        return "maint_runbook"

    return "unknown"
