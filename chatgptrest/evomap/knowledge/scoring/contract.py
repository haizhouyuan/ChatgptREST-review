"""Unified Score Contract for all EvoMap Knowledge extractors.

Every extractor MUST compute and fill these fields on each Atom:
- quality_auto   [0,1]  Content quality (structure, density, completeness)
- value_auto     [0,1]  Knowledge value (usefulness, uniqueness, timeliness)
- source_quality [0,1]  Source credibility
- scores_json    {}     Full component breakdown (traceable)

Design rationale (from GPT-5-2-Pro review):
- All extractors output the SAME score contract
- No single proxy variable (e.g. answer length) can be the sole quality signal
- quality_auto must combine >= 3 independent dimensions
- scores_json must trace component scores for debugging
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field


@dataclass
class ScoreComponents:
    """Traceable score components. Stored as scores_json."""

    extractor: str = ""

    # Quality sub-components (combined → quality_auto)
    structure_score: float = 0.0       # Has lists/code/headings/tables
    information_density: float = 0.0   # Unique terms / total length ratio
    completeness: float = 0.0          # Answer saturation (not too short, not too long)
    specificity: float = 0.0           # How specific is the question/heading
    evidence_quality: float = 0.0      # Grounding in source material

    # Value sub-components (combined → value_auto)
    doc_value: float = 0.0             # Document-level value estimate
    type_prior: float = 0.0            # AtomType-based prior
    actionability: float = 0.0         # Procedural / decision / troubleshooting
    uniqueness: float = 0.0            # Inverse of duplication

    # Computed finals
    final_quality: float = 0.0
    final_value: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> ScoreComponents:
        try:
            d = json.loads(s) if isinstance(s, str) else s
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()


# ---------------------------------------------------------------------------
# Shared scoring utilities
# ---------------------------------------------------------------------------

def score_structure(text: str) -> float:
    """Score structural richness of content [0, 1].

    Signals: code blocks, bullet lists, numbered lists, tables, headings.
    """
    if not text:
        return 0.0

    signals = 0.0
    total_weight = 5.0

    # Code blocks (``` or indented)
    code_blocks = len(re.findall(r'```', text))
    if code_blocks >= 2:
        signals += 1.0
    elif code_blocks >= 1:
        signals += 0.5

    # Bullet lists
    bullets = len(re.findall(r'^\s*[-*]\s', text, re.MULTILINE))
    if bullets >= 3:
        signals += 1.0
    elif bullets >= 1:
        signals += 0.4

    # Numbered lists
    numbered = len(re.findall(r'^\s*\d+[.)]\s', text, re.MULTILINE))
    if numbered >= 3:
        signals += 1.0
    elif numbered >= 1:
        signals += 0.4

    # Tables
    if re.search(r'\|.+\|.+\|', text):
        signals += 1.0

    # Sub-headings within content
    headings = len(re.findall(r'^#{2,4}\s', text, re.MULTILINE))
    if headings >= 2:
        signals += 1.0
    elif headings >= 1:
        signals += 0.5

    return min(1.0, signals / total_weight)


def score_specificity(title: str) -> float:
    """Score heading/question specificity [0, 1].

    Generic headings ("总结", "方案", "问题") score low.
    Specific headings ("Redis 主从配置步骤") score high.
    """
    if not title:
        return 0.0

    title_lower = title.lower().strip()

    # Very generic → low specificity
    generic_patterns = [
        r'^(总结|方案|问题|说明|概述|背景|介绍|参考|附录|其他)$',
        r'^(summary|overview|introduction|notes|misc|other|todo)$',
        r'^\(intro\)$', r'^\(full document\)$',
    ]
    for pat in generic_patterns:
        if re.match(pat, title_lower):
            return 0.1

    # Length-based heuristic: longer titles tend to be more specific
    words = len(title_lower.split())
    cjk_chars = sum(1 for c in title_lower if '\u4e00' <= c <= '\u9fff')
    effective_words = words + cjk_chars * 0.5

    if effective_words <= 1:
        return 0.2
    elif effective_words <= 3:
        return 0.5
    elif effective_words <= 6:
        return 0.7
    else:
        return 0.9


def score_completeness(text: str, ideal_min: int = 200, ideal_max: int = 3000) -> float:
    """Score content saturation [0, 1].

    Too short = fragment, too long = noise. Sweet spot in [ideal_min, ideal_max].
    """
    length = len(text)
    if length < 50:
        return 0.1
    elif length < ideal_min:
        return 0.3 + 0.4 * (length / ideal_min)
    elif length <= ideal_max:
        return 0.8 + 0.2 * min(1.0, length / ideal_max)
    else:
        # Slight penalty for very long (but not harsh)
        return max(0.6, 1.0 - 0.1 * math.log(length / ideal_max))


def score_information_density(text: str) -> float:
    """Score information density [0, 1].

    Ratio of unique meaningful tokens to total length.
    High density = concise, information-rich. Low = repetitive or boilerplate.
    """
    if not text or len(text) < 50:
        return 0.3

    # Simple unique word ratio
    words = re.findall(r'\w+', text.lower())
    if not words:
        return 0.3

    unique_ratio = len(set(words)) / len(words)

    # URLs, code, numbers boost density (technical content)
    tech_signals = (
        len(re.findall(r'https?://', text))
        + len(re.findall(r'```', text))
        + len(re.findall(r'`[^`]+`', text))
    )
    tech_boost = min(0.2, tech_signals * 0.03)

    return min(1.0, unique_ratio * 1.2 + tech_boost)


def compute_quality(components: ScoreComponents) -> float:
    """Combine quality sub-components into quality_auto [0, 1]."""
    weights = {
        "structure_score": 0.20,
        "information_density": 0.20,
        "completeness": 0.25,
        "specificity": 0.20,
        "evidence_quality": 0.15,
    }
    total = sum(
        getattr(components, k, 0.0) * w
        for k, w in weights.items()
    )
    return min(1.0, max(0.0, total))


def compute_value(components: ScoreComponents) -> float:
    """Combine value sub-components into value_auto [0, 1]."""
    weights = {
        "doc_value": 0.30,
        "type_prior": 0.20,
        "actionability": 0.25,
        "uniqueness": 0.25,
    }
    total = sum(
        getattr(components, k, 0.0) * w
        for k, w in weights.items()
    )
    return min(1.0, max(0.0, total))


# ---------------------------------------------------------------------------
# Per-extractor source quality defaults
# ---------------------------------------------------------------------------

SOURCE_QUALITY = {
    "chat_followup": 0.75,    # AI-generated answers — moderately reliable
    "note_section": 0.60,     # Markdown notes — mixed quality
    "maint_runbook": 0.80,    # Production scripts — high reliability
    "commit_kd0": 0.70,       # Git commits — factual but terse
}
