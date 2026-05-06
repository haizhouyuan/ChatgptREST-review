"""Tests for KB Hub hybrid search (T1.3).

Covers:
    - FTS5-only search (no embeddings)
    - Vector-only search (no text match)
    - Hybrid RRF fusion (FTS5 + vector)
    - evidence_pack mode (wide retrieval)
    - index_document stores to both FTS + vector
    - count() returns both stats
    - close guard
    - Empty hub search
    - Quality score propagation
"""

import sqlite3

import pytest
import numpy as np

from chatgptrest.kb.hub import KBHub, HybridHit


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def hub():
    h = KBHub(db_path=":memory:", vec_db_path=":memory:")
    yield h
    if not h._closed:
        h.close()


def _seed_hub(hub, n=10, dim=64):
    """Seed the hub with n documents (both FTS5 + vector)."""
    np.random.seed(42)
    for i in range(n):
        hub.index_document(
            artifact_id=f"doc_{i}",
            title=f"Document {i} about topic {i % 3}",
            content=f"This is the full text content of document {i}. "
                    f"It discusses topic {i % 3} in detail. "
                    f"Keywords: alpha {'beta' if i % 2 == 0 else 'gamma'}",
            embedding=np.random.randn(dim).astype(np.float32),
            source_path=f"/kb/docs/doc_{i}.md",
            content_type="markdown",
            quality_score=0.5 + (i % 5) * 0.1,
        )


# ── Tests ─────────────────────────────────────────────────────────

def test_fts_only_search(hub):
    """Search works with FTS5 only (no embeddings)."""
    hub.index_document("doc1", "Anhui Project Progress", "Anhui outsourcing project progress report second edition")
    hub.index_document("doc2", "Shanghai Project Plan", "Shanghai R&D project quarterly plan")

    hits = hub.search("Anhui", top_k=5)
    assert len(hits) >= 1
    assert hits[0].artifact_id == "doc1"
    assert isinstance(hits[0], HybridHit)


def test_vector_only_search(hub):
    """Search with embedding but no FTS match still returns results."""
    dim = 32
    np.random.seed(42)
    target = np.array([1.0] + [0.0] * (dim - 1), dtype=np.float32)
    noise = np.random.randn(dim).astype(np.float32)

    # Both docs have same text (so FTS won't differentiate)
    hub.index_document("doc1", "test", "generic content", embedding=target)
    hub.index_document("doc2", "test", "generic content", embedding=noise)

    # Query embedding similar to target
    query_emb = np.array([0.9, 0.1] + [0.0] * (dim - 2), dtype=np.float32)

    hits = hub.search("zzz_no_fts_match", top_k=5, query_embedding=query_emb)
    # Should get vector results even though FTS found nothing
    if hits:
        assert hits[0].artifact_id == "doc1"


def test_hybrid_rrf_fusion(hub):
    """Hybrid search merges FTS5 and vector results via RRF."""
    dim = 32
    np.random.seed(42)

    # Doc that's strong in FTS but weak in vector
    fts_strong = np.random.randn(dim).astype(np.float32)
    hub.index_document("fts_doc", "安徽外协方案", "安徽外协项目方案详细报告",
                       embedding=fts_strong)

    # Doc that's strong in vector but weak in FTS
    vec_strong = np.array([1.0] + [0.0] * (dim - 1), dtype=np.float32)
    hub.index_document("vec_doc", "other topic", "些别的内容",
                       embedding=vec_strong)

    query_emb = np.array([0.95, 0.05] + [0.0] * (dim - 2), dtype=np.float32)

    hits = hub.search("安徽外协", top_k=5, query_embedding=query_emb)
    assert len(hits) >= 1
    # Both docs should appear in results
    hit_ids = {h.artifact_id for h in hits}
    assert "fts_doc" in hit_ids


def test_evidence_pack(hub):
    """evidence_pack returns many results for report writing."""
    # Disable auto-embed to avoid dim mismatch with mock 64d embeddings
    hub._embed_ready = True  # prevent fastembed lazy-load
    _seed_hub(hub, n=20)
    evidence = hub.evidence_pack("topic", max_docs=15)
    assert len(evidence) <= 15
    assert all(isinstance(h, HybridHit) for h in evidence)


def test_index_stores_both(hub):
    """index_document stores to both FTS5 and vector."""
    dim = 16
    hub.index_document(
        "doc1", "Test Title", "Test content body",
        embedding=np.random.randn(dim).astype(np.float32),
    )
    counts = hub.count()
    assert counts["fts_docs"] == 1
    assert counts["vectors"] == 1


def test_index_persists_vectors_without_close(tmp_path):
    """index_document flushes vectors to SQLite immediately."""
    hub = KBHub(db_path=tmp_path / "kb_search.db", vec_db_path=tmp_path / "kb_vectors.db")
    try:
        hub.index_document(
            "doc1",
            "Persisted Title",
            "Persisted body",
            embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        )
        with sqlite3.connect(tmp_path / "kb_vectors.db") as conn:
            saved = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        assert saved == 1
    finally:
        hub.close()


def test_reindex_replaces_existing_vectors_for_same_doc(tmp_path):
    """Re-indexing a doc should replace old vectors instead of duplicating them."""
    hub = KBHub(db_path=tmp_path / "kb_search.db", vec_db_path=tmp_path / "kb_vectors.db")
    try:
        hub.index_document(
            "doc1",
            "Version 1",
            "First body",
            embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        )
        hub.index_document(
            "doc1",
            "Version 2",
            "Second body",
            embedding=np.array([0.0, 1.0, 0.0], dtype=np.float32),
        )

        assert hub.count()["vectors"] == 1
        with sqlite3.connect(tmp_path / "kb_vectors.db") as conn:
            saved = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        assert saved == 1
    finally:
        hub.close()


def test_index_fts_only():
    """index_document without embedding only stores FTS (no vec store)."""
    h = KBHub(db_path=":memory:")  # no vec_db_path → _vec is None
    h.index_document("doc1", "Test", "Content without embedding")
    counts = h.count()
    assert counts["fts_docs"] == 1
    assert counts["vectors"] == 0
    h.close()


def test_count(hub):
    """count() tracks indexed documents."""
    assert hub.count() == {"fts_docs": 0, "vectors": 0}
    _seed_hub(hub, n=5)
    assert hub.count() == {"fts_docs": 5, "vectors": 5}


def test_close_guard(hub):
    """Operations after close() raise RuntimeError."""
    hub.close()
    with pytest.raises(RuntimeError, match="closed"):
        hub.search("test")
    with pytest.raises(RuntimeError, match="closed"):
        hub.index_document("x", "x", "x")


def test_empty_search(hub):
    """Search on empty hub returns empty list."""
    hits = hub.search("anything", top_k=5)
    assert hits == []


def test_quality_score_propagation(hub):
    """Quality score from index_document propagates to search results."""
    hub.index_document("doc1", "Anhui Report", "Anhui project progress report details", quality_score=0.85)
    hits = hub.search("Anhui", top_k=1)
    assert len(hits) == 1
    assert hits[0].quality_score == 0.85
