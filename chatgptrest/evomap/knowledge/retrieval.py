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
import re
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Stability, PromotionStatus

logger = logging.getLogger(__name__)

# Sentinel: tracks whether auto-rescore has run in this process
_RESCORE_DONE = False

_PLANNING_SEMANTIC_TERMS = (
    "两轮车",
    "关节模组",
    "竞争分析",
    "市场竞争",
    "来访准备",
    "合作洽谈",
    "绿源",
    "钛虎",
    "机器人",
    "车轮",
    "车身",
    "市场",
    "竞争",
    "分析",
    "来访",
    "拜访",
    "准备",
    "合作",
    "洽谈",
    "交流",
    "关节",
    "模组",
)

_PLANNING_TERM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "来访准备": ("来访", "拜访", "准备", "接待", "会议纪要"),
    "合作洽谈": ("合作", "洽谈", "交流"),
    "竞争分析": ("竞争", "市场", "分析", "对标"),
    "市场竞争": ("市场", "竞争", "对标"),
    "来访": ("来访", "拜访"),
    "合作": ("合作", "洽谈", "交流"),
    "关节模组": ("关节模组", "关节", "模组"),
    "钛虎": ("钛虎", "机器人", "关节模组", "合作"),
    "绿源": ("绿源", "两轮车", "车轮", "车身"),
    "两轮车": ("两轮车", "车轮"),
}

_PLANNING_ENTITY_TERMS = (
    "绿源",
    "钛虎",
    "九号",
    "新日",
    "金彭",
    "雅迪",
    "爱玛",
    "小牛",
    "台铃",
    "鹿明",
)

_PLANNING_EXACT_BOOST_TERMS: dict[str, float] = {
    "绿源": 0.20,
    "钛虎": 0.20,
    "九号": 0.18,
    "新日": 0.18,
    "金彭": 0.18,
    "雅迪": 0.16,
    "爱玛": 0.16,
    "小牛": 0.16,
    "台铃": 0.16,
    "鹿明": 0.16,
    "关节模组": 0.10,
    "市场竞争": 0.10,
    "竞争分析": 0.10,
    "来访准备": 0.10,
    "合作洽谈": 0.10,
    "车轮": 0.08,
    "来访": 0.06,
    "拜访": 0.06,
    "准备": 0.05,
    "合作": 0.05,
}


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
    PLANNING_EXPLICIT_PATH = "planning_explicit_path"
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

    # Runtime-facing surface name (set by runtime_retrieval_config).
    surface_name: str = RetrievalSurface.USER_HOT_PATH.value

    # Planning explicit fallback guardrails.
    planning_fallback_max_results: int = 0
    planning_fallback_min_quality: float = 0.7
    planning_fallback_allowed_buckets: tuple[str, ...] = ()

    # Optional vector lane.
    enable_vector_search: bool = False
    vector_limit: int = 20
    vector_min_score: float = 0.0
    vector_rrf_k: int = 60
    vector_db_path: str = ""


