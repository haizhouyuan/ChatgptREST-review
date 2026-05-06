"""
KB Hybrid Retrieval – FTS5 full-text search + future vector/RRF fusion.

This module provides:
1. FTS5 full-text index over KB artifacts (BM25 ranking)
2. Search interface that returns scored results
3. RRF fusion utility for combining multiple ranked lists
4. Extensible design for adding vector search later

Design (from KB DR):
- FTS5 for precision (exact matches)
- Vector embeddings for semantic recall (future: ChromaDB)
- RRF (Reciprocal Rank Fusion) for merging ranked lists
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result with score and metadata."""
    artifact_id: str = ""
    source_path: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0           # Higher is better
    content_type: str = ""
    para_bucket: str = ""
    quality_score: float = 0.0
    version: int = 1              # Document version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# FTS5 Index DDL
# ---------------------------------------------------------------------------

_FTS_DDL = r"""
CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    artifact_id,
    title,
    content,
    source_path,
    tags,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS kb_fts_meta (
    artifact_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    para_bucket TEXT NOT NULL DEFAULT '',
    quality_score REAL NOT NULL DEFAULT 0.0,
    word_count  INTEGER NOT NULL DEFAULT 0,
    indexed_at  TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT ''
);
"""


# ---------------------------------------------------------------------------
# KBRetriever
# ---------------------------------------------------------------------------

