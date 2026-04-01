"""KD0 commit scorer + extractor — rule-based knowledge-density scoring.

Strategy from LLM consultation:
- KD0 (rule-based): message patterns, diff stats, path signals
- Score formula: sigmoid(linear_combo * (1 - penalty))
- High-KD commits → extract as COMMIT_CLUSTER episodes → QA atoms

Scoring signals:
- Hard negatives: bump version, merge branch, typo fix, WIP
- Strong positives: fix(reason), refactor, design decision, architecture
- Diff features: path signals, size/shape, content proxies
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
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
# KD0 scoring rules
# ---------------------------------------------------------------------------

# Hard negatives — instantly low score
HARD_NEGATIVES = [
    (r"^bump\s+version", -0.8),
    (r"^(merge|Merge)\s+(branch|pull)", -0.8),
    (r"^(chore|ci|release|deps?)[\(:]", -0.5),
    (r"^(wip|WIP|fixup|squash|temp|tmp)\b", -0.6),
    (r"^(typo|whitespace|format|lint|style)\b", -0.5),
    (r"^\d+\.\d+\.\d+", -0.7),  # version number commits
    (r"^Initial commit", -0.3),
    (r"^Update \w+\.(md|txt|yml|yaml|json)$", -0.3),
]

# Strong positives — knowledge-rich signals
STRONG_POSITIVES = [
    (r"fix\(.+\):", 0.3),  # conventional commit with scope + reason
    (r"(refactor|redesign|rearchitect)", 0.3),
    (r"(因为|because|since|由于|根因|root cause)", 0.25),
    (r"(设计|design|architecture|方案|approach)", 0.2),
    (r"(解决|solve|fix|repair|resolve)\s+.{10,}", 0.2),
    (r"(为什么|why|rationale|trade-?off)", 0.25),
    (r"(重构|migration|迁移|升级|upgrade)", 0.2),
    (r"(implement|实现|新增|add)\s+.{15,}", 0.15),
    (r"(feat|feature)\(.+\):", 0.15),
]


def score_message(msg: str) -> float:
    """Score commit message text (0.0-1.0)."""
    score = 0.5  # baseline
    msg_lower = msg.lower()

    for pattern, weight in HARD_NEGATIVES:
        if re.search(pattern, msg, re.IGNORECASE):
            score += weight

    for pattern, weight in STRONG_POSITIVES:
        if re.search(pattern, msg, re.IGNORECASE):
            score += weight

    # Length bonus: longer messages = more explanation
    words = len(msg.split())
    if words > 20:
        score += 0.1
    if words > 50:
        score += 0.1

    # Multi-line bonus: body with explanation
    if "\n\n" in msg:
        score += 0.15

    return max(0.0, min(1.0, score))


def score_diff_stats(stats: dict) -> float:
    """Score based on diff statistics."""
    score = 0.5

    files = stats.get("files_changed", 0)
    insertions = stats.get("insertions", 0)
    deletions = stats.get("deletions", 0)

    # Very small changes are usually trivial
    total_lines = insertions + deletions
    if total_lines < 5:
        score -= 0.2
    elif total_lines > 50:
        score += 0.1

    # Balanced changes (refactoring signal)
    if insertions > 0 and deletions > 0:
        ratio = min(insertions, deletions) / max(insertions, deletions)
        if ratio > 0.3:
            score += 0.1  # balanced = likely refactor

    # Too many files = probably automated
    if files > 20:
        score -= 0.2

    # Path signals
    paths = stats.get("paths", [])
    for p in paths:
        p_lower = p.lower()
        # Test files = good coverage
        if "test" in p_lower:
            score += 0.05
        # Docs = knowledge
        if p_lower.endswith((".md", ".rst", ".txt")):
            score += 0.05
        # Config-only changes = usually low value
        if p_lower.endswith((".json", ".yml", ".yaml", ".toml")) and files <= 2:
            score -= 0.1
        # Core source files
        if p_lower.endswith((".py", ".ts", ".js", ".go", ".rs")):
            score += 0.03

    return max(0.0, min(1.0, score))


def kd0_score(msg: str, diff_stats: dict) -> float:
    """Combined KD0 score: sigmoid(msg_score * 0.6 + diff_score * 0.4)."""
    msg_s = score_message(msg)
    diff_s = score_diff_stats(diff_stats)

    raw = msg_s * 0.6 + diff_s * 0.4

    # Sigmoid mapping to [0,1]
    import math
    centered = (raw - 0.5) * 6  # scale to [-3, 3]
    return 1.0 / (1.0 + math.exp(-centered))


# ---------------------------------------------------------------------------
# Git log parser
# ---------------------------------------------------------------------------

def get_commits(repo_path: str, max_count: int = 500) -> list[dict]:
    """Get recent commits with stats from a git repo.

    Fix (Pro L652-661, Gemini L108-110): uses NUL separator for safe
    parsing instead of custom delimiter + hardcoded cursor.
    Now captures full body (%B) and ISO date (%aI).
    """
    commits = []
    try:
        # NUL-separated format: sha\0body\0author\0date\0
        # Each record ends with \0\0 (double NUL from trailing separator)
        result = subprocess.run(
            ["git", "log", f"--max-count={max_count}",
             "--format=%H%x00%B%x00%an%x00%aI%x00",
             "--shortstat"],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return commits
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return commits

    raw = result.stdout
    # Split on the sha pattern (40-char hex followed by NUL)
    # Each commit block: sha\0body\0author\0date\0\n shortstat\n\n
    # Split by double-NUL + optional whitespace to separate records
    records = re.split(r'\x00\s*(?=[0-9a-f]{40}\x00)', raw)

    for record in records:
        record = record.strip()
        if not record:
            continue

        parts = record.split('\x00')
        if len(parts) < 4:
            continue

        sha = parts[0].strip()
        if len(sha) != 40 or not all(c in '0123456789abcdef' for c in sha):
            continue

        body = parts[1].strip()
        author = parts[2].strip()
        date_str = parts[3].strip()

        # Subject = first line of body
        subject = body.split('\n')[0].strip() if body else ""

        # Parse shortstat from remaining text after date field
        stats = {"files_changed": 0, "insertions": 0, "deletions": 0, "paths": []}
        rest = '\x00'.join(parts[4:]) if len(parts) > 4 else ""
        m = re.search(r'(\d+) files? changed', rest)
        if m:
            stats["files_changed"] = int(m.group(1))
        m = re.search(r'(\d+) insertions?', rest)
        if m:
            stats["insertions"] = int(m.group(1))
        m = re.search(r'(\d+) deletions?', rest)
        if m:
            stats["deletions"] = int(m.group(1))

        # Parse ISO date to epoch
        timestamp = 0.0
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(date_str)
            timestamp = dt.timestamp()
        except Exception:
            pass

        commits.append({
            "sha": sha, "subject": subject, "body": body,
            "date": date_str, "author": author,
            "message": body,  # full body for scoring
            "diff_stats": stats, "timestamp": timestamp,
        })

    return commits


def get_diff_paths(repo_path: str, sha: str) -> list[str]:
    """Get file paths changed in a commit."""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class CommitKD0Extractor(BaseExtractor):
    """Extract knowledge-worthy commits using KD0 scoring."""

    source_name = "commits"

    def __init__(self, db, repo_paths: list[str], kd0_threshold: float = 0.55,
                 max_commits_per_repo: int = 300):
        super().__init__(db)
        self.repo_paths = repo_paths
        self.kd0_threshold = kd0_threshold
        self.max_commits = max_commits_per_repo

    def extract_documents(self) -> Iterator[Document]:
        """Each repo becomes a Document."""
        for repo_path in self.repo_paths:
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                continue

            repo_name = os.path.basename(repo_path)
            commits = get_commits(repo_path, max_count=self.max_commits)

            if not commits:
                continue

            # Score all commits
            scored = []
            for c in commits:
                # Get file paths for diff scoring
                paths = get_diff_paths(repo_path, c["sha"])
                c["diff_stats"]["paths"] = paths
                c["kd0"] = kd0_score(c["message"], c["diff_stats"])
                scored.append(c)

            # Filter by threshold
            worthy = [c for c in scored if c["kd0"] >= self.kd0_threshold]

            if not worthy:
                continue

            content_hash = _hash_text(f"{repo_name}|{len(worthy)}|{worthy[0]['sha']}")
            doc = Document(
                doc_id=f"doc_commits_{_hash_text(repo_path)}",
                source="commits",
                project=repo_name,
                raw_ref=repo_path,
                title=f"{repo_name} knowledge commits",
                created_at=os.path.getmtime(repo_path),
                hash=content_hash,
                meta_json=json.dumps({
                    "repo": repo_name,
                    "total_commits": len(scored),
                    "worthy_commits": len(worthy),
                    "threshold": self.kd0_threshold,
                }),
            )
            doc._worthy = worthy
            doc._repo_name = repo_name
            yield doc

    def extract_episodes(self, doc: Document) -> Iterator[Episode]:
        """Each high-KD commit becomes an Episode.

        Fix: fills time_start from parsed commit date, propagates repo_name.
        """
        worthy = getattr(doc, "_worthy", [])
        repo_name = getattr(doc, "_repo_name", "")

        for i, commit in enumerate(worthy):
            ep = Episode(
                episode_id=f"ep_commit_{commit['sha'][:16]}",
                doc_id=doc.doc_id,
                episode_type=EpisodeType.COMMIT_CLUSTER.value,
                title=commit["subject"][:200],
                summary=commit["message"][:500],
                start_ref=commit["sha"],
                end_ref=commit["sha"],
                time_start=commit.get("timestamp", 0),
                source_ext=json.dumps({
                    "sha": commit["sha"],
                    "author": commit["author"],
                    "date": commit["date"],
                    "kd0_score": round(commit["kd0"], 3),
                    "files_changed": commit["diff_stats"]["files_changed"],
                    "insertions": commit["diff_stats"]["insertions"],
                    "deletions": commit["diff_stats"]["deletions"],
                    "repo": repo_name,
                }),
            )
            ep._commit = commit
            ep._repo_name = repo_name
            yield ep

    def extract_atoms(self, episode: Episode) -> Iterator[Atom]:
        """Each commit → 1 QA atom with Score Contract scoring."""
        commit = getattr(episode, "_commit", None)
        repo_name = getattr(episode, "_repo_name", "")
        if not commit:
            return

        subject = commit["subject"]
        message = commit["message"]
        kd0 = commit["kd0"]
        paths = commit["diff_stats"].get("paths", [])
        paths_str = ", ".join(paths[:5])

        # Determine atom type from commit message patterns
        atom_type = AtomType.QA.value
        msg_lower = message.lower()
        if re.search(r"(fix|bug|error|repair|resolve)", msg_lower):
            atom_type = AtomType.TROUBLESHOOTING.value
        elif re.search(r"(refactor|redesign|architecture|migrate)", msg_lower):
            atom_type = AtomType.DECISION.value
        elif re.search(r"(lesson|learn|mistake|retrospective|复盘)", msg_lower):
            atom_type = AtomType.LESSON.value

        answer = f"**Commit**: {commit['sha'][:8]}\n"
        answer += f"**Files**: {paths_str}\n"
        answer += f"**Changes**: +{commit['diff_stats']['insertions']}/-{commit['diff_stats']['deletions']}\n\n"
        answer += message

        question = f"[{repo_name}] {subject}" if repo_name else subject

        # Score Contract scoring
        src_quality = SOURCE_QUALITY.get("commit_kd0", 0.70)
        sc = ScoreComponents(
            extractor="commit_kd0",
            structure_score=score_structure(answer),
            information_density=score_information_density(message),
            completeness=score_completeness(message, ideal_min=30, ideal_max=500),
            specificity=score_specificity(subject),
            evidence_quality=src_quality,
            doc_value=kd0,
            type_prior=0.6 if atom_type == AtomType.QA.value else 0.75,
            actionability=0.7 if atom_type in (AtomType.TROUBLESHOOTING.value, AtomType.PROCEDURE.value) else 0.5,
            uniqueness=0.8,  # commits are inherently unique
        )
        sc.final_quality = compute_quality(sc)
        sc.final_value = compute_value(sc)

        yield Atom(
            atom_id=f"at_commit_{commit['sha'][:16]}",
            episode_id=episode.episode_id,
            atom_type=atom_type,
            question=question,
            answer=answer[:2000],
            canonical_question=subject.strip().lower()[:200],
            intent="code_change",
            stability=Stability.VERSIONED.value,
            status=AtomStatus.CANDIDATE.value,
            valid_from=commit.get("timestamp", 0),
            value_auto=sc.final_value,
            quality_auto=sc.final_quality,
            source_quality=src_quality,
            scores_json=sc.to_json(),
        )

    def extract_evidence(self, atom: Atom, episode: Episode) -> Iterator[Evidence]:
        commit = getattr(episode, "_commit", {})
        excerpt = atom.answer[:200] if atom.answer else atom.question[:200]
        yield Evidence(
            evidence_id=f"ev_{atom.atom_id[:20]}",
            atom_id=atom.atom_id,
            doc_id=episode.doc_id,
            span_ref=f"commit:{commit.get('sha', '')[:12]}",
            excerpt=excerpt,
            excerpt_hash=_hash_text(excerpt),
            evidence_role="source",
            weight=1.0,
        )