_SURFACE_ALLOWED_PROMOTION_STATUS: dict[RetrievalSurface, tuple[str, ...]] = {
    RetrievalSurface.USER_HOT_PATH: (PromotionStatus.ACTIVE.value,),
    RetrievalSurface.PLANNING_EXPLICIT_PATH: (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.CANDIDATE.value,
        PromotionStatus.STAGED.value,
    ),
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

_PLANNING_FALLBACK_ALLOWED_BUCKETS = (
    "planning_latest_output",
    "planning_outputs",
    "planning_review_pack",
    "planning_strategy",
    "planning_budget",
    "planning_controlled",
)

_SURFACE_DEFAULT_OVERRIDES: dict[RetrievalSurface, dict[str, Any]] = {
    RetrievalSurface.USER_HOT_PATH: {
        "surface_name": RetrievalSurface.USER_HOT_PATH.value,
    },
    RetrievalSurface.PLANNING_EXPLICIT_PATH: {
        "surface_name": RetrievalSurface.PLANNING_EXPLICIT_PATH.value,
        "min_status": (
            AtomStatus.CANDIDATE.value,
            AtomStatus.SCORED.value,
            AtomStatus.GATE_A.value,
            AtomStatus.GATE_B.value,
            AtomStatus.GATE_C.value,
            AtomStatus.REFINED.value,
            AtomStatus.PUBLISHED.value,
            "reviewed",
        ),
        "planning_fallback_max_results": 3,
        "planning_fallback_min_quality": 0.7,
        "planning_fallback_allowed_buckets": _PLANNING_FALLBACK_ALLOWED_BUCKETS,
        "enable_vector_search": True,
        "vector_limit": 20,
        "vector_min_score": 0.0,
    },
    RetrievalSurface.DIAGNOSTIC_PATH: {
        "surface_name": RetrievalSurface.DIAGNOSTIC_PATH.value,
    },
    RetrievalSurface.SHADOW_EXPERIMENT_PATH: {
        "surface_name": RetrievalSurface.SHADOW_EXPERIMENT_PATH.value,
    },
    RetrievalSurface.PROMOTION_REVIEW_PATH: {
        "surface_name": RetrievalSurface.PROMOTION_REVIEW_PATH.value,
    },
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
        **_SURFACE_DEFAULT_OVERRIDES.get(resolved_surface, {}),
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


def summarize_retrieval_layers(scored_atoms: list["ScoredAtom"]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in scored_atoms:
        layer = str(getattr(item, "retrieval_layer", "") or "").strip().lower() or "unknown"
        counts[layer] = counts.get(layer, 0) + 1
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
    vector_score: float = 0.0
    retrieval_source: str = "fts"
    retrieval_layer: str = "promoted_active"
    source_bucket: str = ""
    source_ref: str = ""
    document_id: str = ""
    entity_boost: float = 0.0

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
            "vector_score": round(self.vector_score, 3),
            "retrieval_source": self.retrieval_source,
            "retrieval_layer": self.retrieval_layer,
            "source_bucket": self.source_bucket,
            "source_ref": self.source_ref,
            "entity_boost": round(self.entity_boost, 3),
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


def _normalize_dense_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    min_score = min(values)
    max_score = max(values)
    span = max_score - min_score
    normalized: dict[str, float] = {}
    for item_id, score in scores.items():
        if span > 0:
            normalized[item_id] = 0.1 + 0.9 * ((score - min_score) / span)
        else:
            normalized[item_id] = 1.0
    return normalized


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _planning_query_terms(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []

    tokens = [token.strip() for token in re.split(r"[\s,，、/|;；]+", text) if token.strip()]
    terms: list[str] = list(tokens)
    compact = "".join(tokens) if tokens else text

    if compact:
        for term in _PLANNING_SEMANTIC_TERMS:
            if term in compact:
                terms.append(term)
                terms.extend(_PLANNING_TERM_SYNONYMS.get(term, ()))

    # Preserve a few original phrases for exact-match recovery before broadening.
    if text not in terms:
        terms.insert(0, text)
    if compact and compact not in terms:
        terms.insert(1, compact)

    return _dedupe_preserve_order(terms)


def _planning_entity_exact_multiplier(
    query: str,
    atom: Atom,
    row: dict[str, Any],
    *,
    source_bucket: str,
) -> float:
    doc_project = str(row.get("_doc_project") or row.get("scope_project") or "").strip().lower()
    if doc_project != "planning":
        return 1.0

    haystack = " ".join(
        [
            str(row.get("_doc_title") or ""),
            str(row.get("_raw_ref") or ""),
            str(getattr(atom, "question", "") or ""),
            str(getattr(atom, "canonical_question", "") or ""),
            str(getattr(atom, "answer", "") or "")[:400],
        ]
    )
    if not haystack.strip():
        return 1.0

    boost = 0.0
    seen: set[str] = set()
    for term in _planning_query_terms(query):
        weight = _PLANNING_EXACT_BOOST_TERMS.get(term)
        if weight is None or term in seen:
            continue
        seen.add(term)
        if term in haystack:
            boost += weight

    if (
        source_bucket == "planning_controlled"
        and any(term in haystack for term in _PLANNING_ENTITY_TERMS if term in query)
    ):
        boost += 0.08

    return min(1.35, 1.0 + boost)


def _rrf_scores(rankings: list[list[str]], *, rrf_k: int = 60) -> dict[str, float]:
    if not rankings:
        return {}
    scores: dict[str, float] = {}
    for ranked_ids in rankings:
        for rank, item_id in enumerate(ranked_ids, 1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank)
    return _normalize_dense_scores(scores)


def _load_atom_context_rows(conn: Any, atom_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not atom_ids:
        return {}
    placeholders = ",".join("?" for _ in atom_ids)
    rows = conn.execute(
        f"""
        SELECT
            a.*,
            e.doc_id AS _doc_id,
            COALESCE(d.project, '') AS _doc_project,
            COALESCE(d.title, '') AS _doc_title,
            COALESCE(d.raw_ref, '') AS _raw_ref,
            COALESCE(d.meta_json, '{{}}') AS _doc_meta_json
        FROM atoms a
        LEFT JOIN episodes e ON e.episode_id = a.episode_id
        LEFT JOIN documents d ON d.doc_id = e.doc_id
        WHERE a.atom_id IN ({placeholders})
        """,
        atom_ids,
    ).fetchall()
    return {str(row["atom_id"]): dict(row) for row in rows}


def _substring_fallback_rows(
    conn: Any,
    query: str,
    cfg: RetrievalConfig,
) -> list[dict[str, Any]]:
    """Use a conservative LIKE-based fallback when FTS returns no planning hits.

    This is intentionally narrow:
    - only used by the planning explicit surface
    - only used after FTS yields zero rows
    - only broad enough to recover Chinese/raw-ingress phrases that FTS tokenization
      misses, while still keeping retrieval bounded by the runtime surface guards
    """

    tokens = (
        _planning_query_terms(query)
        if cfg.surface_name == RetrievalSurface.PLANNING_EXPLICIT_PATH.value
        else [token.strip() for token in query.split() if token.strip()]
    )
    if not tokens:
        return []

    like_clauses: list[str] = []
    match_parts: list[str] = []
    match_params: list[Any] = []
    where_params: list[Any] = []
    for token in tokens[:8]:
        pattern = f"%{token}%"
        like_clauses.append(
            "("
            "a.question LIKE ? OR a.answer LIKE ? OR COALESCE(a.canonical_question, '') LIKE ? "
            "OR COALESCE(d.title, '') LIKE ? OR COALESCE(d.raw_ref, '') LIKE ?"
            ")"
        )
        match_parts.append(
            "("
            "CASE WHEN a.question LIKE ? THEN 1 ELSE 0 END + "
            "CASE WHEN a.answer LIKE ? THEN 1 ELSE 0 END + "
            "CASE WHEN COALESCE(a.canonical_question, '') LIKE ? THEN 1 ELSE 0 END + "
            "CASE WHEN COALESCE(d.title, '') LIKE ? THEN 1 ELSE 0 END + "
            "CASE WHEN COALESCE(d.raw_ref, '') LIKE ? THEN 1 ELSE 0 END"
            ")"
        )
        match_params.extend([pattern, pattern, pattern, pattern, pattern])
        where_params.extend([pattern, pattern, pattern, pattern, pattern])

    project_clause = ""
    if cfg.project_id:
        project_clause = " AND COALESCE(a.scope_project, d.project, '') = ?"

    sql = f"""
        SELECT
            a.*,
            0.0 AS fts_rank,
            ({' + '.join(match_parts)}) AS match_score,
            e.doc_id AS _doc_id,
            COALESCE(d.project, '') AS _doc_project,
            COALESCE(d.title, '') AS _doc_title,
            COALESCE(d.raw_ref, '') AS _raw_ref,
            COALESCE(d.meta_json, '{{}}') AS _doc_meta_json
        FROM atoms a
        LEFT JOIN episodes e ON e.episode_id = a.episode_id
        LEFT JOIN documents d ON d.doc_id = e.doc_id
        WHERE ({' OR '.join(like_clauses)})
          {project_clause}
        ORDER BY
            match_score DESC,
            CASE WHEN a.promotion_status = ? THEN 0 ELSE 1 END,
            a.quality_auto DESC,
            a.valid_from DESC
        LIMIT ?
    """
    params = [*match_params, *where_params]
    if cfg.project_id:
        params.append(cfg.project_id)
    params.extend([PromotionStatus.ACTIVE.value, cfg.fts_limit])
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _extract_source_bucket(row: dict[str, Any]) -> str:
    meta_json = str(row.get("_doc_meta_json") or "").strip()
    if meta_json:
        try:
            meta = json.loads(meta_json)
            review_meta = meta.get("planning_review")
            if isinstance(review_meta, dict):
                bucket = str(review_meta.get("source_bucket") or "").strip()
                if bucket:
                    return bucket
        except Exception:
            pass
    raw_ref = str(row.get("_raw_ref") or "").strip()
    doc_project = str(row.get("_doc_project") or row.get("scope_project") or "").strip().lower()
    if raw_ref and doc_project == "planning":
        try:
            from chatgptrest.evomap.knowledge.planning_review_plane import _source_bucket

            return str(_source_bucket(raw_ref) or "").strip()
        except Exception:
            return ""
    return ""


def _vector_hits_for_query(query: str, cfg: RetrievalConfig) -> tuple[dict[str, float], dict[str, float]]:
    if not cfg.enable_vector_search:
        return {}, {}
    try:
        from chatgptrest.core.openmind_paths import resolve_evomap_vector_db_path
        from chatgptrest.evomap.knowledge.vector_lane import EvoMapVectorIndex

        vector_db_path = cfg.vector_db_path or resolve_evomap_vector_db_path()
        index = EvoMapVectorIndex(vector_db_path)
        try:
            raw_hits = index.search(query, top_k=max(cfg.vector_limit, cfg.result_limit), min_score=cfg.vector_min_score)
        finally:
            index.close()
    except Exception as exc:
        logger.debug("EvoMap vector search unavailable for query=%r: %s", query[:50], exc)
        return {}, {}

    best_scores: dict[str, float] = {}
    for hit in raw_hits:
        atom_id = str(hit.doc_id or "").strip()
        if not atom_id:
            continue
        score = float(hit.score or 0.0)
        if score > best_scores.get(atom_id, float("-inf")):
            best_scores[atom_id] = score
    normalized = _normalize_dense_scores(best_scores)
    return best_scores, normalized


def _resolve_retrieval_layer(atom: Atom, cfg: RetrievalConfig, *, source_bucket: str) -> str | None:
    status = str(getattr(atom, "promotion_status", "") or "").strip().lower()
    if (
        source_bucket == "planning_controlled"
        and cfg.surface_name != RetrievalSurface.PLANNING_EXPLICIT_PATH.value
        and status in {
            PromotionStatus.ACTIVE.value,
            PromotionStatus.CANDIDATE.value,
            PromotionStatus.STAGED.value,
        }
    ):
        return None
    if status == PromotionStatus.ACTIVE.value:
        return "promoted_active"
    if cfg.surface_name == RetrievalSurface.PLANNING_EXPLICIT_PATH.value:
        if status not in {PromotionStatus.CANDIDATE.value, PromotionStatus.STAGED.value}:
            return None
        if source_bucket not in set(cfg.planning_fallback_allowed_buckets or ()):
            return None
        if float(getattr(atom, "quality_auto", 0.0) or 0.0) < float(cfg.planning_fallback_min_quality):
            return None
        return "candidate_fallback" if status == PromotionStatus.CANDIDATE.value else "staged_fallback"
    if status == PromotionStatus.CANDIDATE.value:
        return "promoted_candidate"
    if status == PromotionStatus.STAGED.value:
        return "promoted_staged"
    return None


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
            SELECT
                a.*,
                rank AS fts_rank,
                e.doc_id AS _doc_id,
                COALESCE(d.project, '') AS _doc_project,
                COALESCE(d.title, '') AS _doc_title,
                COALESCE(d.raw_ref, '') AS _raw_ref,
                COALESCE(d.meta_json, '{}') AS _doc_meta_json
            FROM atoms a
            JOIN atoms_fts f ON a.rowid = f.rowid
            LEFT JOIN episodes e ON e.episode_id = a.episode_id
            LEFT JOIN documents d ON d.doc_id = e.doc_id
            WHERE atoms_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, cfg.fts_limit),
        ).fetchall()
    except Exception as e:
        logger.warning("FTS5 search failed for query=%r: %s", query[:50], e)
        rows = []

    if not rows and cfg.surface_name == RetrievalSurface.PLANNING_EXPLICIT_PATH.value:
        try:
            rows = _substring_fallback_rows(conn, query, cfg)
        except Exception as exc:
            logger.debug(
                "Planning substring fallback failed for query=%r: %s",
                query[:50],
                exc,
            )
            rows = []

    # Parse into (Atom, fts_rank, row) tuples
    raw_results: list[tuple[Atom, float, dict[str, Any]]] = []
    atom_rows: dict[str, dict[str, Any]] = {}
    atom_map: dict[str, Atom] = {}
    for row in rows:
        row_dict = dict(row)
        fts_rank = row_dict.pop("fts_rank", 0)
        atom = Atom.from_row(row_dict)
        raw_results.append((atom, fts_rank, dict(row)))
        atom_rows[atom.atom_id] = dict(row)
        atom_map[atom.atom_id] = atom

    logger.debug("FTS5 returned %d candidates for query=%r", len(raw_results), query[:50])

    # Step 2: Pre-filter (stability, status, promotion_status)
    filtered: list[tuple[Atom, float, dict[str, Any]]] = []
    for atom, rank, row in raw_results:
        if cfg.project_id and str(getattr(atom, "scope_project", "") or "").strip() != cfg.project_id:
            continue
        if atom.stability in cfg.exclude_stability:
            continue
        if atom.status not in cfg.min_status:
            continue
        if atom.promotion_status and atom.promotion_status not in cfg.allowed_promotion_status:
            continue
        filtered.append((atom, rank, row))

    # Step 3: Normalize FTS ranks to relevance scores
    normalized = _normalize_fts_ranks([(atom, rank) for atom, rank, _row in filtered])
    fts_relevance = {atom.atom_id: relevance for atom, relevance in normalized}
    fts_ranked_ids = [atom.atom_id for atom, _relevance in normalized]

    # Step 3.5: Optional vector lane (active/candidate/reviewed slice only)
    raw_vector_scores, vector_relevance = _vector_hits_for_query(query, cfg)
    vector_ranked_ids = [item_id for item_id, _score in sorted(raw_vector_scores.items(), key=lambda item: item[1], reverse=True)]
    fused_relevance = (
        _rrf_scores([ranked for ranked in (fts_ranked_ids, vector_ranked_ids) if ranked], rrf_k=cfg.vector_rrf_k)
        if len([ranked for ranked in (fts_ranked_ids, vector_ranked_ids) if ranked]) > 1
        else {}
    )

    missing_vector_ids = [item_id for item_id in vector_ranked_ids if item_id not in atom_rows]
    if missing_vector_ids:
        loaded_rows = _load_atom_context_rows(conn, missing_vector_ids)
        for atom_id, row in loaded_rows.items():
            atom_rows[atom_id] = row
            atom_map[atom_id] = Atom.from_row(row)

    # Step 4: Quality gate + multiplicative scoring
    active_scored: list[ScoredAtom] = []
    fallback_scored: list[ScoredAtom] = []
    candidate_ids = []
    seen_ids: set[str] = set()
    for item_id in fts_ranked_ids + vector_ranked_ids:
        if item_id not in seen_ids:
            candidate_ids.append(item_id)
            seen_ids.add(item_id)
    for atom_id in candidate_ids:
        atom = atom_map.get(atom_id)
        row = atom_rows.get(atom_id) or {}
        if atom is None:
            continue
        if cfg.project_id and str(getattr(atom, "scope_project", "") or "").strip() != cfg.project_id:
            continue
        if atom.stability in cfg.exclude_stability:
            continue
        if atom.status not in cfg.min_status:
            continue
        if atom.promotion_status and atom.promotion_status not in cfg.allowed_promotion_status:
            continue

        source_bucket = _extract_source_bucket(row)
        layer = _resolve_retrieval_layer(atom, cfg, source_bucket=source_bucket)
        if layer is None:
            continue

        relevance = fused_relevance.get(atom_id) or fts_relevance.get(atom_id) or vector_relevance.get(atom_id) or 0.0
        quality = atom.quality_auto

        # Quality gate
        if quality < cfg.min_quality:
            continue
        if layer in {"candidate_fallback", "staged_fallback"} and quality < cfg.planning_fallback_min_quality:
            continue

        # Time decay
        decay = compute_time_decay(atom.valid_from, cfg.decay_half_life_days)
        entity_multiplier = 1.0
        if cfg.surface_name == RetrievalSurface.PLANNING_EXPLICIT_PATH.value:
            entity_multiplier = _planning_entity_exact_multiplier(
                query,
                atom,
                row,
                source_bucket=source_bucket,
            )

        # Multiplicative final score
        final = relevance * quality * decay * entity_multiplier

        retrieval_source = "fts"
        if atom_id in fts_relevance and atom_id in vector_relevance:
            retrieval_source = "fts+vector"
        elif atom_id in vector_relevance:
            retrieval_source = "vector"

        scored_atom = ScoredAtom(
            atom=atom,
            fts_rank=0,  # Raw rank not needed after normalization
            relevance=relevance,
            quality=quality,
            time_decay=decay,
            final_score=final,
            vector_score=float(raw_vector_scores.get(atom_id, 0.0) or 0.0),
            retrieval_source=retrieval_source,
            retrieval_layer=layer,
            source_bucket=source_bucket,
            source_ref=str(row.get("_raw_ref") or ""),
            document_id=str(row.get("_doc_id") or ""),
            entity_boost=max(0.0, entity_multiplier - 1.0),
        )
        if layer in {"candidate_fallback", "staged_fallback"}:
            fallback_scored.append(scored_atom)
        else:
            active_scored.append(scored_atom)

    # Step 5: Sort by final score
    active_scored.sort(key=lambda s: s.final_score, reverse=True)
    fallback_scored.sort(key=lambda s: s.final_score, reverse=True)

    # Step 6: Source diversification (max N per episode)
    diversified_active = _diversify(active_scored, cfg.max_per_episode)
    diversified_fallback = _diversify(fallback_scored, cfg.max_per_episode)

    # Step 7: Limit results
    results = diversified_active[:cfg.result_limit]
    if (
        cfg.surface_name == RetrievalSurface.PLANNING_EXPLICIT_PATH.value
        and cfg.planning_fallback_max_results > 0
    ):
        fallback_pool = diversified_fallback[: cfg.planning_fallback_max_results]
        combined = diversified_active + fallback_pool
        combined.sort(key=lambda item: item.final_score, reverse=True)
        results = combined[:cfg.result_limit]
    elif cfg.surface_name != RetrievalSurface.PLANNING_EXPLICIT_PATH.value:
        results = (diversified_active + diversified_fallback)[:cfg.result_limit]
    return results[:cfg.result_limit]


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
