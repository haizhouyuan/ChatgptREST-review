"""Vector store with pluggable backends.

Default implementation: numpy brute-force cosine similarity.
Vectors are persisted to SQLite and loaded into memory on startup.

Design decisions (from architecture review):
    - numpy brute-force for ≤10,000 vectors (<5ms search)
    - VectorStore protocol for future pluggability (sqlite-vec, LanceDB)
    - SQLite BLOB storage for persistence
    - Memory footprint: ~10MB for 1,500 × 768-dim vectors
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────

@dataclass
class VectorHit:
    """A single search result from the vector store."""

    doc_id: str
    chunk_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Protocol ──────────────────────────────────────────────────────

@runtime_checkable
class VectorStore(Protocol):
    """Protocol for pluggable vector store backends.

    Implementing this protocol allows swapping numpy brute-force
    for sqlite-vec, LanceDB, Qdrant, etc. without changing callers.
    """

    def add(
        self,
        doc_id: str,
        chunk_id: str,
        embedding: np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a vector to the store."""
        ...

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
    ) -> list[VectorHit]:
        """Search for nearest vectors by cosine similarity."""
        ...

    def remove(self, doc_id: str) -> int:
        """Remove all vectors for a document. Returns count removed."""
        ...

    def count(self) -> int:
        """Total number of vectors in the store."""
        ...

    def save(self) -> None:
        """Persist the store to disk (if applicable)."""
        ...

    def close(self) -> None:
        """Release resources."""
        ...


# ── DDL ───────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS vectors (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    chunk_id    TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    dim         INTEGER NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vectors_doc
    ON vectors(doc_id);