class KBRetriever:
    """
    FTS5-based full-text search over KB artifacts.

    Usage::

        retriever = KBRetriever("/path/to/kb_search.db")
        retriever.index_text("art_001", "My Document", "full text...", "/path", ["tag1"])
        results = retriever.search("keyword query")
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._local = threading.local()
        with self._conn() as conn:
            conn.executescript(_FTS_DDL)
            # Migration: add tags column to kb_fts_meta if missing
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(kb_fts_meta)").fetchall()}
                if "tags" not in cols:
                    conn.execute("ALTER TABLE kb_fts_meta ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
                    conn.commit()
            except Exception:
                pass  # graceful: if migration fails, tag filtering just won't find tags

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    # -- Indexing -------------------------------------------------------------

    def index_text(
        self,
        artifact_id: str,
        title: str,
        content: str,
        source_path: str = "",
        tags: list[str] | None = None,
        content_type: str = "",
        para_bucket: str = "",
        quality_score: float = 0.0,
    ) -> None:
        """Index a text document for full-text search."""
        tags_str = " ".join(tags or [])

        with self._conn() as conn:
            # Remove old entry if exists
            conn.execute(
                "DELETE FROM kb_fts WHERE artifact_id = ?",
                (artifact_id,),
            )
            conn.execute(
                "DELETE FROM kb_fts_meta WHERE artifact_id = ?",
                (artifact_id,),
            )

            # Insert FTS
            conn.execute(
                """INSERT INTO kb_fts (artifact_id, title, content, source_path, tags)
                   VALUES (?, ?, ?, ?, ?)""",
                (artifact_id, title, content, source_path, tags_str),
            )

            # Insert metadata
            from datetime import datetime, timezone
            conn.execute(
                """INSERT INTO kb_fts_meta
                   (artifact_id, source_path, title, content_type,
                    para_bucket, quality_score, word_count, indexed_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    artifact_id, source_path, title, content_type,
                    para_bucket, quality_score, len(content.split()),
                    datetime.now(timezone.utc).isoformat(),
                    tags_str,
                ),
            )
            conn.commit()

    def index_file(
        self,
        artifact_id: str,
        file_path: str | Path,
        title: str = "",
        tags: list[str] | None = None,
        content_type: str = "",
        para_bucket: str = "",
        quality_score: float = 0.0,
    ) -> bool:
        """Index a file by reading its content. Returns True on success."""
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Cannot read {path}: {e}")
            return False

        if not title:
            title = path.stem

        self.index_text(
            artifact_id=artifact_id,
            title=title,
            content=content,
            source_path=str(path),
            tags=tags,
            content_type=content_type,
            para_bucket=para_bucket,
            quality_score=quality_score,
        )
        return True

    # -- Query preparation ---------------------------------------------------

    @staticmethod
    def _prepare_fts_query(query: str) -> str:
        """Prepare a search query for FTS5 with unicode61 tokenizer.

        The unicode61 tokenizer treats each CJK character as a separate token.
        We need to extract meaningful terms and combine them for matching.
        Strategy:
          - Extract ASCII words (keep as-is)
          - Extract individual Chinese characters
          - Combine with OR for flexible matching
        """
        import re
        query = query.strip()
        if not query:
            return ""

        # Extract ASCII words (e.g., "PEEK", "PPS") — these are kept as terms
        ascii_words = re.findall(r'[a-zA-Z0-9_]+', query)

        # Extract Chinese characters — each is a separate FTS5 token
        cjk_chars = re.findall(r'[\u4e00-\u9fff]', query)

        # Build FTS5 query: combine terms with OR
        terms = []
        for w in ascii_words:
            terms.append(f'"{w}"')  # quote ASCII words for exact match
        for c in cjk_chars:
            terms.append(c)

        if not terms:
            # Fallback: use the entire query quoted
            safe = query.replace('"', '""')
            return f'"{safe}"'

        return " OR ".join(terms)

    # -- Search ---------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        min_quality: float = 0.0,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        """
        Full-text search using FTS5 BM25 ranking.

        Returns results sorted by relevance (BM25 score × quality boost).
        """
        if not query.strip():
            return []

        fts_query = self._prepare_fts_query(query)
        if not fts_query:
            return []

        with self._conn() as conn:
            # Build optional tag filter clause
            tag_clause = ""
            tag_params: list[str] = []
            if tags:
                # Match any of the provided tags (OR logic)
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("m.tags LIKE ?")
                    tag_params.append(f"%{tag}%")
                tag_clause = " AND (" + " OR ".join(tag_conditions) + ")"

            try:
                rows = conn.execute(
                    f"""SELECT
                        f.artifact_id,
                        f.title,
                        snippet(kb_fts, 2, '→', '←', '…', 30) as snippet,
                        bm25(kb_fts) as bm25_score,
                        m.source_path,
                        m.content_type,
                        m.para_bucket,
                        m.quality_score
                    FROM kb_fts f
                    JOIN kb_fts_meta m ON f.artifact_id = m.artifact_id
                    WHERE kb_fts MATCH ?{tag_clause}
                    ORDER BY bm25(kb_fts)
                    LIMIT ?""",
                    (fts_query, *tag_params, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # Fallback: try quoted phrase match
                try:
                    rows = conn.execute(
                        f"""SELECT
                            f.artifact_id,
                            f.title,
                            snippet(kb_fts, 2, '→', '←', '…', 30) as snippet,
                            bm25(kb_fts) as bm25_score,
                            m.source_path,
                            m.content_type,
                            m.para_bucket,
                            m.quality_score
                        FROM kb_fts f
                        JOIN kb_fts_meta m ON f.artifact_id = m.artifact_id
                        WHERE kb_fts MATCH '"' || ? || '"'{tag_clause}
                        ORDER BY bm25(kb_fts)
                        LIMIT ?""",
                        (query, *tag_params, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []

        results = []
        for row in rows:
            quality = row["quality_score"]
            if quality < min_quality:
                continue

            # Normalize BM25 score (FTS5 returns negative, more negative = better match)
            bm25 = abs(row["bm25_score"])
            # Combine BM25 with quality boost (70% relevance + 30% quality)
            combined = 0.7 * bm25 + 0.3 * quality * bm25

            results.append(SearchResult(
                artifact_id=row["artifact_id"],
                source_path=row["source_path"],
                title=row["title"],
                snippet=row["snippet"],
                score=round(combined, 4),
                content_type=row["content_type"],
                para_bucket=row["para_bucket"],
                quality_score=quality,
            ))

        # Sort by combined score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def count_indexed(self) -> int:
        """Number of indexed documents."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT count(*) as cnt FROM kb_fts_meta"
            ).fetchone()
        return row["cnt"] if row else 0

    # -- Deletion -------------------------------------------------------------

    def remove(self, artifact_id: str) -> None:
        """Remove a document from the index."""
        with self._conn() as conn:
            conn.execute("DELETE FROM kb_fts WHERE artifact_id = ?", (artifact_id,))
            conn.execute("DELETE FROM kb_fts_meta WHERE artifact_id = ?", (artifact_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# RRF Fusion utility
# ---------------------------------------------------------------------------

def rrf_fuse(
    *ranked_lists: list[SearchResult],
    k: int = 60,
    top_n: int = 20,
) -> list[SearchResult]:
    """
    Reciprocal Rank Fusion (RRF) for combining multiple ranked lists.

    Formula: RRF_score(d) = Σ 1/(k + rank_i(d))

    From KB DR: "RRF is presented as a simple method for combining rankings
    from multiple IR systems and is reported to consistently yield better
    results than any individual system."

    Args:
        *ranked_lists: Multiple lists of SearchResult, each pre-sorted by score
        k: RRF constant (default 60, from original paper)
        top_n: Number of results to return
    """
    # Collect RRF scores by artifact_id
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            aid = result.artifact_id
            rrf_scores[aid] = rrf_scores.get(aid, 0.0) + 1.0 / (k + rank)
            if aid not in result_map:
                result_map[aid] = result

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    # Build results with RRF scores
    fused = []
    for aid in sorted_ids[:top_n]:
        result = result_map[aid]
        result.score = round(rrf_scores[aid], 6)
        fused.append(result)

    return fused
