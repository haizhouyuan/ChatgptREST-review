"""Maint runbook extractor — generate runbook cards from shell/python scripts.

Extracts structured knowledge from maintenance scripts:
- Script purpose (from header comments)
- Parameters and configuration
- Error handling patterns
- Dependencies and prerequisites
"""

from __future__ import annotations

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
# Script parser
# ---------------------------------------------------------------------------

def parse_script_header(content: str, ext: str) -> dict:
    """Extract structured info from script header comments."""
    lines = content.split("\n")
    result = {
        "shebang": "",
        "purpose": "",
        "description": "",
        "why": "",
        "how": "",
        "params": [],
        "deps": [],
    }

    comment_char = "#" if ext in (".sh", ".py", ".bash") else "//"
    in_header = True
    header_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped.startswith("#!"):
            result["shebang"] = stripped
            continue
        if stripped.startswith(comment_char) or stripped == "":
            header_lines.append(stripped.lstrip(comment_char).strip())
        elif stripped.startswith("set ") or stripped.startswith("import "):
            continue
        else:
            break

    header_text = "\n".join(header_lines).strip()

    # Extract purpose (first non-empty header line)
    for line in header_lines:
        if line:
            result["purpose"] = line
            break

    result["description"] = header_text

    # Extract Why/How sections
    why_match = re.search(r"(?:Why|为什么)[:\s]*\n((?:\s*[-#]\s*.+\n?)+)", header_text, re.IGNORECASE)
    if why_match:
        result["why"] = why_match.group(1).strip()

    how_match = re.search(r"(?:How|如何|How it works)[:\s]*\n((?:\s*[-#]\s*.+\n?)+)", header_text, re.IGNORECASE)
    if how_match:
        result["how"] = how_match.group(1).strip()

    # Extract parameters/variables
    for line in lines:
        var_match = re.match(r'^(\w+)=["\'$]', line) or re.match(r'^(\w+)=\$\{', line)
        if var_match:
            result["params"].append(var_match.group(1))
        # Also detect argparse/click params in Python
        if "add_argument" in line or "@click" in line:
            arg_match = re.search(r'["\'](-+\w[\w-]*)["\']', line)
            if arg_match:
                result["params"].append(arg_match.group(1))

    # Extract dependencies
    for line in lines[:50]:
        if re.search(r"(require|command -v|which|dpkg|apt|pip install)", line, re.IGNORECASE):
            result["deps"].append(line.strip()[:100])

    return result


