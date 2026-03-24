#!/usr/bin/env python3
"""extract_qa.py — 从 planning 仓库全量抽取 Q&A 对.

扫描 /vol1/1000/projects/planning 下的 14 个业务/技术域，
将每份实质工作还原为结构化的 Q&A 对，输出 JSONL。

用法:
    python extract_qa.py                    # 全量抽取
    python extract_qa.py --domain 两轮车车身业务  # 只抽指定域
    python extract_qa.py --incremental       # 增量模式

输出: planning_qa_all.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PLANNING_ROOT = Path("/vol1/1000/projects/planning")
OUTPUT_DIR = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa")

# Domain mapping: directory name → human-readable domain label
DOMAIN_MAP: dict[str, str] = {
    "aios":           "AIOS架构",
    "docs":           "工具链与文档",
    "两轮车车身业务":   "两轮车车身业务",
    "机器人代工业务规划": "机器人代工业务",
    "减速器开发":      "减速器开发",
    "预算":           "预算与财务",
    "人员与绩效":      "人员与绩效",
    "十五五规划":      "十五五规划",
    "业务PPT":        "业务演示",
    "受控资料":        "受控资料",
    "外来文件管理":    "外来文件管理",
    "00_入口":        "入口与索引",
    "_kb":            "KB知识底座",
    "multi_agent_review_kb": "多Agent评审KB",
    "scripts":        "脚本工具",
    "templates":      "模板",
}

# Skip patterns
SKIP_DIRS = {".git", ".venv", ".venv_occt", ".venv_openpyxl", ".venv_sim",
             "__pycache__", ".pytest_cache", ".specstory", ".vscode",
             ".openclaw-skill-lab", "node_modules"}
SKIP_EXTENSIONS = {".zip", ".pdf", ".xlsx", ".xls", ".docx", ".pptx",
                    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                    ".pyc", ".db", ".sqlite", ".sqlite3", ".bin",
                    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4",
                    ".wav", ".webm", ".webp"}
# Files too small to be meaningful Q&A
MIN_FILE_SIZE = 200  # bytes
# Files too large to be a single Q&A (will be chunked)
MAX_SINGLE_QA_SIZE = 500_000  # 500KB


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------
@dataclass
class QARecord:
    """A single Q&A pair extracted from planning work."""
    qa_id: str = ""
    domain: str = ""
    source_file: str = ""           # Relative to PLANNING_ROOT
    source_type: str = ""           # "conversational" | "research_report" | "plan_document" | "tool_script" | "index"
    question: str = ""
    answer_summary: str = ""        # ≤ 2000 chars
    answer_full_path: str = ""      # Absolute path to full answer

    # Auto scores (populated by auto_score.py later)
    scores_auto: dict[str, float] = field(default_factory=dict)
    route_auto: str = ""
    rubric_auto: dict[str, float] = field(default_factory=dict)

    # Human scores (populated by human)
    scores_human: dict[str, Any] = field(default_factory=lambda: {
        "clarity": None, "feasibility": None, "evidence": None,
        "risk": None, "alignment": None, "completeness": None,
        "overall": None, "comment": "",
    })
    human_scorer: str = ""
    human_scored_at: str | None = None
    status: str = "pending_extraction"  # pending_extraction → extracted → auto_scored → pending_human_review → scored → approved

    extracted_at: str = ""
    file_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _make_qa_id(domain: str, source_file: str, index: int = 0) -> str:
    """Generate deterministic Q&A ID."""
    raw = f"{domain}:{source_file}:{index}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"pqa_{short_hash}"


# ---------------------------------------------------------------------------
# Content Extractors
# ---------------------------------------------------------------------------

def _read_text_safe(path: Path, max_bytes: int = 2_000_000) -> str:
    """Read file as text, handling encoding issues."""
    try:
        content = path.read_bytes()[:max_bytes]
        for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                return content.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return content.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _summarize(text: str, max_len: int = 2000) -> str:
    """Create a summary by taking the first max_len chars of meaningful content."""
    # Strip markdown headers and blank lines for density
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    summary = "\n".join(lines)
    if len(summary) > max_len:
        summary = summary[:max_len] + "…"
    return summary


def _extract_title(text: str, filename: str) -> str:
    """Extract title from markdown or filename."""
    # Look for # heading
    for line in text.split("\n")[:20]:
        line = line.strip()
        if line.startswith("# ") and len(line) > 3:
            return line[2:].strip()
    # Look for title in frontmatter
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fall back to filename
    return Path(filename).stem


def _infer_question_from_title(title: str, domain: str) -> str:
    """Convert a document title into a question form."""
    # Already a question?
    if title.endswith("？") or title.endswith("?"):
        return title
    # Common patterns
    if "调研" in title or "研究" in title:
        return f"关于「{title}」的调研结论是什么？"
    if "规划" in title or "计划" in title:
        return f"「{title}」的要点是什么？"
    if "方案" in title or "设计" in title:
        return f"「{title}」如何设计与实施？"
    if "报告" in title or "总结" in title:
        return f"「{title}」的核心结论是什么？"
    if "评审" in title or "复审" in title:
        return f"「{title}」发现了哪些问题和建议？"
    return f"关于「{title}」，具体内容和结论是什么？"


def extract_conversational(path: Path, domain: str, rel_path: str) -> list[QARecord]:
    """Extract Q&A pairs from conversational files (markdown with --- separators)."""
    text = _read_text_safe(path)
    if not text:
        return []

    records: list[QARecord] = []

    # Pattern: sections separated by --- where user asks and AI responds
    sections = re.split(r'\n---+\n', text)

    if len(sections) < 3:
        # Not clearly conversational, treat as single document
        return extract_document(path, domain, rel_path)

    # Pair up: odd sections tend to be user input, even sections AI response
    # But real pattern is alternating user/AI
    qa_pairs: list[tuple[str, str]] = []
    current_q = ""
    current_a = ""

    for i, section in enumerate(sections):
        section = section.strip()
        if not section or len(section) < 20:
            continue

        # Heuristic: user messages are usually shorter and contain questions/instructions
        # AI responses are longer and more structured
        is_user_like = (
            len(section) < 500
            or section.startswith("1.")
            or section.startswith("1\\.")
            or "请" in section[:50]
            or "确认" in section[:100]
            or "我" in section[:30]
            or "没有" in section[:50]
        )
        # But also check if it's clearly an AI response
        is_ai_like = (
            len(section) > 1000
            or "## " in section[:200]
            or "| " in section[:500]  # tables
            or "```" in section
        )

        if is_user_like and not is_ai_like:
            if current_q and current_a:
                qa_pairs.append((current_q, current_a))
            current_q = section
            current_a = ""
        else:
            current_a += "\n\n" + section if current_a else section

    if current_q and current_a:
        qa_pairs.append((current_q, current_a))

    for idx, (q, a) in enumerate(qa_pairs):
        if len(q.strip()) < 10 or len(a.strip()) < 50:
            continue
        records.append(QARecord(
            qa_id=_make_qa_id(domain, rel_path, idx),
            domain=domain,
            source_file=rel_path,
            source_type="conversational",
            question=q.strip()[:500],
            answer_summary=_summarize(a),
            answer_full_path=str(path),
            status="extracted",
            extracted_at=datetime.now(timezone.utc).isoformat(),
            file_size_bytes=path.stat().st_size,
        ))

    return records


def extract_document(path: Path, domain: str, rel_path: str) -> list[QARecord]:
    """Extract Q&A from a single document (report, plan, etc.)."""
    text = _read_text_safe(path)
    if not text or len(text.strip()) < MIN_FILE_SIZE:
        return []

    title = _extract_title(text, rel_path)
    question = _infer_question_from_title(title, domain)

    # Determine source type
    name_lower = rel_path.lower()
    if "调研" in name_lower or "research" in name_lower:
        source_type = "research_report"
    elif "规划" in name_lower or "计划" in name_lower or "plan" in name_lower:
        source_type = "plan_document"
    elif "评审" in name_lower or "review" in name_lower or "复审" in name_lower:
        source_type = "review_document"
    elif "索引" in name_lower or "入口" in name_lower or "index" in name_lower:
        source_type = "index"
    elif name_lower.endswith(".py") or name_lower.endswith(".sh"):
        source_type = "tool_script"
    else:
        source_type = "plan_document"

    return [QARecord(
        qa_id=_make_qa_id(domain, rel_path, 0),
        domain=domain,
        source_file=rel_path,
        source_type=source_type,
        question=question,
        answer_summary=_summarize(text),
        answer_full_path=str(path),
        status="extracted",
        extracted_at=datetime.now(timezone.utc).isoformat(),
        file_size_bytes=path.stat().st_size,
    )]


def extract_jsonl(path: Path, domain: str, rel_path: str) -> list[QARecord]:
    """Extract Q&A from JSONL files (conversation logs)."""
    records: list[QARecord] = []
    try:
        lines = path.read_text("utf-8", errors="replace").strip().split("\n")
    except Exception:
        return []

    qa_pairs: list[tuple[str, str]] = []
    current_q = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = obj.get("role", "")
        content = obj.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )

        if role in ("user", "human"):
            if current_q and len(qa_pairs) > 0 and qa_pairs[-1][1]:
                pass  # already paired
            current_q = content
        elif role in ("assistant", "ai") and current_q:
            qa_pairs.append((current_q, content))
            current_q = ""

    for idx, (q, a) in enumerate(qa_pairs):
        if len(q.strip()) < 10 or len(a.strip()) < 50:
            continue
        records.append(QARecord(
            qa_id=_make_qa_id(domain, rel_path, idx),
            domain=domain,
            source_file=rel_path,
            source_type="conversational",
            question=q.strip()[:500],
            answer_summary=_summarize(a),
            answer_full_path=str(path),
            status="extracted",
            extracted_at=datetime.now(timezone.utc).isoformat(),
            file_size_bytes=path.stat().st_size,
        ))

    return records


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _should_skip(path: Path) -> bool:
    """Check if file should be skipped."""
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    try:
        size = path.stat().st_size
    except (FileNotFoundError, OSError):
        return True  # broken symlink or inaccessible
    if size < MIN_FILE_SIZE:
        return True
    # Skip binary-looking files
    if path.suffix.lower() in (".csv", ".tsv") and size > 1_000_000:
        return True  # Large data files, not Q&A
    return False


def _detect_conversational(text: str) -> bool:
    """Heuristic: is this file conversational (alternating user/AI)?"""
    separators = text.count("\n---\n") + text.count("\n---\n\n")
    if separators >= 4:
        return True
    return False


def scan_domain(domain_dir: str, domain_label: str) -> list[QARecord]:
    """Scan a single domain directory for Q&A pairs."""
    root = PLANNING_ROOT / domain_dir
    if not root.exists():
        return []

    records: list[QARecord] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            rel_path = str(fpath.relative_to(PLANNING_ROOT))

            if _should_skip(fpath):
                continue

            suffix = fpath.suffix.lower()

            if suffix == ".jsonl":
                extracted = extract_jsonl(fpath, domain_label, rel_path)
            elif suffix in (".md", ".txt"):
                # Check if conversational
                text = _read_text_safe(fpath, max_bytes=50_000)
                if _detect_conversational(text):
                    extracted = extract_conversational(fpath, domain_label, rel_path)
                else:
                    extracted = extract_document(fpath, domain_label, rel_path)
            elif suffix in (".py", ".sh"):
                extracted = extract_document(fpath, domain_label, rel_path)
            elif suffix == ".json":
                # JSON files — treat as documents if they have content
                extracted = extract_document(fpath, domain_label, rel_path)
            else:
                continue

            records.extend(extracted)

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract Q&A pairs from planning repo")
    parser.add_argument("--domain", type=str, default="",
                        help="Only extract from this domain (directory name)")
    parser.add_argument("--incremental", action="store_true",
                        help="Only extract files not already in output")
    parser.add_argument("--output", type=str, default="",
                        help="Output file path (default: planning_qa_all.jsonl)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT_DIR / "planning_qa_all.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing records for incremental mode
    existing_ids: set[str] = set()
    if args.incremental and output_path.exists():
        for line in output_path.read_text().strip().split("\n"):
            if line.strip():
                try:
                    rec = json.loads(line)
                    existing_ids.add(rec.get("qa_id", ""))
                except json.JSONDecodeError:
                    pass

    # Determine which domains to scan
    if args.domain:
        domains = {args.domain: DOMAIN_MAP.get(args.domain, args.domain)}
    else:
        domains = DOMAIN_MAP.copy()
        # Also scan top-level files
        domains[""] = "仓库根目录"

    all_records: list[QARecord] = []
    domain_stats: dict[str, int] = {}

    for domain_dir, domain_label in sorted(domains.items()):
        if domain_dir == "":
            # Scan top-level markdown files
            for f in sorted(PLANNING_ROOT.iterdir()):
                if f.is_file() and f.suffix.lower() in (".md",) and f.stat().st_size >= MIN_FILE_SIZE:
                    rel = f.name
                    recs = extract_document(f, domain_label, rel)
                    for r in recs:
                        if r.qa_id not in existing_ids:
                            all_records.append(r)
        else:
            recs = scan_domain(domain_dir, domain_label)
            for r in recs:
                if r.qa_id not in existing_ids:
                    all_records.append(r)
            domain_stats[domain_label] = len(recs)

    # Write output
    mode = "a" if args.incremental else "w"
    with open(output_path, mode, encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Q&A Extraction Complete")
    print(f"{'='*60}")
    print(f"Total Q&A pairs extracted: {len(all_records)}")
    print(f"Output: {output_path}")
    print(f"\nPer-domain breakdown:")
    for domain, count in sorted(domain_stats.items(), key=lambda x: -x[1]):
        print(f"  {domain:24s} {count:4d}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
