"""Note section extractor — process Markdown files into Document → Episode → Atom.

Handles: planning md, LifeOS Vault md, research md.
Strategy (from Pro consultation):
- Section-level extraction (H2/H3 subtree as minimum unit)
- Note triage: classify as evergreen/project/procedure/decision/journal/clipping
- Claim extraction: concept→"what is", procedure→"how to", tradeoff→"when to use"
- Per note max: 0-3 atoms + 1 summary + 0-2 entity relations
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
    AtomStatus,
    AtomType,
    Document,
    Episode,
    EpisodeType,
    Evidence,
    Stability,
    _hash_text,
    _new_id,
)
from chatgptrest.evomap.knowledge.scoring.contract import (
    SOURCE_QUALITY,
    ScoreComponents,
    compute_quality,
    compute_value,
    score_completeness,
    score_information_density,
    score_specificity,
    score_structure,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Note triage
# ---------------------------------------------------------------------------

def classify_note(title: str, content: str) -> str:
    """Classify a note into categories for prioritization."""
    title_lower = title.lower()
    content_lower = content[:500].lower()

    # Check for procedure/howto markers
    if any(kw in title_lower for kw in ["流程", "步骤", "操作", "procedure", "howto",
                                         "setup", "install", "配置", "部署"]):
        return "procedure"
    if any(kw in title_lower for kw in ["决策", "选型", "方案", "decision", "选择",
                                         "对比", "比较", "trade"]):
        return "decision"
    if any(kw in title_lower for kw in ["规划", "设计", "架构", "方案", "plan",
                                         "design", "spec", "rfc"]):
        return "project"
    if any(kw in title_lower for kw in ["日志", "日记", "记录", "log", "daily",
                                         "journal", "meeting", "会议"]):
        return "journal"
    if any(kw in title_lower for kw in ["摘录", "引用", "clip", "reference", "转载"]):
        return "clipping"

    # Content-based signals
    if re.search(r"(为什么|why|trade-?off|versus|vs\.?\s|优缺点)", content_lower):
        return "decision"
    if re.search(r"(步骤|step\s?\d|第[一二三四五六七八九十]步|1\.\s)", content_lower):
        return "procedure"
    if re.search(r"(原则|principle|概念|concept|定义|definition)", content_lower):
        return "evergreen"

    return "project"  # default


def estimate_note_value(title: str, content: str, note_type: str) -> float:
    """Estimate note value (0.0-1.0) based on cheap features."""
    score = 0.5

    # Type-based baseline
    type_scores = {
        "evergreen": 0.2, "project": 0.15, "procedure": 0.15,
        "decision": 0.15, "journal": -0.15, "clipping": -0.2,
    }
    score += type_scores.get(note_type, 0)

    # Content signals
    content_lower = content.lower()
    if len(content) > 1000:
        score += 0.05
    if len(content) > 3000:
        score += 0.05

    # Heading structure = well-organized
    headings = len(re.findall(r'^#{1,4}\s', content, re.MULTILINE))
    if headings >= 3:
        score += 0.1

    # Actionable keywords
    if re.search(r"(避免|avoid|注意|warning|坑|pitfall|陷阱)", content_lower):
        score += 0.1
    if re.search(r"(建议|recommend|最佳实践|best practice)", content_lower):
        score += 0.05

    # Code blocks = technical content
    code_blocks = len(re.findall(r'```', content))
    if code_blocks >= 2:
        score += 0.1

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Section splitter
# ---------------------------------------------------------------------------

def split_sections(content: str) -> list[dict]:
    """Split markdown content into sections by H2/H3 headings.

    Returns list of {title, level, content, start_line, end_line}.

    Fix (Gemini DeepThink review): tracks code block state to avoid
    misidentifying # comments inside ``` blocks as headings.
    """
    lines = content.split("\n")
    sections = []
    current = None
    in_code_block = False

    for i, line in enumerate(lines):
        # Track fenced code blocks (``` or ~~~)
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        # Skip heading detection inside code blocks
        if in_code_block:
            continue

        m = re.match(r'^(#{1,3})\s+(.+)', line)
        if m:
            if current:
                current["end_line"] = i - 1
                current["content"] = "\n".join(lines[current["start_line"]:i]).strip()
                if current["content"]:
                    sections.append(current)
            current = {
                "title": m.group(2).strip(),
                "level": len(m.group(1)),
                "start_line": i,
                "end_line": len(lines) - 1,
                "content": "",
            }
        elif current is None and line.strip():
            # Content before first heading
            current = {
                "title": "(intro)",
                "level": 0,
                "start_line": 0,
                "end_line": len(lines) - 1,
                "content": "",
            }

    if current:
        current["end_line"] = len(lines) - 1
        current["content"] = "\n".join(lines[current["start_line"]:]).strip()
        if current["content"]:
            sections.append(current)

    # If no sections found, treat entire content as one section
    if not sections and content.strip():
        sections.append({
            "title": "(full document)",
            "level": 0,
            "start_line": 0,
            "end_line": len(lines) - 1,
            "content": content.strip(),
        })

    return sections


# ---------------------------------------------------------------------------
# Question generation from sections
# ---------------------------------------------------------------------------

def generate_questions(title: str, content: str, note_type: str) -> list[dict]:
    """Generate QA pairs from a section using template rules.

    Returns list of {question, answer, atom_type, intent}.
    """
    results = []
    content_lower = content.lower()
    title_clean = title.strip("# ").strip()

    if not title_clean or title_clean == "(intro)" or len(content.strip()) < 50:
        return results

    # Max 3 atoms per section (Pro recommendation)
    max_atoms = 3

    # Rule 1: Concept/definition → "What is"
    if note_type in ("evergreen", "project") or re.search(
        r"(概念|定义|是什么|原理|definition|concept|overview)", content_lower
    ):
        results.append({
            "question": f"{title_clean}是什么？",
            "answer": content[:2000],
            "atom_type": AtomType.QA.value,
            "intent": "concept",
        })

    # Rule 2: Procedure/steps → "How to"
    if note_type == "procedure" or re.search(
        r"(步骤|step|流程|操作方法|如何|how to|setup|配置)", content_lower
    ):
        results.append({
            "question": f"如何{title_clean}？",
            "answer": content[:2000],
            "atom_type": AtomType.PROCEDURE.value,
            "intent": "howto",
        })

    # Rule 3: Decision/tradeoff → "When to use"
    if note_type == "decision" or re.search(
        r"(为什么|why|选型|对比|trade|versus|优缺点|适用|when to)", content_lower
    ):
        results.append({
            "question": f"关于{title_clean}的决策/对比分析？",
            "answer": content[:2000],
            "atom_type": AtomType.DECISION.value,
            "intent": "compare",
        })

    # Rule 4: Pitfall/warning → troubleshooting
    if re.search(r"(坑|pitfall|注意|warning|避免|avoid|问题|trouble|error|bug)", content_lower):
        results.append({
            "question": f"{title_clean}有哪些常见问题/注意事项？",
            "answer": content[:2000],
            "atom_type": AtomType.TROUBLESHOOTING.value,
            "intent": "debug",
        })

    # Rule 5: Lesson/summary → lesson
    if re.search(r"(总结|summary|经验|lesson|回顾|review|复盘|反思|教训)", content_lower):
        results.append({
            "question": f"{title_clean}的关键经验教训？",
            "answer": content[:2000],
            "atom_type": AtomType.LESSON.value,
            "intent": "fact",
        })

    # Fallback: if no rules matched but content is substantial, create a generic QA
    if not results and len(content) > 200:
        results.append({
            "question": f"{title_clean}",
            "answer": content[:2000],
            "atom_type": AtomType.QA.value,
            "intent": "fact",
        })

    return results[:max_atoms]


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class NoteSectionExtractor(BaseExtractor):
    """Extract knowledge from Markdown files using section-level analysis."""

    source_name = "markdown"

    def __init__(self, db, source_dirs: list[str], source_label: str = "md",
                 max_depth: int = 10, min_content_len: int = 100):
        super().__init__(db)
        self.source_dirs = source_dirs
        self.source_label = source_label
        self.max_depth = max_depth
        self.min_content_len = min_content_len

    def _find_md_files(self) -> list[str]:
        """Find all .md files in source directories."""
        files = []
        for src_dir in self.source_dirs:
            if not os.path.isdir(src_dir):
                logger.warning("Source dir not found: %s", src_dir)
                continue
            for root, dirs, filenames in os.walk(src_dir):
                # Respect max depth
                depth = root[len(src_dir):].count(os.sep)
                if depth >= self.max_depth:
                    dirs.clear()
                    continue
                # Skip hidden/git dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in filenames:
                    if fn.endswith(".md") and not fn.startswith("."):
                        files.append(os.path.join(root, fn))
        return files

    def extract_documents(self) -> Iterator[Document]:
        """Each markdown file becomes a Document."""
        md_files = self._find_md_files()
        logger.info("Found %d markdown files in %s", len(md_files), self.source_dirs)

        for filepath in md_files:
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError) as e:
                logger.debug("Skip unreadable: %s (%s)", filepath, e)
                continue

            if len(content) < self.min_content_len:
                continue

            # Extract title from first heading or filename
            title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else Path(filepath).stem

            content_hash = _hash_text(content)
            note_type = classify_note(title, content)
            value = estimate_note_value(title, content, note_type)

            # Skip low-value notes (journals, clippings, very short)
            if value < 0.3:
                continue

            doc = Document(
                doc_id=f"doc_{self.source_label}_{_hash_text(filepath)}",
                source=self.source_label,
                project=self._detect_project(filepath),
                raw_ref=filepath,
                title=title[:200],
                created_at=os.path.getmtime(filepath),
                hash=content_hash,
                meta_json=json.dumps({
                    "note_type": note_type,
                    "value_estimate": value,
                    "file_size": len(content),
                    "path": filepath,
                }),
            )
            doc._content = content  # type: ignore
            doc._note_type = note_type  # type: ignore
            doc._value = value  # type: ignore
            yield doc

    def _detect_project(self, filepath: str) -> str:
        """Detect project from file path."""
        for label, pattern in [
            ("planning", "projects/planning"),
            ("research", "projects/research"),
            ("lifeos", "LifeOS"),
            ("maint", "maint"),
        ]:
            if pattern in filepath:
                return label
        return "unknown"




    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Generate question-answer atoms from section content.

        Fix (Pro review L546-573): adds quality_auto/value_auto scoring
        using unified Score Contract instead of leaving them at 0.
        """
        content = getattr(episode, "_content", "")
        title = getattr(episode, "_title", "")
        note_type = getattr(episode, "_note_type", "project")
        doc_value = getattr(episode, "_doc_value", 0.5)

        qa_pairs = generate_questions(title, content, note_type)

        # Actionability prior based on note type
        type_actionability = {
            "procedure": 0.9, "decision": 0.8, "troubleshooting": 0.8,
            "evergreen": 0.6, "project": 0.5, "journal": 0.3, "clipping": 0.2,
        }
        type_prior = {
            "procedure": 0.8, "decision": 0.8, "troubleshooting": 0.7,
            "evergreen": 0.7, "project": 0.5, "journal": 0.3, "clipping": 0.2,
        }

        for j, qa in enumerate(qa_pairs):
            # Build score components (traceable)
            sc = ScoreComponents(
                extractor="note_section",
                structure_score=score_structure(qa["answer"]),
                information_density=score_information_density(qa["answer"]),
                completeness=score_completeness(qa["answer"]),
                specificity=score_specificity(qa["question"]),
                evidence_quality=0.5,  # markdown = medium grounding
                doc_value=doc_value,
                type_prior=type_prior.get(note_type, 0.5),
                actionability=type_actionability.get(note_type, 0.5),
                uniqueness=0.6,  # TODO: compute from dedup check
            )
            sc.final_quality = compute_quality(sc)
            sc.final_value = compute_value(sc)

            atom = Atom(
                atom_id=f"at_{episode.episode_id[-16:]}_{j}",
                episode_id=episode.episode_id,
                atom_type=qa["atom_type"],
                question=qa["question"],
                answer=qa["answer"],
                canonical_question=qa["question"].strip().lower()[:200],
                intent=qa["intent"],
                applicability=json.dumps({"source": self.source_label}),
                stability=Stability.VERSIONED.value,
                status=AtomStatus.CANDIDATE.value,
                valid_from=episode.time_start,
                quality_auto=sc.final_quality,
                value_auto=sc.final_value,
                source_quality=SOURCE_QUALITY.get("note_section", 0.6),
                scores_json=sc.to_json(),
            )
            yield atom

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        """Each section becomes an Episode.

        Fix: propagate doc._value to episode for downstream scoring.
        """
        content = getattr(doc, "_content", "")
        note_type = getattr(doc, "_note_type", "project")
        doc_value = getattr(doc, "_value", 0.5)

        sections = split_sections(content)

        for i, sec in enumerate(sections):
            if len(sec["content"]) < 50:
                continue

            ep = Episode(
                episode_id=f"ep_sec_{doc.doc_id[-12:]}_{i}",
                doc_id=doc.doc_id,
                episode_type=EpisodeType.MD_SECTION.value,
                title=sec["title"][:200],
                summary=sec["content"][:300],
                start_ref=f"L{sec['start_line']+1}",
                end_ref=f"L{sec['end_line']+1}",
                time_start=doc.created_at,
                source_ext=json.dumps({
                    "section_index": i,
                    "heading_level": sec["level"],
                    "note_type": note_type,
                    "char_count": len(sec["content"]),
                }),
            )
            ep._content = sec["content"]  # type: ignore
            ep._title = sec["title"]  # type: ignore
            ep._note_type = note_type  # type: ignore
            ep._doc_value = doc_value  # type: ignore  # propagate for scoring
            yield ep

    def extract_evidence(self, atom: Atom, episode: Episode) -> Iterator[Evidence]:
        """Link atom to source file location.

        Fix (Pro L516-531): use actual answer excerpt for grounding,
        not just the question text.
        """
        # Use first 200 chars of answer as excerpt (real supporting text)
        excerpt = atom.answer[:200] if atom.answer else atom.question[:200]
        yield Evidence(
            evidence_id=f"ev_{atom.atom_id[:20]}",
            atom_id=atom.atom_id,
            doc_id=episode.doc_id,
            span_ref=f"{episode.start_ref}-{episode.end_ref}",
            excerpt=excerpt,
            excerpt_hash=_hash_text(excerpt),
            evidence_role="source",
            weight=1.0,
        )
