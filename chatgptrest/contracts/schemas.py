"""
Typed artifact schemas for the Personal Intelligent Infrastructure.

Every layer produces and consumes these schemas.  They are designed to be:
- JSON-serialisable (for event log, MCP, REST)
- Hashable (for dedup / KB indexing)
- Versionable (``schema_version`` field)

Naming convention: PascalCase classes, snake_case fields.
All timestamps are ISO-8601 strings.  All IDs are ``str``.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Route(str, Enum):
    """Advisor routing destinations."""
    CLARIFY = "clarify"
    DIRECT_ANSWER = "direct_answer"
    KB_ANSWER = "kb_answer"
    DEEP_RESEARCH = "deep_research"
    FUNNEL = "funnel"
    ACTION = "action"
    HYBRID = "hybrid"


class FunnelStage(str, Enum):
    """Nine-stage hybrid funnel model (from Funnel DR)."""
    CAPTURE = "capture"
    TRIAGE = "triage"
    EXPLORE = "explore"
    FRAME = "frame"
    OPTIONIZE = "optionize"
    EVALUATE = "evaluate"
    VALIDATE = "validate"
    FREEZE = "freeze"
    EXECUTE_LEARN = "execute_learn"


class ConvergeTool(str, Enum):
    """Available diverge→converge mechanisms."""
    DEBATE = "debate"            # Existing tri-role debate
    RICE = "rice"                # Reach×Impact×Confidence/Effort
    MOSCOW = "moscow"            # Must/Should/Could/Won't
    KANO = "kano"                # Attractive/Must-be/Performance
    CSP = "csp"                  # Constraint Satisfaction
    PREMORTEM = "premortem"      # Assume failure, find reasons
    RED_BLUE = "red_blue"        # Adversarial stress test
    EVIDENCE = "evidence"        # Evidence-weighted
    AHP = "ahp"                  # Analytic Hierarchy Process


class EvidenceType(str, Enum):
    SOURCE = "source"
    EXPERIMENT = "experiment"
    OBSERVATION = "observation"


class EvidenceQuality(str, Enum):
    MEASUREMENT = "measurement"        # Direct data (highest)
    INTERVIEW = "interview"            # User/expert transcript
    EXPERT_OPINION = "expert_opinion"
    SPECULATION = "speculation"        # Lowest


class ArtifactKind(str, Enum):
    """Kinds of artifacts flowing through the system."""
    ANSWER = "answer_artifact"
    EVIDENCE_PACK = "evidence_pack"
    PROJECT_CARD = "project_card"
    DECISION_RECORD = "decision_record"
    TRACE = "trace"
    KB_NOTE = "kb_note"


# ---------------------------------------------------------------------------
# Layer 1: Advisor – AdvisorContext
# ---------------------------------------------------------------------------

@dataclass
class RouteScores:
    """C/K/U/R/I scoring model (from Advisor DR)."""
    intent_certainty: float = 0.0   # I ∈ [0,100]
    complexity: float = 0.0         # C ∈ [0,100]
    kb_score: float = 0.0           # K ∈ [0,100]
    urgency: float = 0.0            # U ∈ [0,100]
    risk: float = 0.0               # R ∈ [0,100]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntentSignals:
    """Signals extracted during intent classification."""
    intent_top: str = ""                  # Q&A, research, planning, action, ...
    intent_confidence: float = 0.0        # 0-1
    multi_intent: bool = False
    step_count_est: int = 1
    constraint_count: int = 0
    open_endedness: float = 0.0           # 0-1
    verification_need: bool = False
    action_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KBProbeResult:
    """Result of the mandatory KB probe before routing."""
    hit_rate: float = 0.0                 # fraction of chunks above threshold
    coverage: float = 0.0                 # entity/sub-question coverage
    freshness: float = 0.0               # age-based validity [0,1]
    answerability: float = 0.0            # can we answer from KB? [0,1]
    top_chunks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdvisorContext:
    """
    The canonical input artifact assembled by the Advisor gateway
    before routing to any workflow.
    """
    schema_version: str = "1.0"
    context_id: str = field(default_factory=_uuid)
    trace_id: str = field(default_factory=_uuid)
    session_id: str = ""
    timestamp: str = field(default_factory=_now_iso)

    # User input
    user_message: str = ""
    user_locale: str = "zh-CN"

    # Derived signals
    intent: IntentSignals = field(default_factory=IntentSignals)
    kb_probe: KBProbeResult = field(default_factory=KBProbeResult)
    scores: RouteScores = field(default_factory=RouteScores)

    # Routing decision
    selected_route: str = ""       # Route enum value
    route_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Layer 2: Workflow → Evidence & Answers
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """A single piece of evidence supporting a claim."""
    evidence_id: str = field(default_factory=_uuid)
    evidence_type: str = "source"          # EvidenceType value
    quality: str = "expert_opinion"        # EvidenceQuality value
    quality_score: float = 0.5             # 0-1 numeric
    supports: list[str] = field(default_factory=list)  # claim_ids
    source_url: str = ""
    source_title: str = ""
    snippet: str = ""
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Claim:
    """A claim that can be supported or refuted by evidence."""
    claim_id: str = field(default_factory=_uuid)
    text: str = ""
    criticality: str = "medium"           # high / medium / low

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePack:
    """
    A bundle of claims + supporting evidence.
    Used by DeepResearch, Funnel, and KB.
    """
    schema_version: str = "1.0"
    pack_id: str = field(default_factory=_uuid)
    trace_id: str = ""
    created_at: str = field(default_factory=_now_iso)

    claims: list[Claim] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    provenance: str = ""                  # which workflow produced this

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnswerArtifact:
    """
    The final answer produced by any workflow,
    with confidence and evidence pointers.
    """
    schema_version: str = "1.0"
    answer_id: str = field(default_factory=_uuid)
    trace_id: str = ""
    created_at: str = field(default_factory=_now_iso)

    route_used: str = ""                  # Route enum value
    answer_text: str = ""
    confidence: float = 0.0               # 0-1
    evidence_pack_id: str = ""            # reference to EvidencePack
    citations: list[dict[str, str]] = field(default_factory=list)
    kb_writeback_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Layer 2: Funnel → ProjectCard
# ---------------------------------------------------------------------------

@dataclass
class SuccessMetric:
    metric: str = ""
    target: str = ""
    measurement_method: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Risk:
    risk_id: str = field(default_factory=_uuid)
    description: str = ""
    probability: float = 0.0
    impact: float = 0.0
    mitigation: str = ""
    detection_signal: str = ""
    owner: str = "human"                  # "human" | "agent"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    task_id: str = field(default_factory=_uuid)
    title: str = ""
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    estimated_effort_hours: float = 0.0
    agent_role: str = ""
    outputs: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AcceptanceTest:
    test_id: str = field(default_factory=_uuid)
    test: str = ""
    pass_fail_rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionRecord:
    """ADR-style decision record."""
    chosen_option: str = ""
    alternatives_considered: list[dict[str, str]] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RubricSnapshot:
    """Convergence Rubric v1 scores at freeze time."""
    total: float = 0.0
    information_completeness: float = 0.0
    controversy_convergence: float = 0.0
    risk_controllability: float = 0.0
    scope_boundary_clarity: float = 0.0
    executability: float = 0.0
    evidence_sufficiency: float = 0.0
    gate: str = ""                        # "A" | "B" | "C"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectCard:
    """
    Execution-ready project card produced by the Funnel.
    Schema from Funnel DR → ProjectCard JSON Schema.
    """
    schema_version: str = "1.0"
    project_id: str = field(default_factory=_uuid)
    trace_id: str = ""
    created_at: str = field(default_factory=_now_iso)

    # Identity & intent
    title: str = ""
    problem_statement: str = ""
    job_to_be_done: str = ""
    success_metrics: list[SuccessMetric] = field(default_factory=list)

    # Scope & boundaries
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    dependencies: list[dict[str, str]] = field(default_factory=list)

    # Plan & execution
    deliverables: list[dict[str, str]] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    acceptance_tests: list[AcceptanceTest] = field(default_factory=list)
    definition_of_done: list[str] = field(default_factory=list)

    # Risk & mitigation
    risks: list[Risk] = field(default_factory=list)
    premortem_summary: str = ""
    red_team_findings: str = ""

    # Evidence & decision
    evidence_pack_id: str = ""
    decision_record: DecisionRecord = field(default_factory=DecisionRecord)
    rubric_snapshot: RubricSnapshot = field(default_factory=RubricSnapshot)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Cross-cutting: Trace Events (CloudEvents-inspired)
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """Core event types flowing through the event log."""
    # Layer 1: Advisor
    MESSAGE_RECEIVED = "message_received"
    INTENT_CLASSIFIED = "intent_classified"
    ROUTE_SELECTED = "route_selected"

    # Layer 3: KB
    KB_QUERY_STARTED = "kb_query_started"
    KB_QUERY_FINISHED = "kb_query_finished"
    KB_WRITE_REQUESTED = "kb_write_requested"
    KB_WRITE_COMMITTED = "kb_write_committed"

    # Layer 2: Workflow
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_STEP_FINISHED = "workflow_step_finished"
    WORKFLOW_FINISHED = "workflow_finished"

    # Tools
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_FINISHED = "tool_call_finished"

    # Artifacts
    ARTIFACT_CREATED = "artifact_created"

    # Quality
    QUALITY_GATE_PASSED = "quality_gate_passed"
    QUALITY_GATE_FAILED = "quality_gate_failed"

    # User feedback
    USER_FEEDBACK_RECEIVED = "user_feedback_received"

    # Layer 4: EvoMap
    EVOMAP_SIGNAL_DETECTED = "evomap_signal_detected"
    EVOMAP_CHANGE_PROPOSED = "evomap_change_proposed"
    EVOMAP_CHANGE_APPLIED = "evomap_change_applied"


@dataclass
class TraceEvent:
    """
    CloudEvents-inspired envelope for all system events.
    One trace_id is propagated across Advisor→Funnel→KB→EvoMap.
    """
    # CloudEvents standard fields
    specversion: str = "1.0"
    event_id: str = field(default_factory=_uuid)
    source: str = ""                      # e.g. "advisor/triage", "funnel/frame"
    event_type: str = ""                  # EventType value
    timestamp: str = field(default_factory=_now_iso)

    # Tracing
    trace_id: str = ""
    session_id: str = ""
    parent_event_id: str = ""             # for event chaining

    # Payload
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def content_hash(self) -> str:
        """Deterministic hash for dedup."""
        import json
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return _sha256(raw)


# ---------------------------------------------------------------------------
# v3 Additions: Effect types, 3-stage funnel, memory tiers
# ---------------------------------------------------------------------------

class EffectType:
    """Types of external side-effects managed by Effects Outbox."""
    FEISHU_NOTIFY = "feishu_notify"
    AGENT_DISPATCH = "agent_dispatch"
    KB_WRITEBACK = "kb_writeback"


class FunnelStageV3:
    """Three-stage funnel model (v3: CoT + Extraction per stage).

    Each stage runs two LLM calls:
        1. CoT (free-form reasoning scratchpad)
        2. Extraction (structured JSON output)
    """
    UNDERSTAND = "understand"     # Capture + Triage + Explore
    ANALYZE = "analyze"          # Frame + Optionize + Evaluate
    FINALIZE = "finalize"        # Validate + Freeze + Execute/Learn


class MemoryTier:
    """Memory tier classification for future unified MemoryManager.

    Adopted from KB 03_memory_kb_architecture.md four-layer model.
    """
    WORKING = "working"      # Current session state, <10ms
    EPISODIC = "episodic"    # Historical events/tasks, <100ms
    SEMANTIC = "semantic"    # Long-term facts/profile, <100ms
    META = "meta"            # Routing stats/audit, <50ms


class MemorySource:
    """Source types for memory record provenance."""
    USER_INPUT = "user_input"
    LLM_INFERENCE = "llm_inference"
    TOOL_RESULT = "tool_result"
    EVOMAP_SIGNAL = "evomap_signal"
    AGENT_OUTPUT = "agent_output"