"""


# ── Numpy Implementation ─────────────────────────────────────────

class NumpyVectorStore:
    """Brute-force cosine similarity using numpy.

    All vectors are held in a contiguous numpy array in memory.
    Persistence is via SQLite (vectors stored as BLOBs).

    Performance characteristics:
        - 1,500 × 768-dim: search <1ms, memory ~10MB
        - 10,000 × 768-dim: search <5ms, memory ~60MB

    Usage::

        store = NumpyVectorStore("vectors.db")
        store.add("doc1", "chunk1", np.random.randn(768))
        hits = store.search(np.random.randn(768), top_k=5)
        store.save()
        store.close()
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_DDL)
        self._conn.commit()

        # In-memory index
        self._ids: list[str] = []           # vector IDs
        self._doc_ids: list[str] = []       # document IDs
        self._chunk_ids: list[str] = []     # chunk IDs
        self._metadata: list[dict] = []     # metadata dicts
        self._matrix: np.ndarray | None = None  # (N, dim) matrix
        self._dim: int | None = None
        self._dirty = False
        self._closed = False

        # Load existing vectors from SQLite
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load all vectors from SQLite into memory."""
        rows = self._conn.execute(
            "SELECT id, doc_id, chunk_id, embedding, dim, metadata FROM vectors"
        ).fetchall()

        if not rows:
            return

        self._dim = rows[0][3].__len__() // 4  # float32 = 4 bytes
        # Actually use stored dim
        self._dim = rows[0][4]
        vectors = []

        for row_id, doc_id, chunk_id, blob, dim, meta_json in rows:
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            if len(vec) != dim:
                logger.warning(
                    "Vector dim mismatch: expected %d, got %d (id=%s)",
                    dim, len(vec), row_id,
                )
                continue
            self._ids.append(row_id)
            self._doc_ids.append(doc_id)
            self._chunk_ids.append(chunk_id)
            self._metadata.append(json.loads(meta_json))
            vectors.append(vec)

        if vectors:
            self._matrix = np.vstack(vectors)
            # Normalize for cosine similarity (precompute)
            norms = np.linalg.norm(self._matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            self._matrix = self._matrix / norms

        logger.info(
            "Loaded %d vectors (dim=%d) from %s",
            len(self._ids), self._dim or 0, self._db_path,
        )

    # ── VectorStore Protocol ──────────────────────────────────────

    def add(
        self,
        doc_id: str,
        chunk_id: str,
        embedding: np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a vector to the in-memory index.

        Call :meth:`save` to persist to SQLite.
        """
        if self._closed:
            raise RuntimeError("NumpyVectorStore is closed")

        vec = np.asarray(embedding, dtype=np.float32).flatten()
        dim = len(vec)

        if self._dim is None:
            self._dim = dim
        elif dim != self._dim:
            raise ValueError(
                f"Dimension mismatch: store has dim={self._dim}, got {dim}"
            )

        vec_id = str(uuid.uuid4())

        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        self._ids.append(vec_id)
        self._doc_ids.append(doc_id)
        self._chunk_ids.append(chunk_id)
        self._metadata.append(metadata or {})

        if self._matrix is None:
            self._matrix = vec.reshape(1, -1)
        else:
            self._matrix = np.vstack([self._matrix, vec.reshape(1, -1)])

        self._dirty = True

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
    ) -> list[VectorHit]:
        """Search by cosine similarity (dot product on normalized vectors)."""
        if self._closed:
            raise RuntimeError("NumpyVectorStore is closed")

        if self._matrix is None or len(self._ids) == 0:
            return []

        q = np.asarray(query_vec, dtype=np.float32).flatten()
        if len(q) != self._dim:
            raise ValueError(
                f"Query dim mismatch: store has dim={self._dim}, got {len(q)}"
            )

        # Normalize query
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        # Cosine similarity = dot product of normalized vectors
        scores = self._matrix @ q

        # Get top-K indices
        k = min(top_k, len(scores))
        if k <= 0:
            return []

        # Use argpartition for efficiency (O(n) vs O(n log n))
        if k < len(scores):
            top_idx = np.argpartition(scores, -k)[-k:]
        else:
            top_idx = np.arange(len(scores))

        # Sort top-K by score descending
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        return [
            VectorHit(
                doc_id=self._doc_ids[i],
                chunk_id=self._chunk_ids[i],
                score=float(scores[i]),
                metadata=self._metadata[i],
            )
            for i in top_idx
        ]

    def remove(self, doc_id: str) -> int:
        """Remove all vectors for a document."""
        if self._closed:
            raise RuntimeError("NumpyVectorStore is closed")

        indices_to_remove = [
            i for i, d in enumerate(self._doc_ids) if d == doc_id
        ]
        if not indices_to_remove:
            return 0

        keep = [i for i in range(len(self._ids)) if i not in set(indices_to_remove)]

        self._ids = [self._ids[i] for i in keep]
        self._doc_ids = [self._doc_ids[i] for i in keep]
        self._chunk_ids = [self._chunk_ids[i] for i in keep]
        self._metadata = [self._metadata[i] for i in keep]

        if keep and self._matrix is not None:
            self._matrix = self._matrix[keep]
        else:
            self._matrix = None
            self._dim = None

        self._dirty = True
        return len(indices_to_remove)

    def count(self) -> int:
        """Total vectors in memory."""
        return len(self._ids)

    def save(self) -> None:
        """Persist all vectors to SQLite (full rewrite)."""
        if self._closed:
            raise RuntimeError("NumpyVectorStore is closed")
        if not self._dirty:
            return

        import time
        now = time.time()

        self._conn.execute("DELETE FROM vectors")
        for i, vec_id in enumerate(self._ids):
            raw_vec = self._matrix[i].astype(np.float32)
            blob = raw_vec.tobytes()
            meta_json = json.dumps(self._metadata[i], ensure_ascii=False, default=str)
            self._conn.execute(
                """INSERT INTO vectors (id, doc_id, chunk_id, embedding, dim, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (vec_id, self._doc_ids[i], self._chunk_ids[i],
                 blob, self._dim, meta_json, now),
            )
        self._conn.commit()
        self._dirty = False
        logger.info("Saved %d vectors to %s", len(self._ids), self._db_path)

    def close(self) -> None:
        """Save and close."""
        if not self._closed:
            if self._dirty:
                self.save()
            self._closed = True
            self._conn.close()
            logger.debug("NumpyVectorStore closed: %s", self._db_path)
