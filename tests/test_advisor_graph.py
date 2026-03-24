"""Tests for LangGraph Advisor Graph (T2.1 + T2.2).

Covers:
    - Graph compiles and runs end-to-end
    - normalize strips Chinese fillers
    - kb_probe defaults and pre-populated
    - analyze_intent classifies WRITE_REPORT / BUILD_FEATURE / DO_RESEARCH / QUICK_QUESTION
    - route_decision applies C/K/U/R/I routing correctly
    - All 4 routes reachable
    - State shape is lean (no large blobs)
"""

import sqlite3
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
import chatgptrest.advisor.graph as graph_mod
from chatgptrest.advisor.graph import (
    AdvisorState,
    build_advisor_graph,
    bind_runtime_services,
    execute_quick_ask,
    normalize,
    kb_probe,
    analyze_intent,
    route_decision,
)


@pytest.fixture
def app():
    graph = build_advisor_graph()
    return graph.compile()


# ── Node Unit Tests ───────────────────────────────────────────────

def test_normalize_strips_fillers():
    """normalize removes Chinese filler words."""
    state: AdvisorState = {"user_message": "那个就是帮我写个报告嗯"}
    result = normalize(state)
    assert "那个" not in result["normalized_message"]
    assert "就是" not in result["normalized_message"]
    assert "嗯" not in result["normalized_message"]
    assert "报告" in result["normalized_message"]


def test_normalize_preserves_english():
    """normalize doesn't break English text."""
    state: AdvisorState = {"user_message": "Write me a progress report"}
    result = normalize(state)
    assert result["normalized_message"] == "Write me a progress report"


def test_kb_probe_default():
    """kb_probe defaults to no match."""
    state: AdvisorState = {"user_message": "test"}
    result = kb_probe(state)
    assert result["kb_has_answer"] is False
    assert result["kb_answerability"] == 0.0


def test_kb_probe_pre_populated():
    """kb_probe uses pre-populated answerability."""
    state: AdvisorState = {"user_message": "test", "kb_answerability": 0.8}
    result = kb_probe(state)
    assert result["kb_has_answer"] is True


def test_intent_write_report():
    """analyze_intent classifies report requests."""
    state: AdvisorState = {"normalized_message": "帮我写个安徽项目进展报告"}
    result = analyze_intent(state)
    assert result["intent_top"] == "WRITE_REPORT"
    assert result["intent_confidence"] > 0.8


def test_intent_build_feature():
    """analyze_intent classifies build requests."""
    state: AdvisorState = {"normalized_message": "开发一个新功能"}
    result = analyze_intent(state)
    assert result["intent_top"] == "BUILD_FEATURE"


def test_intent_research():
    """analyze_intent classifies research requests."""
    state: AdvisorState = {"normalized_message": "调研一下竞品分析"}
    result = analyze_intent(state)
    assert result["intent_top"] == "DO_RESEARCH"


def test_intent_upload_to_google_drive_stays_actionable_question():
    """Explicit action asks should stay actionable instead of becoming build/funnel work."""
    state: AdvisorState = {"normalized_message": "把这个文件上传到Google Drive"}
    result = analyze_intent(state)
    assert result["intent_top"] == "QUICK_QUESTION"
    assert result["action_required"] is True


def test_intent_send_notice_marks_action_required():
    """Direct notification commands should be recognized as action requests."""
    state: AdvisorState = {"normalized_message": "给团队发一条通知，说今晚 9 点开始切换"}
    result = analyze_intent(state)
    assert result["intent_top"] == "QUICK_QUESTION"
    assert result["action_required"] is True


def test_intent_sales_points_system_prefers_build_feature():
    """Product-building prompts should not be hijacked into KB quick-answer mode."""
    state: AdvisorState = {
        "normalized_message": "我们要做一个销售奖励积分系统，请输出关键业务流程、核心实体和最小可行版本方案。"
    }
    result = analyze_intent(state)
    assert result["intent_top"] == "BUILD_FEATURE"


def test_intent_industry_chain_research_prefers_research():
    """Industry-chain investigation prompts should stay on research semantics."""
    state: AdvisorState = {
        "normalized_message": "调研行星滚柱丝杠产业链的关键玩家、国产替代进展和主要技术瓶颈。"
    }
    result = analyze_intent(state)
    assert result["intent_top"] == "DO_RESEARCH"


def test_intent_reward_system_project_card_prefers_build_feature():
    """Business-style reward-system requests should stay on build/funnel semantics."""
    state: AdvisorState = {
        "normalized_message": (
            "想做一个给我儿子用的奖励积分小应用，既要承载奖励算法，"
            "也要把游戏化、儿童心理发展和成就体系放进去，先按项目卡方式帮我拆清楚。"
        )
    }
    result = analyze_intent(state)
    assert result["intent_top"] == "BUILD_FEATURE"


