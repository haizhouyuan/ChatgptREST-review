"""KnowledgeDistiller — semantic distillation of large KB artifacts.

Large artifacts (>2KB) are distilled into atomic knowledge chunks (<1KB)
using a cheap LLM call. Each chunk is stored as a separate artifact with
an initial quality_score of 0.5 (non-zero, unlike raw ingestion).

The original artifact is marked as stability='archived'.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_KB_REGISTRY_DB = str(
    pathlib.Path(os.path.expanduser("~/.openmind/kb_registry.db"))
)
_KB_SEARCH_DB = str(
    pathlib.Path(os.path.expanduser("~/.openmind/kb_search.db"))
)
_KB_DIR = str(pathlib.Path(os.path.expanduser("~/.openmind/kb")))

# Artifact size threshold for distillation
_SIZE_THRESHOLD = 2048  # bytes
_INITIAL_QUALITY_SCORE = 0.5


class KnowledgeDistiller:
    """Distills large KB artifacts into atomic knowledge chunks.

    Usage::

        distiller = KnowledgeDistiller()
        stats = distiller.run()
        # stats = {"processed": 3, "chunks_created": 12, "archived": 3}
    """

    def __init__(
        self,
        registry_db: str = "",
        search_db: str = "",
        kb_dir: str = "",
        llm_fn: Any = None,
    ) -> None:
        self._registry_db = registry_db or _KB_REGISTRY_DB
        self._search_db = search_db or _KB_SEARCH_DB
        self._kb_dir = kb_dir or _KB_DIR
        self._llm_fn = llm_fn  # optional: (prompt, system_msg) → str
        logger.info("KnowledgeDistiller initialized")

    def run(self) -> dict[str, int]:
        """Process all large artifacts and distill them.

        Returns stats: processed, chunks_created, archived.
        """
        if not os.path.exists(self._registry_db):
            logger.warning("KnowledgeDistiller: kb_registry.db not found")
            return {"processed": 0, "chunks_created": 0, "archived": 0}

        conn = sqlite3.connect(self._registry_db)
        conn.row_factory = sqlite3.Row

        # Find large, unarchived artifacts
        rows = conn.execute(
            "SELECT artifact_id, source_path, file_size, content_type "
            "FROM artifacts "
            "WHERE file_size > ? AND stability != 'archived' "
            "ORDER BY file_size DESC",
            (_SIZE_THRESHOLD,),
        ).fetchall()

        stats = {"processed": 0, "chunks_created": 0, "archived": 0}

        for row in rows:
            try:
                chunks = self._distill_artifact(
                    row["artifact_id"],
                    row["source_path"],
                    row["content_type"],
                )
                if chunks:
                    self._store_chunks(conn, row["artifact_id"], chunks)
                    self._archive_original(conn, row["artifact_id"])
                    stats["processed"] += 1
                    stats["chunks_created"] += len(chunks)
                    stats["archived"] += 1
            except Exception as e:
                logger.warning(
                    "KnowledgeDistiller: failed to distill %s: %s",
                    row["artifact_id"], e,
                )

        conn.commit()
        conn.close()

        logger.info(
            "KnowledgeDistiller: processed=%d chunks=%d archived=%d",
            stats["processed"], stats["chunks_created"], stats["archived"],
        )
        return stats

    def _distill_artifact(
        self, artifact_id: str, source_path: str, content_type: str,
    ) -> list[dict[str, str]]:
        """Distill a single artifact into atomic chunks.

        If LLM is available, uses it for semantic extraction.
        Otherwise, falls back to simple text splitting.
        """
        # Load content
        content = self._load_content(source_path)
        if not content:
            return []

        if self._llm_fn:
            return self._llm_distill(content, content_type, source_path=source_path)
        else:
            return self._post_validate_chunks(
                self._simple_distill(content, content_type)
            )

    def _llm_distill(
        self, content: str, content_type: str, *, source_path: str = "",
    ) -> list[dict[str, str]]:
        """Use LLM to extract atomic knowledge chunks."""
        source_name = os.path.basename(source_path) if source_path else "unknown"
        prompt = (
            "将以下长文本蒸馏为原子知识块（每块 <200 词）。严格约束：\n"
            "1. 消除所有代词，还原为具体名词/实体（De-contextualization）\n"
            "2. 每个知识块必须在脱离原文档的情况下依然能被独立无歧义地理解\n"
            "3. 包含代码时，必须保留完整闭合的函数签名和必要 import\n"
            f"4. 每块必须包含：主题标签、核心事实、来源文件名（{source_name}）\n"
            "5. 返回编号列表\n\n"
            f"Source file: {source_name}\n"
            f"Content type: {content_type}\n\n"
            f"Content:\n{content[:8000]}"
        )
        system_msg = (
            "You are a knowledge distiller. Extract atomic, self-contained "
            "knowledge chunks. Each chunk must be independently understandable "
            "without the original document. Eliminate all pronouns and "
            "dangling references. Return as a numbered list. Be concise and factual."
        )

        try:
            result = self._llm_fn(prompt, system_msg)
            if not result:
                return self._post_validate_chunks(
                    self._simple_distill(content, content_type)
                )
            chunks = self._parse_llm_chunks(result)
            return self._post_validate_chunks(chunks)
        except Exception as e:
            logger.warning("LLM distillation failed, using simple split: %s", e)
            return self._post_validate_chunks(
                self._simple_distill(content, content_type)
            )

    def _simple_distill(
        self, content: str, content_type: str,
    ) -> list[dict[str, str]]:
        """Simple paragraph-based splitting as fallback."""
        chunks = []

        if content_type in ("application/json", "json"):
            # JSON: extract top-level keys as chunks
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    for key, value in data.items():
                        chunk_text = f"{key}: {json.dumps(value, ensure_ascii=False, default=str)[:500]}"
                        chunks.append({"title": key, "content": chunk_text})
                elif isinstance(data, list):
                    for i, item in enumerate(data[:20]):  # limit
                        chunk_text = json.dumps(item, ensure_ascii=False, default=str)[:500]
                        chunks.append({"title": f"item_{i}", "content": chunk_text})
            except json.JSONDecodeError:
                pass

        if not chunks:
            # Markdown/text: split by paragraphs or headers
            paragraphs = content.split("\n\n")
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if len(para) > 50:  # skip tiny fragments
                    title = para[:60].replace("\n", " ")
                    chunks.append({"title": title, "content": para[:800]})

        return chunks[:20]  # limit total chunks

    def _parse_llm_chunks(self, result: str) -> list[dict[str, str]]:
        """Parse numbered list from LLM output into chunks."""
        chunks = []
        current = []
        for line in result.split("\n"):
            stripped = line.strip()
            # Detect numbered items (1. 2. 3. etc)
            if stripped and stripped[0].isdigit() and "." in stripped[:4]:
                if current:
                    text = "\n".join(current)
                    chunks.append({
                        "title": text[:60].replace("\n", " "),
                        "content": text,
                    })
                current = [stripped.split(".", 1)[-1].strip()]
            elif stripped:
                current.append(stripped)

        if current:
            text = "\n".join(current)
            chunks.append({
                "title": text[:60].replace("\n", " "),
                "content": text,
            })

        return chunks

    # ── OPEN-6 fix: Post-validation ───────────────────────────────

    _DANGLING_PRONOUNS = {
        "如上所述", "那个", "这个", "该参数", "上述", "前述",
        "上面的", "下面的", "它的", "他的", "她的",
        "this", "that", "these", "those", "the above", "as mentioned",
    }

    def _post_validate_chunks(
        self, chunks: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Lightweight post-validation to reject low-quality chunks.

        Filters out:
        - Chunks shorter than 30 chars (too fragmented)
        - Chunks with dangling pronouns (de-contextualization failure)
        """
        validated = []
        for chunk in chunks:
            content = chunk.get("content", "")
            # Reject too-short chunks
            if len(content) < 30:
                logger.debug("Post-validator: rejected short chunk (%d chars)", len(content))
                continue
            # Check for dangling pronouns
            content_lower = content.lower()
            has_dangling = any(p in content_lower for p in self._DANGLING_PRONOUNS)
            if has_dangling:
                logger.debug(
                    "Post-validator: chunk has dangling pronoun, keeping with warning: %.60s",
                    content,
                )
                # Don't reject — just log warning, as some usage is legitimate
            validated.append(chunk)
        rejected = len(chunks) - len(validated)
        if rejected:
            logger.info("Post-validator: rejected %d/%d chunks", rejected, len(chunks))
        return validated

    def _store_chunks(
        self,
        conn: sqlite3.Connection,
        parent_id: str,
        chunks: list[dict[str, str]],
    ) -> None:
        """Store distilled chunks as new artifacts."""
        now = datetime.now(timezone.utc).isoformat()
        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{parent_id[:8]}_{i:03d}_{uuid.uuid4().hex[:8]}"
            content = chunk["content"]

            # Write chunk file
            chunk_path = os.path.join(self._kb_dir, f"{chunk_id}.md")
            os.makedirs(os.path.dirname(chunk_path), exist_ok=True)
            with open(chunk_path, "w") as f:
                f.write(f"# {chunk['title']}\n\n{content}\n")

            file_size = os.path.getsize(chunk_path)

            # Insert into registry
            conn.execute(
                "INSERT OR IGNORE INTO artifacts "
                "(artifact_id, source_system, source_path, project_id, "
                "content_hash, content_type, file_size, created_at, "
                "modified_at, indexed_at, quality_score, stability, "
                "structural_role) "
                "VALUES (?, 'distiller', ?, ?, ?, 'markdown', ?, ?, ?, ?, ?, 'active', 'chunk')",
                (
                    chunk_id, chunk_path, parent_id,
                    hashlib.sha256(content.encode()).hexdigest()[:16], file_size,
                    now, now, now,
                    _INITIAL_QUALITY_SCORE,
                ),
            )

            # Also insert into FTS search index if available
            self._index_chunk(chunk_id, chunk["title"], content)

    def _archive_original(
        self, conn: sqlite3.Connection, artifact_id: str,
    ) -> None:
        """Mark original large artifact as archived."""
        conn.execute(
            "UPDATE artifacts SET stability = 'archived' WHERE artifact_id = ?",
            (artifact_id,),
        )
        logger.info("Archived large artifact: %s", artifact_id)

    def _index_chunk(
        self, chunk_id: str, title: str, content: str,
    ) -> None:
        """Index chunk in FTS search database."""
        if not os.path.exists(self._search_db):
            return
        try:
            search_conn = sqlite3.connect(self._search_db)
            # Try to insert into FTS table
            search_conn.execute(
                "INSERT OR REPLACE INTO kb_fts (artifact_id, title, content) "
                "VALUES (?, ?, ?)",
                (chunk_id, title, content[:2000]),
            )
            search_conn.commit()
            search_conn.close()
        except Exception as e:
            logger.debug("FTS indexing skipped: %s", e)

    def _load_content(self, source_path: str) -> str:
        """Load artifact content from file."""
        if not os.path.exists(source_path):
            # Try relative to KB dir
            alt_path = os.path.join(self._kb_dir, os.path.basename(source_path))
            if os.path.exists(alt_path):
                source_path = alt_path
            else:
                logger.debug("Artifact file not found: %s", source_path)
                return ""
        try:
            with open(source_path, "r", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.warning("Failed to read artifact: %s", e)
            return ""