def extract_functions(content: str, ext: str) -> list[dict]:
    """Extract function definitions from scripts."""
    functions = []

    if ext == ".sh" or ext == ".bash":
        for m in re.finditer(r'^(\w+)\s*\(\)\s*\{', content, re.MULTILINE):
            name = m.group(1)
            start = m.start()
            # Get function comment (lines above)
            before = content[:start].rstrip().split("\n")
            comment = ""
            for line in reversed(before[-3:]):
                if line.strip().startswith("#"):
                    comment = line.strip().lstrip("# ") + " " + comment
            functions.append({"name": name, "comment": comment.strip(), "pos": start})

    elif ext == ".py":
        for m in re.finditer(r'^def (\w+)\([^)]*\):', content, re.MULTILINE):
            name = m.group(1)
            start = m.end()
            # Get docstring
            docstring = ""
            rest = content[start:start+500]
            ds_match = re.match(r'\s*"""(.+?)"""', rest, re.DOTALL)
            if ds_match:
                docstring = ds_match.group(1).strip()[:200]
            functions.append({"name": name, "comment": docstring, "pos": m.start()})

    return functions


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class MaintRunbookExtractor(BaseExtractor):
    """Extract runbook cards from maintenance scripts."""

    source_name = "maint"

    def __init__(self, db, maint_dirs: list[str], extensions: tuple = (".sh", ".py", ".bash", ".md")):
        super().__init__(db)
        self.maint_dirs = maint_dirs
        self.extensions = extensions

    def _find_scripts(self) -> list[str]:
        files = []
        for src_dir in self.maint_dirs:
            if not os.path.isdir(src_dir):
                continue
            for root, dirs, filenames in os.walk(src_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                depth = root[len(src_dir):].count(os.sep)
                if depth >= 5:
                    dirs.clear()
                    continue
                for fn in filenames:
                    if any(fn.endswith(e) for e in self.extensions):
                        files.append(os.path.join(root, fn))
        return files

    def extract_documents(self) -> Iterator[Document]:
        scripts = self._find_scripts()
        logger.info("Found %d maint scripts in %s", len(scripts), self.maint_dirs)

        for filepath in scripts:
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            if len(content) < 50:
                continue

            ext = Path(filepath).suffix
            content_hash = _hash_text(content)
            basename = Path(filepath).stem

            doc = Document(
                doc_id=f"doc_maint_{_hash_text(filepath)}",
                source="maint",
                project="infrastructure",
                raw_ref=filepath,
                title=basename,
                created_at=os.path.getmtime(filepath),
                hash=content_hash,
                meta_json=json.dumps({
                    "ext": ext,
                    "size": len(content),
                    "path": filepath,
                }),
            )
            doc._content = content
            doc._ext = ext
            yield doc

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        content = getattr(doc, "_content", "")
        ext = getattr(doc, "_ext", ".sh")

        if ext == ".md":
            # For markdown files, treat as single episode
            ep = Episode(
                episode_id=f"ep_maint_{doc.doc_id[-12:]}_0",
                doc_id=doc.doc_id,
                episode_type=EpisodeType.RUNBOOK.value,
                title=doc.title,
                summary=content[:300],
                source_ext=json.dumps({"type": "markdown"}),
            )
            ep._content = content
            ep._ext = ext
            yield ep
        else:
            # For scripts, episode is the whole script
            header = parse_script_header(content, ext)
            functions = extract_functions(content, ext)

            ep = Episode(
                episode_id=f"ep_maint_{doc.doc_id[-12:]}_0",
                doc_id=doc.doc_id,
                episode_type=EpisodeType.RUNBOOK.value,
                title=header["purpose"][:200] or doc.title,
                summary=header["description"][:500],
                source_ext=json.dumps({
                    "type": "script",
                    "ext": ext,
                    "shebang": header["shebang"],
                    "function_count": len(functions),
                    "param_count": len(header["params"]),
                }),
            )
            ep._content = content
            ep._ext = ext
            ep._header = header
            ep._functions = functions
            yield ep

    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Extract runbook atoms with Score Contract scoring."""
        content = getattr(episode, "_content", "")
        ext = getattr(episode, "_ext", "")
        header = getattr(episode, "_header", None)
        functions = getattr(episode, "_functions", [])

        src_quality = SOURCE_QUALITY.get("maint_runbook", 0.80)

        def _score_atom(question: str, answer: str, intent: str) -> ScoreComponents:
            sc = ScoreComponents(
                extractor="maint_runbook",
                structure_score=score_structure(answer),
                information_density=score_information_density(answer),
                completeness=score_completeness(answer, ideal_min=100, ideal_max=2000),
                specificity=score_specificity(question),
                evidence_quality=src_quality,
                doc_value=0.7,  # maint scripts are generally valuable
                type_prior=0.75,
                actionability=0.85 if intent in ("runbook", "howto") else 0.7,
                uniqueness=0.7,
            )
            sc.final_quality = compute_quality(sc)
            sc.final_value = compute_value(sc)
            return sc

        if ext == ".md":
            if len(content) > 100:
                sc = _score_atom(f"运维文档：{episode.title}", content[:2000], "runbook")
                yield Atom(
                    atom_id=f"at_{episode.episode_id[-16:]}_0",
                    episode_id=episode.episode_id,
                    atom_type=AtomType.PROCEDURE.value,
                    question=f"运维文档：{episode.title}",
                    answer=content[:2000],
                    canonical_question=episode.title.lower()[:200],
                    intent="runbook",
                    stability=Stability.VERSIONED.value,
                    status=AtomStatus.CANDIDATE.value,
                    quality_auto=sc.final_quality,
                    value_auto=sc.final_value,
                    source_quality=src_quality,
                    scores_json=sc.to_json(),
                )
            return

        if not header:
            return

        # Atom 1: What does this script do? (purpose card)
        if header["purpose"]:
            answer = f"**Purpose**: {header['purpose']}\n\n{header['description'][:1000]}"
            sc = _score_atom(f"{episode.title}脚本的作用是什么？", answer, "runbook")
            yield Atom(
                atom_id=f"at_{episode.episode_id[-16:]}_purpose",
                episode_id=episode.episode_id,
                atom_type=AtomType.PROCEDURE.value,
                question=f"{episode.title}脚本的作用是什么？",
                answer=answer,
                canonical_question=f"what does {episode.title} do",
                intent="runbook",
                stability=Stability.VERSIONED.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=sc.final_quality,
                value_auto=sc.final_value,
                source_quality=src_quality,
                scores_json=sc.to_json(),
            )

        # Atom 2: How to use (if params or how section exist)
        if header["how"] or header["params"]:
            params_str = ", ".join(header["params"][:10])
            answer = ""
            if header["how"]:
                answer += f"**How it works**:\n{header['how']}\n\n"
            if params_str:
                answer += f"**Parameters**: {params_str}\n"

            sc = _score_atom(f"如何使用{episode.title}？", answer[:2000], "howto")
            yield Atom(
                atom_id=f"at_{episode.episode_id[-16:]}_howto",
                episode_id=episode.episode_id,
                atom_type=AtomType.PROCEDURE.value,
                question=f"如何使用{episode.title}？",
                answer=answer[:2000],
                canonical_question=f"how to use {episode.title}",
                intent="howto",
                stability=Stability.VERSIONED.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=sc.final_quality,
                value_auto=sc.final_value,
                source_quality=src_quality,
                scores_json=sc.to_json(),
            )

        # Atom 3: Why does this exist? (if why section)
        if header["why"]:
            answer = f"**Rationale**:\n{header['why'][:1500]}"
            sc = _score_atom(f"为什么需要{episode.title}？", answer, "rationale")
            yield Atom(
                atom_id=f"at_{episode.episode_id[-16:]}_why",
                episode_id=episode.episode_id,
                atom_type=AtomType.DECISION.value,
                question=f"为什么需要{episode.title}？",
                answer=answer,
                canonical_question=f"why {episode.title}",
                intent="rationale",
                stability=Stability.VERSIONED.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=sc.final_quality,
                value_auto=sc.final_value,
                source_quality=src_quality,
                scores_json=sc.to_json(),
            )

    def extract_evidence(self, atom: Atom, episode: Episode) -> Iterator[Evidence]:
        excerpt = atom.answer[:200] if atom.answer else atom.question[:200]
        yield Evidence(
            evidence_id=f"ev_{atom.atom_id[:20]}",
            atom_id=atom.atom_id,
            doc_id=episode.doc_id,
            span_ref="full_script",
            excerpt=excerpt,
            excerpt_hash=_hash_text(excerpt),
            evidence_role="source",
            weight=1.0,
        )
