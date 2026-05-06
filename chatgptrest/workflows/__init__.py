"""
DeepResearch Workflow (S5) – Web Research → Evidence → Synthesis → KB Writeback.

Orchestrates the full deep research flow:
1. Parse & enhance the user query (from AdvisorContext)
2. Submit to ChatgptREST's existing deep_research endpoint
3. Monitor job completion
4. Parse answer into structured EvidencePack
5. Produce AnswerArtifact
6. Write results back to KB
7. Emit trace events throughout
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from ..contracts.schemas import (
    AdvisorContext,
    AnswerArtifact,
    Claim,
    EvidenceItem,
    EvidencePack,
    TraceEvent,
    EventType,
    _uuid,
    _now_iso,
)
from ..contracts.event_log import EventLogStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow state
# ---------------------------------------------------------------------------

@dataclass
class DeepResearchState:
    """Tracks the state of a deep research job."""
    trace_id: str = ""
    session_id: str = ""
    original_query: str = ""
    enhanced_prompt: str = ""
    job_id: str = ""
    status: str = "pending"    # pending → submitted → polling → completed → synthesized → written_back
    raw_answer: str = ""
    evidence_pack: Optional[EvidencePack] = None
    answer_artifact: Optional[AnswerArtifact] = None
    error: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Query Enhancement
# ---------------------------------------------------------------------------

def enhance_research_prompt(query: str, context: AdvisorContext | None = None) -> str:
    """
    Enhance a user query into a detailed research prompt.

    Adds structure to help the deep research model produce better results:
    - Explicit research questions
    - Expected output structure
    - Quality requirements
    """
    parts = [
        f"## 研究主题\n{query}\n",
        "## 研究要求",
        "1. 提供系统性的分析，而非表面回答",
        "2. 引用具体来源、论文、框架或案例",
        "3. 对比不同方法/观点的优劣",
        "4. 给出可操作的建议和下一步行动",
        "5. 如有争议性观点，说明各方立场",
        "",
        "## 输出格式",
        "- 使用清晰的标题层级结构",
        "- 关键结论用加粗标注",
        "- 数据和证据用表格或列表呈现",
        "- 最后给出总结和行动建议",
    ]

    if context and context.kb_probe and context.kb_probe.hit_rate > 0:
        parts.append(f"\n## 已有知识参考\nKB 已有相关覆盖率: {context.kb_probe.hit_rate:.0%}，"
                     "请在此基础上深入补充而非重复。")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Evidence Extraction (from markdown answer)
# ---------------------------------------------------------------------------

def extract_evidence_from_answer(
    answer_text: str,
    trace_id: str = "",
) -> EvidencePack:
    """
    Parse a research answer into a structured EvidencePack.

    Extracts:
    - Key claims (bold text, numbered conclusions)
    - Evidence items (citations, data points, framework references)
    - Source references
    """
    claims = []
    evidence_items = []

    lines = answer_text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Extract bold text as claims
        bold_matches = re.findall(r'\*\*(.+?)\*\*', stripped)
        for match in bold_matches:
            if len(match) > 10:  # Skip short bold text
                claims.append(Claim(
                    text=match,
                    criticality="medium",
                ))

        # Extract numbered conclusions
        if re.match(r'^\d+\.\s+', stripped) and len(stripped) > 30:
            # Check if it's a recommendation/conclusion section
            context_window = "\n".join(lines[max(0, i-5):i])
            if any(kw in context_window.lower() for kw in
                   ["结论", "建议", "推荐", "总结", "conclusion", "recommend", "summary"]):
                claims.append(Claim(
                    text=stripped,
                    criticality="high",
                ))

        # Extract citations and references
        url_matches = re.findall(r'https?://[^\s\)]+', stripped)
        for url in url_matches:
            evidence_items.append(EvidenceItem(
                evidence_type="source",
                quality="citation",
                quality_score=0.7,
                source_url=url,
                snippet=stripped[:200],
            ))

        # Extract framework/methodology references
        framework_keywords = [
            "framework", "model", "theory", "method", "approach",
            "框架", "模型", "理论", "方法", "范式",
        ]
        if any(kw in stripped.lower() for kw in framework_keywords) and len(stripped) > 20:
            evidence_items.append(EvidenceItem(
                evidence_type="framework",
                quality="expert_opinion",
                quality_score=0.6,
                snippet=stripped[:300],
            ))

    # Deduplicate claims
    seen_claims = set()
    unique_claims = []
    for c in claims:
        key = c.text[:50]
        if key not in seen_claims:
            seen_claims.add(key)
            unique_claims.append(c)

    return EvidencePack(
        trace_id=trace_id,
        provenance="deep_research",
        claims=unique_claims[:20],  # Cap at 20 claims
        evidence=evidence_items[:30],  # Cap at 30 evidence items
    )


# ---------------------------------------------------------------------------
# DeepResearch Workflow Engine
# ---------------------------------------------------------------------------

class DeepResearchWorkflow:
    """
    Orchestrates the full deep research flow.

    Usage::

        workflow = DeepResearchWorkflow(event_log=store)
        state = workflow.execute(
            query="Agent 自进化的最新方法论有哪些？",
            context=advisor_context,
        )
        print(state.answer_artifact.answer_text[:200])
    """

    def __init__(
        self,
        event_log: EventLogStore | None = None,
        kb_retriever=None,  # KBRetriever for writeback
        kb_registry=None,    # ArtifactRegistry for writeback
    ):
        self.event_log = event_log
        self.kb_retriever = kb_retriever
        self.kb_registry = kb_registry

    def _emit(self, event_type: str, trace_id: str, data: dict, session_id: str = "") -> None:
        """Emit a trace event."""
        if self.event_log:
            self.event_log.append(TraceEvent(
                source="deep_research/workflow",
                event_type=event_type,
                trace_id=trace_id,
                session_id=session_id,
                data=data,
            ))

    def execute(
        self,
        query: str,
        *,
        context: AdvisorContext | None = None,
        trace_id: str = "",
        session_id: str = "",
    ) -> DeepResearchState:
        """
        Execute the full deep research workflow.

        For now, this runs in "local" mode (no actual API call),
        processing existing research results or producing a structured
        research plan that can be submitted externally.
        """
        trace_id = trace_id or _uuid()
        state = DeepResearchState(
            trace_id=trace_id,
            session_id=session_id,
            original_query=query,
            started_at=_now_iso(),
        )

        # Step 1: Enhance prompt
        state.enhanced_prompt = enhance_research_prompt(query, context)
        state.status = "enhanced"
        self._emit("workflow_started", trace_id, {
            "workflow": "deep_research",
            "query": query,
            "enhanced_prompt_length": len(state.enhanced_prompt),
        }, session_id)

        # Step 2: In local mode, we create a research plan artifact
        # In production, this would submit to ChatgptREST's /api/deep-research
        state.status = "plan_ready"
        self._emit("workflow_step_finished", trace_id, {
            "step": "prompt_enhancement",
            "enhanced_prompt": state.enhanced_prompt[:500],
        }, session_id)

        return state

    def process_answer(
        self,
        state: DeepResearchState,
        answer_text: str,
    ) -> DeepResearchState:
        """
        Process a completed research answer (from API or manual input).

        Extracts evidence, builds AnswerArtifact, and writes back to KB.
        """
        state.raw_answer = answer_text
        state.status = "completed"

        # Step 3: Extract evidence
        state.evidence_pack = extract_evidence_from_answer(
            answer_text, state.trace_id
        )
        state.status = "evidence_extracted"
        self._emit("workflow_step_finished", state.trace_id, {
            "step": "evidence_extraction",
            "claims_count": len(state.evidence_pack.claims),
            "evidence_count": len(state.evidence_pack.evidence),
        }, state.session_id)

        # Step 4: Build AnswerArtifact
        state.answer_artifact = AnswerArtifact(
            trace_id=state.trace_id,
            answer_text=answer_text,
            evidence_pack_id=state.evidence_pack.pack_id,
            route_used="deep_research",
            confidence=min(1.0, len(state.evidence_pack.claims) * 0.1 + 0.3),
        )
        state.status = "synthesized"

        # Step 5: KB Writeback
        if self.kb_retriever:
            self.kb_retriever.index_text(
                artifact_id=f"dr_{state.trace_id[:12]}",
                title=f"Research: {state.original_query[:50]}",
                content=answer_text,
                source_path=f"deep_research/{state.trace_id}",
                tags=["deep_research", "auto_indexed"],
                content_type="markdown",
                quality_score=0.8,
            )
            state.status = "written_back"
            self._emit("kb_write_committed", state.trace_id, {
                "artifact_id": f"dr_{state.trace_id[:12]}",
                "word_count": len(answer_text.split()),
            }, state.session_id)

        state.completed_at = _now_iso()
        self._emit("workflow_finished", state.trace_id, {
            "workflow": "deep_research",
            "status": state.status,
            "claims": len(state.evidence_pack.claims),
            "evidence": len(state.evidence_pack.evidence),
        }, state.session_id)

        return state
