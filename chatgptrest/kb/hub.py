"""KB Hub — unified retrieval facade with hybrid search.

Combines:
    - KBRetriever (FTS5 full-text search, BM25 ranking)
    - NumpyVectorStore (cosine similarity on embeddings)
    - RRF fusion (reciprocal rank fusion to merge results)
    - evidence_pack mode (full-coverage retrieval for report writing)
    - Auto-embedding generation (via FastEmbed)

This is the single entry point for all KB operations in the
Advisor/Funnel pipeline.

Design decisions:
    - Hybrid search (FTS5 + vector) merged via existing rrf_fuse()
    - evidence_pack mode returns high-coverage results for reports (A2/A3)
    - Top-K mode (default) for quick intent routing and kb_probe
    - Quality score used as a boost factor, not a hard filter
    - Auto-embedding: if no embedding provided, generates via FastEmbed
    - No premature adoption of multi-tier routing (KB/Memory/Archive)
      — that belongs in Phase 3 when we have enough data to benefit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from chatgptrest.kb.retrieval import KBRetriever, SearchResult, rrf_fuse
from chatgptrest.kb.vector_store import NumpyVectorStore, VectorHit
from chatgptrest.kb.versioning import KBVersionManager

logger = logging.getLogger(__name__)

# Type alias for embedding function
EmbeddingFn = Callable[[list[str]], list[np.ndarray]]


# ── Data Models ───────────────────────────────────────────────────

@dataclass
class HybridHit:
    """Unified search hit from hybrid retrieval."""

    artifact_id: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0           # RRF-fused score
    fts_score: float = 0.0       # BM25 component
    vec_score: float = 0.0       # cosine similarity component
    source_path: str = ""
    content_type: str = ""
    quality_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── KBHub ─────────────────────────────────────────────────────────

class KBHub:
    """Unified KB retrieval facade.

    Usage::

        hub = KBHub(db_path="kb.db", vec_db_path="vectors.db")

        # Quick probe (top-K, for intent routing)
        # Auto-generates embedding if vectors enabled
        hits = hub.search("安徽项目进展", top_k=5)

        # Evidence pack (full coverage, for report writing)
        evidence = hub.evidence_pack("安徽外协", max_docs=30)

        # Index a new document (auto-generates embedding if not provided)
        hub.index_document("doc1", "外协方案 v2", content)

    Args:
        db_path: SQLite path for FTS5 index
        vec_db_path: SQLite path for vector store (default: same dir)
        embedding_fn: Optional custom embedding function.
                      If not provided, uses FastEmbed (BAAI/bge-small-en-v1.5)
    """

    DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        vec_db_path: str | Path | None = None,
        *,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ) -> None:
        self._fts = KBRetriever(db_path)
        self._vec = NumpyVectorStore(vec_db_path or db_path) if vec_db_path else None
        self._closed = False
        self._embedding_model_name = embedding_model
        self._embedder = None  # lazy init
        self._embed_ready = False  # avoid repeated failed init attempts
        # Version manager (L4)
        version_db = str(db_path).replace(".db", "_versions.db") if db_path != ":memory:" else ":memory:"
        self._versions = KBVersionManager(version_db)

    def _get_embedder(self):
        """Lazy-init fastembed TextEmbedding model. Returns None if unavailable."""
        if self._embedder is not None:
            return self._embedder
        if self._embed_ready:  # already tried and failed
            return None
        self._embed_ready = True
        try:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self._embedding_model_name)
            logger.info("fastembed loaded: %s", self._embedding_model_name)
        except Exception as e:
            logger.warning("fastembed unavailable (FTS5-only mode): %s", e)
            self._embedder = None
        return self._embedder

    def _embed_texts(self, texts: list[str]) -> list[np.ndarray] | None:
        """Embed texts via fastembed. Returns None if embedder unavailable."""
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            return [np.array(v) for v in embedder.embed(texts)]
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None

    # ── Indexing ──────────────────────────────────────────────────

    def index_document(
        self,
        artifact_id: str,
        title: str,
        content: str,
        embedding: np.ndarray | None = None,
        *,
        source_path: str = "",
        tags: list[str] | None = None,
        content_type: str = "",
        quality_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
        chunk_id: str = "full",
        auto_embed: bool = True,
        author: str = "system",
    ) -> None:
        """Index a document for both FTS5 and vector search.

        Args:
            artifact_id: Unique document ID
            title: Document title
            content: Full text content (indexed by FTS5)
            embedding: Optional vector embedding. If not provided and auto_embed=True,
                      will auto-generate via FastEmbed.
            chunk_id: Chunk identifier within the document
            auto_embed: If True and no embedding provided, auto-generate via FastEmbed
            author: Author for version tracking
        """
        if self._closed:
            raise RuntimeError("KBHub is closed")

        # Create new version (if content changed)
        try:
            self._versions.create_version(
                doc_id=artifact_id,
                content=content,
                author=author,
                change_note=f"Indexed: {title}",
            )
        except Exception as e:
            logger.warning("Version tracking failed for %s: %s", artifact_id, e)

        # Advisory: warn about untagged docs (fail-open)
        if not tags:
            logger.info("KB index_document: %s has no tags (title=%s)", artifact_id, title[:60])

        # FTS5 index (always)
        self._fts.index_text(
            artifact_id=artifact_id,
            title=title,
            content=content,
            source_path=source_path,
            tags=tags,
            content_type=content_type,
            quality_score=quality_score,
        )

        # Keep vector rows aligned with FTS replacement semantics for this doc.
        vectors_dirty = False
        if self._vec is not None:
            removed = self._vec.remove(artifact_id)
            vectors_dirty = removed > 0

        # Vector index: auto-generate embedding if not provided (P1-2/Issue #53)
        if embedding is None and self._vec is not None:
            # Issue #53: Chunk embedding instead of 2000-char truncation
            chunk_size = 800
            overlap = 200
            chunks = []
            
            if len(content) <= chunk_size:
                chunks.append(content)
            else:
                start = 0
                while start < len(content):
                    chunks.append(content[start:start + chunk_size])
                    start += chunk_size - overlap
            
            # Embed all chunks at once
            vecs = self._embed_texts(chunks)
            if vecs:
                for i, vec in enumerate(vecs):
                    # For hybrid search, we still just need one vector per chunk pointing to the document
                    self._vec.add(
                        doc_id=artifact_id,
                        chunk_id=f"{chunk_id}_{i}",
                        embedding=vec,
                        metadata={**(metadata or {"title": title}), "chunk_idx": i}
                    )
                vectors_dirty = True
        elif embedding is not None and self._vec is not None:
            # Explicit single embedding provided
            self._vec.add(
                doc_id=artifact_id,
                chunk_id=chunk_id,
                embedding=embedding,
                metadata=metadata or {"title": title},
            )
            vectors_dirty = True

        if vectors_dirty and self._vec is not None:
            self._vec.save()

    # ── Search ────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        query_embedding: np.ndarray | None = None,
        fts_weight: float = 0.5,
        vec_weight: float = 0.5,
        min_quality: float = 0.0,
        auto_embed: bool = True,
    ) -> list[HybridHit]:
        """Hybrid search combining FTS5 + vector via RRF fusion.

        If auto_embed=True and no query_embedding is provided,
        automatically generates embedding via FastEmbed.

        Phase 6.2.2 improvements:
        - Widened candidate pool (candidate_k = max(top_k*5, 30))
        - Vector hit hydration (fill snippet from FTS index)
        - Unified quality gate after fusion (not just FTS side)

        Args:
            query: Text query for FTS5 search
            query_embedding: Optional vector for similarity search.
                            If not provided and auto_embed=True, auto-generates.
            top_k: Number of results to return
            fts_weight: Weight for FTS5 results (not used in RRF, kept for API)
            vec_weight: Weight for vector results (not used in RRF, kept for API)
            min_quality: Minimum quality score filter
            auto_embed: If True and no query_embedding provided, auto-generate via FastEmbed

        Returns:
            List of HybridHit results, sorted by fused score.
        """
        if self._closed:
            raise RuntimeError("KBHub is closed")

        # [6.2.2] Widen candidate pool — don't truncate to top_k before fusion
        candidate_k = max(top_k * 5, 30)

        # P1-2: Auto-generate query embedding via fastembed
        if query_embedding is None:
            vecs = self._embed_texts([query])
            if vecs:
                query_embedding = vecs[0]

        # FTS5 search — no min_quality here, unified gate after fusion
        fts_results = self._fts.search(
            query, limit=candidate_k, min_quality=0.0
        )

        # Vector search (if embedding available)
        vec_results: list[SearchResult] = []
        if query_embedding is not None and self._vec is not None and self._vec.count() > 0:
            vec_hits = self._vec.search(query_embedding, top_k=candidate_k)
            # Convert VectorHit → SearchResult for RRF fusion
            vec_results = [
                SearchResult(
                    artifact_id=vh.doc_id,
                    title=vh.metadata.get("title", ""),
                    snippet="",  # Will be hydrated below
                    score=vh.score,
                )
                for vh in vec_hits
            ]

        # [6.2.2] Hydrate vector hit snippets from FTS data
        if vec_results:
            fts_snippets = {r.artifact_id: r for r in fts_results}
            for vr in vec_results:
                if vr.artifact_id in fts_snippets:
                    src = fts_snippets[vr.artifact_id]
                    vr.snippet = src.snippet
                    vr.source_path = src.source_path
                    vr.content_type = src.content_type
                    vr.quality_score = src.quality_score
                elif vr.snippet == "":
                    # Attempt direct FTS lookup for hydration
                    try:
                        hydrated = self._fts.search(
                            vr.artifact_id, limit=1, min_quality=0.0
                        )
                        if hydrated:
                            vr.snippet = hydrated[0].snippet
                            vr.source_path = hydrated[0].source_path
                            vr.content_type = hydrated[0].content_type
                            vr.quality_score = hydrated[0].quality_score
                    except Exception:
                        pass  # Hydration failed, snippet stays empty

        # Fusion — with widened candidate pool
        if fts_results and vec_results:
            fused = rrf_fuse(fts_results, vec_results, top_n=candidate_k)
        elif fts_results:
            fused = fts_results[:candidate_k]
        elif vec_results:
            fused = vec_results[:candidate_k]
        else:
            return []

        # [6.2.2] Unified quality gate — applied AFTER fusion
        if min_quality > 0:
            fused = [r for r in fused if r.quality_score >= min_quality]

        # Trim to final top_k after quality gate
        fused = fused[:top_k]

        # Build HybridHit with component scores
        fts_scores = {r.artifact_id: r.score for r in fts_results}
        vec_scores = {r.artifact_id: r.score for r in vec_results}

        return [
            HybridHit(
                artifact_id=r.artifact_id,
                title=r.title,
                snippet=r.snippet,
                score=r.score,
                fts_score=fts_scores.get(r.artifact_id, 0.0),
                vec_score=vec_scores.get(r.artifact_id, 0.0),
                source_path=r.source_path,
                content_type=r.content_type,
                quality_score=r.quality_score,
            )
            for r in fused
        ]

    def evidence_pack(
        self,
        query: str,
        *,
        max_docs: int = 30,
        query_embedding: np.ndarray | None = None,
        min_quality: float = 0.0,
        auto_embed: bool = True,
    ) -> list[HybridHit]:
        """Full-coverage retrieval for report writing.

        Unlike search() which returns top-K, evidence_pack returns
        as many relevant documents as possible (up to max_docs).
        Used by the report_graph when intent = WRITE_REPORT.

        Strategy:
            - Cast a wider net: 3× max_docs for FTS5, 3× for vector
            - Merge via RRF
            - Return up to max_docs results sorted by relevance
        """
        return self.search(
            query,
            top_k=max_docs,
            query_embedding=query_embedding,
            min_quality=min_quality,
            auto_embed=auto_embed,
        )

    # ── Stats ─────────────────────────────────────────────────────

    def count(self) -> dict[str, int]:
        """Return counts of indexed documents."""
        return {
            "fts_docs": self._fts.count_indexed(),
            "vectors": self._vec.count() if self._vec else 0,
        }

    # ── Lifecycle ─────────────────────────────────────────────────

    def save(self) -> None:
        """Persist vector store to disk."""
        if not self._closed and self._vec is not None:
            self._vec.save()

    @property
    def versions(self) -> KBVersionManager:
        """Access the version manager for this KB."""
        return self._versions

    def close(self) -> None:
        """Close all resources."""
        if not self._closed:
            self._closed = True
            if self._vec is not None:
                self._vec.close()
            if self._versions:
                self._versions.close()
            logger.debug("KBHub closed")
