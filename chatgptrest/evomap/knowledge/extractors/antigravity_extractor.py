"""Antigravity conversation extractor for EvoMap.

Scans ~/.gemini/antigravity/brain/<conversation-id>/ for markdown artifacts
produced by the Antigravity AI agent, and extracts them into the
Document → Episode → Atom → Evidence pipeline.

High-value artifacts:
- implementation_plan.md — technical decisions and design proposals
- walkthrough.md — implementation records and verification results
- task.md — task breakdowns and progress tracking
- Domain documents — architecture analyses, code audits, research reports

Skipped:
- *.resolved*, *.metadata.json — internal Antigravity versioning
- .system_generated/ — tool outputs (low extractable value)
- browser/ — screenshots
- *.webp, *.png — binary assets
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Iterator

from chatgptrest.evomap.knowledge.extractors.base import BaseExtractor
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomType,
    Document,
    Episode,
    EpisodeType,
    Evidence,
    Stability,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ANTIGRAVITY_BRAIN_DIR = os.environ.get(
    "ANTIGRAVITY_BRAIN_DIR",
    os.path.expanduser("~/.gemini/antigravity/brain"),
)

# Files to skip (patterns)
_SKIP_PATTERNS = {
    ".resolved",
    ".metadata.json",
}
_SKIP_NAMES = {"task.md"}  # task checklists are low-value for knowledge
_SKIP_DIRS = {"tempmediaStorage", ".system_generated", "browser", ".tempmediaStorage"}
_SKIP_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".mp4"}

# Atom type heuristics (keyword → type)
_DECISION_KEYWORDS = {"决策", "选择", "方案", "decision", "选型", "trade-off", "comparison"}
_TROUBLESHOOT_KEYWORDS = {"修复", "debug", "fix", "bug", "issue", "错误", "问题"}
_PROCEDURE_KEYWORDS = {"步骤", "流程", "procedure", "workflow", "how to", "操作"}
_LESSON_KEYWORDS = {"教训", "lesson", "takeaway", "retrospective", "总结", "经验"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_short(text: str) -> str:
    """SHA-256 hash truncated to 16 hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _is_artifact_md(filename: str) -> bool:
    """Check if a file is a primary artifact markdown (not a resolved/meta copy)."""
    if not filename.endswith(".md"):
        return False
    for pat in _SKIP_PATTERNS:
        if pat in filename:
            return False
    if filename in _SKIP_NAMES:
        return False
    return True


def _read_metadata(md_path: Path) -> dict:
    """Read the .metadata.json sidecar for an artifact."""
    meta_path = md_path.parent / f"{md_path.name}.metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _infer_atom_type(heading: str) -> str:
    """Infer atom type from heading text using keyword heuristics."""
    lower = heading.lower()
    for kw in _DECISION_KEYWORDS:
        if kw in lower:
            return AtomType.DECISION
    for kw in _TROUBLESHOOT_KEYWORDS:
        if kw in lower:
            return AtomType.TROUBLESHOOTING
    for kw in _PROCEDURE_KEYWORDS:
        if kw in lower:
            return AtomType.PROCEDURE
    for kw in _LESSON_KEYWORDS:
        if kw in lower:
            return AtomType.LESSON
    return AtomType.QA  # default