def test_intent_research_judgment_without_report_prefers_research():
    """Explicit research-only framing should not be hijacked by imperative wording."""
    state: AdvisorState = {
        "normalized_message": (
            "把我以前做过的投研助手和研究工作先归纳一下，"
            "再判断新投研框架怎么重构，先做研究判断，不写正式汇报。"
        )
    }
    result = analyze_intent(state)
    assert result["intent_top"] == "DO_RESEARCH"


def test_intent_quick_question():
    """analyze_intent classifies simple questions."""
    state: AdvisorState = {"normalized_message": "what is the status?"}
    result = analyze_intent(state)
    assert result["intent_top"] == "QUICK_QUESTION"


def test_intent_respects_scenario_pack_override():
    state: AdvisorState = {
        "normalized_message": "整理今天的例会纪要",
        "scenario_pack": {"intent_top": "WRITE_REPORT", "profile": "meeting_summary"},
    }
    result = analyze_intent(state)
    assert result["intent_top"] == "WRITE_REPORT"


def test_route_explicit_action_request_prefers_action():
    """Action-required quick asks should resolve to the action pipeline."""
    state: AdvisorState = {
        "normalized_message": "把这个文件上传到Google Drive",
        "user_message": "把这个文件上传到Google Drive",
        "kb_answerability": 0.0,
        "kb_top_chunks": [],
        "urgency_hint": "whenever",
    }
    state.update(analyze_intent(state))
    result = route_decision(state)
    assert result["selected_route"] == "action"


def test_route_action_is_not_overridden_by_build_feature_intent():
    """Build-style wording should not clobber a selected action route."""
    result = route_decision(
        {
            "intent_top": "BUILD_FEATURE",
            "intent_confidence": 0.9,
            "multi_intent": False,
            "step_count_est": 2,
            "constraint_count": 0,
            "open_endedness": 0.2,
            "verification_need": False,
            "action_required": True,
            "kb_answerability": 0.0,
            "kb_top_chunks": [],
            "urgency_hint": "whenever",
        }
    )
    assert result["selected_route"] == "action"


# ── End-to-End Graph Tests ────────────────────────────────────────

def test_graph_compiles(app):
    """Graph compiles without error."""
    assert app is not None


def test_graph_full_run(app):
    """Full graph run produces route decision."""
    result = app.invoke({"user_message": "帮我写个安徽项目进展报告"})
    assert result["selected_route"] != ""
    assert result["route_rationale"] != ""
    assert "route_scores" in result


def test_graph_route_kb_answer(app):
    """KB answer route is reachable."""
    result = app.invoke({
        "user_message": "what is our budget?",
        "kb_answerability": 0.8,
        "urgency_hint": "immediate",
    })
    assert result["selected_route"] == "kb_answer"


def test_graph_report_route_with_checkpointer_avoids_runtime_serialization(tmp_path):
    """Checkpointed report runs should not try to msgpack live runtime services."""

    class _DummyHub:
        def evidence_pack(self, scope, max_docs=20):  # noqa: ANN001
            return []

    class _DummyPolicyEngine:
        def run_quality_gate(self, ctx):  # noqa: ANN001
            return SimpleNamespace(allowed=True, blocked_by=[])

    def _llm(prompt: str, system_msg: str = "") -> str:
        prompt_lower = prompt.lower()
        if "评分" in prompt or "score" in prompt_lower:
            return "评分：8/10\n1. 结构完整\n2. 论据充分"
        if "敏感信息" in prompt or "redact" in prompt_lower:
            return "无敏感信息"
        if "分析（每项一行简短回答）" in prompt:
            return "1. AI发展趋势\n2. 产业与技术进展\n3. 管理层\n4. executive"
        return "# AI发展趋势报告\n\n## 摘要\n- 行业继续增长。\n\n## 结论与建议\n- 持续跟踪基础设施与应用侧演进。"

    runtime = SimpleNamespace(
        llm_connector=_llm,
        kb_hub=_DummyHub(),
        policy_engine=_DummyPolicyEngine(),
        outbox=None,
        memory=None,
        evomap_observer=None,
        kb_registry=None,
        event_bus=None,
        model_router=None,
        writeback_service=None,
        routing_fabric=None,
        evomap_knowledge_db=None,
    )
    checkpoint_db = tmp_path / "advisor-checkpoint.db"
    conn = sqlite3.connect(checkpoint_db, check_same_thread=False)
    app = build_advisor_graph().compile(checkpointer=SqliteSaver(conn))
    try:
        with bind_runtime_services(runtime):
            result = app.invoke(
                {"user_message": "帮我写一篇关于AI发展趋势的报告", "trace_id": "trace-report-serialization"},
                config={"configurable": {"thread_id": "thread-report-serialization"}},
            )
    finally:
        conn.close()

    assert result["selected_route"] == "report"
    assert result["route_status"] != "error"
    assert "LLMConnector" not in str(result.get("route_result", {}))


