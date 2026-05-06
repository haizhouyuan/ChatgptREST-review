"""EvoMap Knowledge DB — Core data models.

6-table schema based on Document → Episode → Atom architecture.
Designed for SQLite with FTS5 full-text search.

References:
- ChatGPT Pro consultation: chatgpt_pro_full_evomap.md
- thinking_heavy Q1-Q2: Thread+Turn model
- thinking_heavy Q3: LifeOS pipeline
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AtomType(str, enum.Enum):
    """Knowledge atom types (from Pro: 5 core types)."""
    QA = "qa"
    DECISION = "decision"
    PROCEDURE = "procedure"
    TROUBLESHOOTING = "troubleshooting"
    LESSON = "lesson"


class EpisodeType(str, enum.Enum):
    """Episode (event unit) types per source."""
    CHAT_CHAIN = "chat_chain"           # ChatgptREST followup chain
    CHAT_SINGLE = "chat_single"         # Single-turn QA
    MD_SECTION = "md_section"           # Markdown heading subtree
    COMMIT_CLUSTER = "commit_cluster"   # Git commit episode
    FUNNEL_CLUSTER = "funnel_cluster"   # Funnel fragment cluster
    SPECSTORY_CYCLE = "specstory_cycle" # .specstory goal→edit→test cycle
    RUNBOOK = "runbook"                 # maint script runbook card


class Stability(str, enum.Enum):
    """Knowledge stability levels (critical for avoiding stale knowledge)."""
    EVERGREEN = "evergreen"       # Timeless principles
    VERSIONED = "versioned"       # Valid for specific version/context
    EPHEMERAL = "ephemeral"       # Temporary / work-in-progress
    SUPERSEDED = "superseded"     # Replaced by newer knowledge


class AtomStatus(str, enum.Enum):
    """Atom lifecycle status."""
    CANDIDATE = "candidate"       # Extracted, not yet scored
    SCORED = "scored"             # AutoScore applied
    GATE_A = "gate_a"            # High quality + high value
    GATE_B = "gate_b"            # High quality, moderate value
    GATE_C = "gate_c"            # Needs rewrite/evidence
    GATE_X = "gate_x"            # Rejected
    REFINED = "refined"          # LLM-refined
    PUBLISHED = "published"      # Human-reviewed, in service
    NEEDS_REVALIDATE = "needs_revalidate"  # Source changed


class PromotionStatus(str, enum.Enum):
    """Atom promotion lifecycle for staged knowledge governance."""
    STAGED = "staged"             # Raw refined result, not yet chain-validated
    CANDIDATE = "candidate"       # Passed P1 structural checks
    ACTIVE = "active"             # Passed P2 groundedness, in active retrieval
    SUPERSEDED = "superseded"     # Replaced by newer atom in same chain
    ARCHIVED = "archived"         # Low-value or intentionally hidden


class EdgeType(str, enum.Enum):
    """Relationship types between atoms/episodes."""
    DERIVED_FROM = "derived_from"
    CLARIFIES = "clarifies"
    ADDS_CONSTRAINT = "adds_constraint"
    CORRECTS = "corrects"
    IMPLEMENTS = "implements"
    EVIDENCED_BY = "evidenced_by"
    SAME_TOPIC = "same_topic"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _new_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex
    return f"{prefix}{uid}" if prefix else uid


def _now() -> float:
    return time.time()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """Raw carrier — a job, markdown file, commit group, funnel fragment, etc."""
    doc_id: str = field(default_factory=lambda: _new_id("doc_"))
    source: str = ""           # chat_job / lifeos_md / research_md / git_commit / funnel / maint_script
    project: str = ""          # ChatgptREST / openclaw / codexread / homeagent / etc.
    raw_ref: str = ""          # Unique locator (job_id, file path, commit sha)
    title: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    hash: str = ""             # Content hash for change detection
    meta_json: str = "{}"      # Flexible metadata

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Document:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


@dataclass
class Episode:
    """Event unit — a followup chain, section subtree, commit cluster, etc."""
    episode_id: str = field(default_factory=lambda: _new_id("ep_"))
    doc_id: str = ""
    episode_type: str = ""     # EpisodeType value
    title: str = ""
    summary: str = ""
    start_ref: str = ""        # Start locator (turn index, line number, commit sha)
    end_ref: str = ""          # End locator
    time_start: float = 0.0
    time_end: float = 0.0
    turn_count: int = 0        # For chat chains
    source_ext: str = "{}"     # Source-specific extension fields (JSON)

    # Thread signals (from thinking_heavy advice)
    followup_depth: int = 0
    constraint_growth: int = 0
    reversal_count: int = 0
    convergence_score: float = 0.0

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Episode:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


@dataclass
class Atom:
    """Knowledge atom — the fundamental retrievable unit."""
    atom_id: str = field(default_factory=lambda: _new_id("at_"))
    episode_id: str = ""
    atom_type: str = AtomType.QA.value

    # Content
    question: str = ""
    answer: str = ""
    canonical_question: str = ""   # Normalized question for dedup
    alt_questions: str = "[]"      # JSON array of alternative phrasings
    constraints: str = "[]"        # JSON array of applicability constraints
    prerequisites: str = "[]"      # JSON array of prerequisites

    # Categorization
    intent: str = ""               # debug / design / howto / compare / decision / fact
    format: str = "plain"          # plain / code / steps / table

    # Lifecycle
    applicability: str = "{}"      # JSON: project, scope, version, component
    scope_project: str = ""        # Runtime retrieval/project-scoped filter
    scope_component: str = ""      # Optional sub-project/component scope
    stability: str = Stability.VERSIONED.value
    status: str = AtomStatus.CANDIDATE.value
    valid_from: float = 0.0
    valid_to: float = 0.0          # 0 = no expiry

    # Scores (from dual-axis scoring: Quality × Value)
    quality_auto: float = 0.0
    value_auto: float = 0.0
    novelty: float = 0.0
    groundedness: float = 0.0      # Evidence consistency score
    confidence: float = 0.0
    reusability: float = 0.0
    scores_json: str = "{}"        # Full score breakdown

    # Source tracking
    source_quality: float = 0.0
    hash: str = ""                 # Content hash for change detection

    # P1: Evolution chain & promotion (Issue #93)
    promotion_status: str = "staged"   # PromotionStatus value
    superseded_by: str = ""            # atom_id of newer replacement
    chain_id: str = ""                 # Groups atoms with same canonical_question
    chain_rank: int = 0                # Ordering within chain (1=oldest, N=newest)
    is_chain_head: int = 0             # 1 only for newest/current in chain
    promotion_reason: str = ""         # Why atom is in current state

    def compute_hash(self) -> str:
        text = f"{self.question}|{self.answer}"
        self.hash = _hash_text(text)
        return self.hash

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Atom:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


@dataclass
class Evidence:
    """Evidence fragment — links atoms to source material."""
    evidence_id: str = field(default_factory=lambda: _new_id("ev_"))
    atom_id: str = ""
    doc_id: str = ""
    span_ref: str = ""         # Locator: file:line_start-line_end, turn:N, commit:sha
    excerpt: str = ""          # Relevant excerpt text
    excerpt_hash: str = ""     # Hash for change detection
    evidence_role: str = ""    # supports / contradicts / context / example
    weight: float = 1.0

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Evidence:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


@dataclass
class Entity:
    """Named entity — repos, skills, components, tools, etc."""
    entity_id: str = field(default_factory=lambda: _new_id("ent_"))
    entity_type: str = ""      # repo / skill / component / tool / module / metric
    name: str = ""
    normalized_name: str = ""  # Lowercase/stemmed for matching

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Entity:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


@dataclass
class Edge:
    """Relationship between any two objects (atoms, episodes, entities)."""
    from_id: str = ""
    to_id: str = ""
    edge_type: str = ""        # EdgeType value
    weight: float = 1.0
    from_kind: str = ""        # "atom" | "episode" | "entity" | "document"
    to_kind: str = ""          # "atom" | "episode" | "entity" | "document"
    meta_json: str = "{}"      # Additional context

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> Edge:
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})
