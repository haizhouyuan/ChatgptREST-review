from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.kb.vector_store import NumpyVectorStore, VectorHit

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"


@dataclass
class EvoMapVectorRecord:
    atom_id: str
    question: str
    answer: str
    promotion_status: str
    quality_auto: float
    groundedness: float
    scope_project: str
    source_bucket: str
    raw_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def embed_text(self) -> str:
        parts = [self.question.strip(), self.answer.strip()]
        return "\n\n".join(part for part in parts if part)


class EvoMapVectorIndex:
    """Thin EvoMap vector wrapper over NumpyVectorStore.

    Kept separate from KB Hub because EvoMap atoms and KB artifacts have
    different lifecycles, metadata, and promotion semantics.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self._db_path = str(db_path)
        self._store = NumpyVectorStore(self._db_path)
        self._embedding_model_name = embedding_model
        self._embedder = None
        self._embed_attempted = False

    def close(self) -> None:
        self._store.close()

    def count(self) -> int:
        return self._store.count()

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        if self._embed_attempted:
            return None
        self._embed_attempted = True
        try:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=self._embedding_model_name)
            logger.info("EvoMap vector lane loaded fastembed model %s", self._embedding_model_name)
        except Exception as exc:
            logger.warning("EvoMap vector lane unavailable (FTS-only fallback): %s", exc)
            self._embedder = None
        return self._embedder

    def _embed_texts(self, texts: list[str]) -> list[np.ndarray] | None:
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            return [np.asarray(vec, dtype=np.float32) for vec in embedder.embed(texts)]
        except Exception as exc:
            logger.warning("EvoMap vector embedding failed: %s", exc)
            return None

    def index_records(
        self,
        records: list[EvoMapVectorRecord],
        *,
        batch_size: int = 256,
        save_every_batches: int = 4,
    ) -> dict[str, Any]:
        if not records:
            return {"indexed": 0, "skipped": 0, "vector_count": self.count()}

        chunk_size = max(1, int(batch_size or 0) or len(records))
        flush_every = max(1, int(save_every_batches or 0) or 1)
        indexed = 0
        batches = 0
        for start in range(0, len(records), chunk_size):
            chunk = records[start:start + chunk_size]
            texts = [record.embed_text() for record in chunk]
            embeddings = self._embed_texts(texts)
            if embeddings is None:
                return {
                    "indexed": indexed,
                    "skipped": len(records) - indexed,
                    "vector_count": self.count(),
                    "mode": "vector_partial" if indexed > 0 else "fts_only",
                    "batches": batches,
                }

            for record, embedding in zip(chunk, embeddings):
                self._store.remove(record.atom_id)
                self._store.add(
                    doc_id=record.atom_id,
                    chunk_id="atom_full",
                    embedding=embedding,
                    metadata={
                        "question": record.question,
                        "promotion_status": record.promotion_status,
                        "quality_auto": record.quality_auto,
                        "groundedness": record.groundedness,
                        "scope_project": record.scope_project,
                        "source_bucket": record.source_bucket,
                        "raw_ref": record.raw_ref,
                        **dict(record.metadata or {}),
                    },
                )
                indexed += 1
            batches += 1
            if batches % flush_every == 0:
                self._store.save()

        self._store.save()
        return {
            "indexed": indexed,
            "skipped": 0,
            "vector_count": self.count(),
            "mode": "vector",
            "batches": batches,
            "batch_size": chunk_size,
            "save_every_batches": flush_every,
        }

    def search(self, query: str, *, top_k: int = 10, min_score: float = 0.0) -> list[VectorHit]:
        text = str(query or "").strip()
        if not text:
            return []
        embeddings = self._embed_texts([text])
        if not embeddings:
            return []
        hits = self._store.search(embeddings[0], top_k=top_k)
        return [hit for hit in hits if float(hit.score) >= float(min_score)]


def fetch_records_for_vectorization(
    db: KnowledgeDB,
    *,
    promotion_statuses: tuple[str, ...] = ("active", "candidate"),
    scope_projects: tuple[str, ...] = (),
    source_buckets: tuple[str, ...] = (),
    min_quality: float = 0.15,
    limit: int = 0,
) -> list[EvoMapVectorRecord]:
    conn = db.connect()
    where = [
        "COALESCE(a.quality_auto, 0) >= ?",
        "a.promotion_status IN ({})".format(",".join("?" for _ in promotion_statuses)),
    ]
    params: list[Any] = [float(min_quality), *promotion_statuses]
    if scope_projects:
        where.append("COALESCE(a.scope_project, d.project, '') IN ({})".format(",".join("?" for _ in scope_projects)))
        params.extend(scope_projects)
    if source_buckets:
        where.append(
            "COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') IN ({})".format(
                ",".join("?" for _ in source_buckets)
            )
        )
        params.extend(source_buckets)
    limit_clause = f"LIMIT {int(limit)}" if int(limit or 0) > 0 else ""
    rows = conn.execute(
        f"""
        SELECT
            a.atom_id,
            a.question,
            a.answer,
            a.promotion_status,
            a.quality_auto,
            a.groundedness,
            COALESCE(a.scope_project, '') AS scope_project,
            COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') AS source_bucket,
            COALESCE(d.raw_ref, '') AS raw_ref
        FROM atoms a
        LEFT JOIN episodes e ON e.episode_id = a.episode_id
        LEFT JOIN documents d ON d.doc_id = e.doc_id
        WHERE {" AND ".join(where)}
        ORDER BY a.promotion_status DESC, a.quality_auto DESC, a.groundedness DESC, a.atom_id ASC
        {limit_clause}
        """,
        params,
    ).fetchall()
    return [
        EvoMapVectorRecord(
            atom_id=str(row["atom_id"]),
            question=str(row["question"] or ""),
            answer=str(row["answer"] or ""),
            promotion_status=str(row["promotion_status"] or ""),
            quality_auto=float(row["quality_auto"] or 0.0),
            groundedness=float(row["groundedness"] or 0.0),
            scope_project=str(row["scope_project"] or ""),
            source_bucket=str(row["source_bucket"] or ""),
            raw_ref=str(row["raw_ref"] or ""),
        )
        for row in rows
    ]


def probe_vector_store(path: str | Path) -> dict[str, Any]:
    db_path = Path(path)
    info = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "vector_count": 0,
    }
    if not db_path.exists() or info["size_bytes"] <= 0:
        return info
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()
        info["vector_count"] = int(row[0] or 0)
    except Exception:
        info["vector_count"] = 0
    finally:
        conn.close()
    return info