def _split_by_headings(content: str) -> list[tuple[str, str, int]]:
    """Split markdown content by H2/H3 headings.

    Returns list of (heading_text, section_content, line_number) tuples.
    """
    sections: list[tuple[str, str, int]] = []
    lines = content.split("\n")
    current_heading = ""
    current_lines: list[str] = []
    heading_line = 1

    for i, line in enumerate(lines, 1):
        # Match H2 or H3
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            # Save previous section
            if current_heading and current_lines:
                body = "\n".join(current_lines).strip()
                if len(body) >= 30:  # skip tiny sections
                    sections.append((current_heading, body, heading_line))
            current_heading = m.group(2).strip()
            current_lines = []
            heading_line = i
        else:
            current_lines.append(line)

    # Save last section
    if current_heading and current_lines:
        body = "\n".join(current_lines).strip()
        if len(body) >= 30:
            sections.append((current_heading, body, heading_line))

    # If no headings found, treat the whole file as one section
    if not sections and len(content.strip()) >= 50:
        title_line = content.strip().split("\n")[0]
        # Strip markdown heading prefix
        title_line = re.sub(r"^#+\s*", "", title_line).strip() or "Content"
        sections.append((title_line, content.strip(), 1))

    return sections


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class AntigravityExtractor(BaseExtractor):
    """Extract knowledge from Antigravity conversation artifacts.

    Scans the Antigravity brain directory for markdown artifacts and
    extracts them into the EvoMap Document → Episode → Atom pipeline.
    """

    source_name = "antigravity"

    def __init__(self, db, brain_dir: str | None = None, min_section_chars: int = 30):
        super().__init__(db)
        self._brain_dir = Path(brain_dir or ANTIGRAVITY_BRAIN_DIR)
        self._min_section_chars = min_section_chars
        # Cache: conversation_id → list of artifact paths
        self._conv_artifacts: dict[str, list[Path]] = {}

    def _scan_conversations(self) -> dict[str, list[Path]]:
        """Scan brain directory for conversations with artifacts."""
        if self._conv_artifacts:
            return self._conv_artifacts

        if not self._brain_dir.exists():
            logger.warning("Antigravity brain dir not found: %s", self._brain_dir)
            return {}

        for conv_dir in sorted(self._brain_dir.iterdir()):
            if not conv_dir.is_dir():
                continue
            conv_id = conv_dir.name
            if conv_id in _SKIP_DIRS:
                continue

            artifacts = []
            for f in sorted(conv_dir.iterdir()):
                if f.is_dir():
                    continue
                if f.suffix in _SKIP_EXTENSIONS:
                    continue
                if _is_artifact_md(f.name):
                    artifacts.append(f)

            if artifacts:
                self._conv_artifacts[conv_id] = artifacts

        logger.info(
            "AntigravityExtractor: found %d conversations with %d artifacts",
            len(self._conv_artifacts),
            sum(len(v) for v in self._conv_artifacts.values()),
        )
        return self._conv_artifacts

    def _conversation_hash(self, conv_id: str, artifacts: list[Path]) -> str:
        """Compute hash for change detection (based on file mtimes)."""
        mtimes = sorted(str(f.stat().st_mtime) for f in artifacts if f.exists())
        return _sha256_short(f"{conv_id}|{'|'.join(mtimes)}")

    # ── Document layer ───────────────────────────────────────────────

    def extract_documents(self) -> Iterator[Document]:
        """Each conversation with artifacts becomes a Document."""
        convs = self._scan_conversations()

        for conv_id, artifacts in convs.items():
            # Build title from first non-task artifact's metadata
            title = ""
            for art in artifacts:
                meta = _read_metadata(art)
                summary = meta.get("Summary", "")
                if summary:
                    title = summary[:120]
                    break
            if not title:
                title = f"Antigravity conversation {conv_id[:8]}"

            doc = Document(
                source=self.source_name,
                project="antigravity",
                raw_ref=conv_id,
                title=title,
                created_at=min(f.stat().st_ctime for f in artifacts),
                updated_at=max(f.stat().st_mtime for f in artifacts),
                hash=self._conversation_hash(conv_id, artifacts),
                meta_json=json.dumps({
                    "conversation_id": conv_id,
                    "artifact_count": len(artifacts),
                    "artifact_names": [f.name for f in artifacts],
                }),
            )
            yield doc

    # ── Episode layer ────────────────────────────────────────────────

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        """Each artifact file becomes an Episode."""
        conv_id = doc.raw_ref
        artifacts = self._conv_artifacts.get(conv_id, [])

        for art in artifacts:
            meta = _read_metadata(art)
            art_type = meta.get("ArtifactType", "other")
            summary = meta.get("Summary", "")

            # Map artifact type to episode type
            episode_type = EpisodeType.MD_SECTION

            stat = art.stat()
            episode = Episode(
                doc_id=doc.doc_id,
                episode_type=episode_type,
                title=art.stem.replace("_", " ").title(),
                summary=summary[:500] if summary else "",
                start_ref=str(art),
                end_ref=str(art),
                time_start=stat.st_ctime,
                time_end=stat.st_mtime,
                source_ext=json.dumps({
                    "filename": art.name,
                    "artifact_type": art_type,
                    "conversation_id": conv_id,
                    "size_bytes": stat.st_size,
                }),
            )
            yield episode

    # ── Atom layer ───────────────────────────────────────────────────

    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Extract atoms by splitting markdown on H2/H3 headings."""
        ext = json.loads(episode.source_ext or "{}")
        filepath = episode.start_ref
        if not filepath or not os.path.exists(filepath):
            return

        try:
            content = Path(filepath).read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("AntigravityExtractor: failed to read %s: %s", filepath, e)
            return

        if len(content) < 50:
            return

        sections = _split_by_headings(content)
        art_type = ext.get("artifact_type", "other")
        filename = ext.get("filename", "")

        for heading, body, _line_num in sections:
            # Truncate very long sections
            answer_text = body[:4000]

            atom_type = _infer_atom_type(heading)

            # Quality heuristics
            quality = min(1.0, len(answer_text) / 2000)
            # Boost for implementation plans and walkthroughs
            if art_type in ("implementation_plan", "walkthrough"):
                quality = min(1.0, quality + 0.2)

            atom = Atom(
                episode_id=episode.episode_id,
                atom_type=atom_type,
                question=heading,
                answer=answer_text,
                intent="design" if art_type == "implementation_plan" else "howto",
                format="plain",
                stability=Stability.VERSIONED,
                quality_auto=quality,
                value_auto=0.5,
                source_quality=0.7,  # agent-generated content
                applicability=json.dumps({
                    "project": "antigravity",
                    "source_file": filename,
                }),
            )
            atom.compute_hash()
            yield atom

    # ── Evidence layer ───────────────────────────────────────────────

    def extract_evidence(self, atom: Atom, episode: Episode) -> Iterator[Evidence]:
        """Link atoms back to source files."""
        filepath = episode.start_ref
        excerpt = atom.answer[:200] if atom.answer else ""

        evidence = Evidence(
            atom_id=atom.atom_id,
            doc_id=episode.doc_id,
            span_ref=filepath,
            excerpt=excerpt,
            excerpt_hash=_sha256_short(excerpt),
            evidence_role="supports",
            weight=1.0,
        )
        yield evidence