def test_kb_probe_rejects_irrelevant_hits():
    """Hit count alone should not mark the KB as answerable."""

    class _DummyHub:
        def search(self, query, top_k=5):  # noqa: ANN001
            return [
                SimpleNamespace(artifact_id="a1", title="无关文档", snippet="这里在讲 Playwright anti-bot 策略。", score=9.2),
                SimpleNamespace(artifact_id="a2", title="另一个无关文档", snippet="这里在讲报告 review 流程。", score=8.7),
            ]

    result = kb_probe({"normalized_message": "什么是知识库检索增强？", "_runtime": SimpleNamespace(kb_hub=_DummyHub())})
    assert result["kb_has_answer"] is False
    assert result["kb_answerability"] < 0.45


def test_kb_probe_accepts_relevant_hits():
    """Relevant lexical overlap should still allow direct KB answers."""

    class _DummyHub:
        def search(self, query, top_k=5):  # noqa: ANN001
            return [
                SimpleNamespace(
                    artifact_id="a1",
                    title="知识库检索增强说明",
                    snippet="知识库检索增强会先检索相关文档，再把检索结果提供给模型生成 grounded answer。",
                    score=9.8,
                ),
            ]

    result = kb_probe({"normalized_message": "什么是知识库检索增强？", "_runtime": SimpleNamespace(kb_hub=_DummyHub())})
    assert result["kb_has_answer"] is True
    assert result["kb_answerability"] >= 0.45


def test_kb_writeback_and_record_uses_canonical_knowledge_plane(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeIngestService:
        def __init__(self, runtime):
            captured["runtime"] = runtime

        def ingest(self, items):
            captured["item"] = items[0]
            return SimpleNamespace(
                results=[
                    SimpleNamespace(
                        ok=True,
                        file_path="/tmp/research.md",
                        artifact_id="art-research-1",
                        accepted=True,
                        message="ingested",
                        quality_gate={"allowed": True},
                        graph_refs={
                            "knowledge_plane": "canonical_knowledge",
                            "write_path": "canonical_projected",
                            "status": "canonical_projected",
                            "graph_mode": "governed_projection",
                        },
                    )
                ]
            )

    monkeypatch.setattr("chatgptrest.cognitive.ingest_service.KnowledgeIngestService", _FakeIngestService)

    runtime = SimpleNamespace(
        writeback_service=object(),
        policy_engine=None,
        event_bus=None,
        evomap_knowledge_db=object(),
    )
    state: AdvisorState = {
        "user_message": "请输出一份行业研究报告",
        "session_id": "sess-graph-writeback",
    }

    with bind_runtime_services(runtime):
        record = graph_mod._kb_writeback_and_record(
            state=state,
            content="# Research\n\ncontent",
            artifact_name="research_trace",
            artifact_type="research",
            source_system="openmind_research",
            project_id="trace-research-1",
            knowledge_plane="canonical_knowledge",
        )

    assert record is not None
    assert record["success"] is True
    assert record["knowledge_plane"] == "canonical_knowledge"
    assert record["write_path"] == "canonical_projected"
    item = captured["item"]
    assert item.graph_extract is True
    assert item.session_id == "sess-graph-writeback"
    assert item.source_ref == "advisor://research/trace-research-1"


def test_execute_quick_ask_ignores_low_confidence_kb_chunks(monkeypatch):
    """Low-confidence kb_probe leftovers should not be reused as direct answer material."""
    from chatgptrest.advisor import simple_routes

    seen: dict[str, object] = {}

    def _fake_quick_ask(message, trace_id="", kb_search_fn=None):  # noqa: ANN001
        seen["hits"] = kb_search_fn(message, 5)
        return SimpleNamespace(
            answer="",
            status="no_answer",
            to_dict=lambda: {"answer": "", "status": "no_answer"},
        )

    monkeypatch.setattr(simple_routes, "quick_ask", _fake_quick_ask)
    runtime = SimpleNamespace(memory=None, kb_hub=None, evomap_knowledge_db=None)
    execute_quick_ask(
        {
            "normalized_message": "什么是知识库检索增强？",
            "kb_has_answer": False,
            "kb_top_chunks": [{"artifact_id": "a1", "title": "irrelevant", "snippet": "legacy snippet"}],
            "_runtime": runtime,
        }
    )
    assert seen["hits"] == []


def test_graph_state_is_lean(app):
    """State doesn't contain large text blobs (no >1KB fields)."""
    result = app.invoke({"user_message": "帮我写个报告"})
    import json
    serialized = json.dumps(result, default=str)
    # State should be small — a few KB at most
    assert len(serialized) < 5000
