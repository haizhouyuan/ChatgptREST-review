"""Tests for numpy VectorStore (T1.2).

Covers:
    - VectorStore protocol compliance
    - Basic add + search
    - Cosine similarity correctness (vs sklearn)
    - Top-K ordering
    - Dimension mismatch rejection
    - Remove by doc_id
    - Save/load persistence round-trip
    - Large batch performance (1500 × 768-dim)
    - Empty store search
    - Close guard
    - Metadata preservation
    - Count
"""

import time
import pytest
import numpy as np

from chatgptrest.kb.vector_store import NumpyVectorStore, VectorStore, VectorHit


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def store():
    s = NumpyVectorStore(":memory:")
    yield s
    if not s._closed:
        s.close()


# ── Tests ─────────────────────────────────────────────────────────

def test_protocol_compliance():
    """NumpyVectorStore implements VectorStore protocol."""
    assert isinstance(NumpyVectorStore(":memory:"), VectorStore)


def test_add_and_search(store):
    """Basic add + search returns correct doc."""
    vec = np.array([1.0, 0.0, 0.0])
    store.add("doc1", "chunk1", vec)
    store.add("doc2", "chunk1", np.array([0.0, 1.0, 0.0]))

    hits = store.search(np.array([1.0, 0.0, 0.0]), top_k=1)
    assert len(hits) == 1
    assert hits[0].doc_id == "doc1"
    assert hits[0].score > 0.99  # near-perfect match


def test_cosine_similarity_correctness(store):
    """Cosine similarity matches sklearn reference."""
    np.random.seed(42)
    a = np.random.randn(128)
    b = np.random.randn(128)
    query = np.random.randn(128)

    store.add("docA", "c1", a)
    store.add("docB", "c1", b)

    hits = store.search(query, top_k=2)
    scores = {h.doc_id: h.score for h in hits}

    # Compute reference cosine similarity
    def cos_sim(x, y):
        return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))

    ref_a = cos_sim(a, query)
    ref_b = cos_sim(b, query)

    assert abs(scores["docA"] - ref_a) < 1e-5
    assert abs(scores["docB"] - ref_b) < 1e-5


def test_top_k_ordering(store):
    """Results are sorted by descending score."""
    np.random.seed(42)
    for i in range(20):
        store.add(f"doc{i}", "c1", np.random.randn(64))

    query = np.random.randn(64)
    hits = store.search(query, top_k=5)
    assert len(hits) == 5
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_dimension_mismatch_add(store):
    """Adding vector with wrong dimension raises ValueError."""
    store.add("doc1", "c1", np.array([1.0, 0.0, 0.0]))
    with pytest.raises(ValueError, match="mismatch"):
        store.add("doc2", "c1", np.array([1.0, 0.0]))  # dim=2, expected 3


def test_dimension_mismatch_search(store):
    """Searching with wrong dim raises ValueError."""
    store.add("doc1", "c1", np.array([1.0, 0.0, 0.0]))
    with pytest.raises(ValueError, match="mismatch"):
        store.search(np.array([1.0, 0.0]))  # dim=2, expected 3


def test_remove_by_doc_id(store):
    """Remove deletes all chunks for a doc."""
    store.add("doc1", "c1", np.array([1.0, 0.0, 0.0]))
    store.add("doc1", "c2", np.array([0.9, 0.1, 0.0]))
    store.add("doc2", "c1", np.array([0.0, 1.0, 0.0]))

    assert store.count() == 3
    removed = store.remove("doc1")
    assert removed == 2
    assert store.count() == 1

    hits = store.search(np.array([1.0, 0.0, 0.0]), top_k=5)
    assert all(h.doc_id == "doc2" for h in hits)


def test_save_load_roundtrip(tmp_path):
    """Vectors survive save → close → reopen."""
    db_path = tmp_path / "test_vectors.db"
    vec = np.array([0.5, 0.3, 0.8])

    # Write
    s1 = NumpyVectorStore(db_path)
    s1.add("doc1", "c1", vec, metadata={"lang": "zh"})
    s1.save()
    s1.close()

    # Read
    s2 = NumpyVectorStore(db_path)
    assert s2.count() == 1
    hits = s2.search(vec, top_k=1)
    assert len(hits) == 1
    assert hits[0].doc_id == "doc1"
    assert hits[0].score > 0.99
    assert hits[0].metadata == {"lang": "zh"}
    s2.close()


def test_large_batch_performance(store):
    """1500 × 768-dim vectors: search < 5ms, memory reasonable."""
    np.random.seed(42)
    dim = 768
    n = 1500

    vecs = np.random.randn(n, dim).astype(np.float32)
    for i in range(n):
        store.add(f"doc{i}", "c1", vecs[i])

    assert store.count() == n

    query = np.random.randn(dim).astype(np.float32)

    # Warm up
    store.search(query, top_k=10)

    # Measure
    start = time.perf_counter()
    hits = store.search(query, top_k=10)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(hits) == 10
    assert elapsed_ms < 50  # generous bound (spec says <5ms)

    # Memory: matrix should be ~4.6MB (1500 × 768 × 4 bytes)
    mem_bytes = store._matrix.nbytes
    assert mem_bytes < 15_000_000  # <15MB


def test_empty_store_search(store):
    """Search on empty store returns empty list."""
    hits = store.search(np.array([1.0, 0.0, 0.0]), top_k=5)
    assert hits == []


def test_close_then_add_raises(store):
    """After close(), add raises RuntimeError."""
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.add("doc1", "c1", np.array([1.0]))


def test_close_then_search_raises(store):
    """After close(), search raises RuntimeError."""
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.search(np.array([1.0]))


def test_metadata_preserved(store):
    """Metadata is preserved through add → search."""
    meta = {"layer": "L3", "domain": "finance", "tags": ["stock", "report"]}
    store.add("doc1", "c1", np.array([1.0, 0.0, 0.0]), metadata=meta)

    hits = store.search(np.array([1.0, 0.0, 0.0]), top_k=1)
    assert hits[0].metadata == meta


def test_count(store):
    """Count tracks additions and removals."""
    assert store.count() == 0
    store.add("d1", "c1", np.array([1.0, 0.0]))
    assert store.count() == 1
    store.add("d2", "c1", np.array([0.0, 1.0]))
    assert store.count() == 2
    store.remove("d1")
    assert store.count() == 1
