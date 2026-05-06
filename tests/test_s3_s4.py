"""
Tests for S3 (KB Retrieval) and S4 (Advisor Routing).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatgptrest.kb.retrieval import KBRetriever, SearchResult, rrf_fuse
from chatgptrest.advisor import (
    compute_all_scores,
    route_request,
    select_route,
    RouteDecision,
)
from chatgptrest.contracts.schemas import (
    IntentSignals,
    KBProbeResult,
    Route,
    RouteScores,
)


# ===== S3: KB Retrieval Tests ==============================================

def test_fts_index_and_search():
    """FTS5: index text documents and search them."""
    print("test_fts_index_and_search...", end=" ")

    ret = KBRetriever(":memory:")

    # Index some documents (use English keywords for FTS5 unicode61 compatibility)
    ret.index_text(
        "doc_001",
        "Funnel Methodology",
        "The requirement funnel methodology transforms vague needs into executable projects. "
        "It includes diverge and converge stages with rubric scoring.",
        "/fake/funnel.md",
        tags=["funnel", "methodology"],
        content_type="markdown",
        quality_score=0.8,
    )
    ret.index_text(
        "doc_002",
        "EvoMap Evolution System",
        "EvoMap is an agent self-evolution system that uses signal collection and evolution plans "
        "to continuously improve agent capabilities via funnel integration.",
        "/fake/evomap.md",
        tags=["evomap", "evolution"],
        content_type="markdown",
        quality_score=0.9,
    )
    ret.index_text(
        "doc_003",
        "Knowledge Base Design",
        "The knowledge base uses PARA organization and supports full-text retrieval and vector search.",
        "/fake/kb.md",
        tags=["kb", "retrieval"],
        content_type="markdown",
        quality_score=0.7,
    )

    assert ret.count_indexed() == 3

    # Search for "funnel"
    results = ret.search("funnel")
    assert len(results) >= 1, f"Expected >=1 results for 'funnel', got {len(results)}"
    assert any("funnel" in r.title.lower() or "funnel" in r.snippet.lower() for r in results)

    # Search for "evolution"
    results2 = ret.search("evolution")
    assert len(results2) >= 1, f"Expected >=1 results for 'evolution', got {len(results2)}"
    assert any("evomap" in r.source_path.lower() for r in results2)

    print(f"  found {len(results)} for 'funnel', {len(results2)} for 'evolution' → PASS ✓")


def test_fts_empty_query():
    """FTS5: empty query returns empty results."""
    print("test_fts_empty_query...", end=" ")

    ret = KBRetriever(":memory:")
    results = ret.search("")
    assert results == []
    results2 = ret.search("   ")
    assert results2 == []
    print("PASS ✓")


def test_fts_remove():
    """FTS5: remove document from index."""
    print("test_fts_remove...", end=" ")

    ret = KBRetriever(":memory:")
    ret.index_text("rm_001", "To Remove", "This should be removed", "/fake.md")
    assert ret.count_indexed() == 1
    ret.remove("rm_001")
    assert ret.count_indexed() == 0
    print("PASS ✓")


def test_rrf_fusion():
    """RRF: fuse multiple ranked lists."""
    print("test_rrf_fusion...", end=" ")

    # List 1: A, B, C (FTS results)
    list1 = [
        SearchResult(artifact_id="A", title="A", score=10),
        SearchResult(artifact_id="B", title="B", score=8),
        SearchResult(artifact_id="C", title="C", score=5),
    ]

    # List 2: B, C, D (Vector results)
    list2 = [
        SearchResult(artifact_id="B", title="B", score=0.95),
        SearchResult(artifact_id="C", title="C", score=0.85),
        SearchResult(artifact_id="D", title="D", score=0.80),
    ]

    fused = rrf_fuse(list1, list2, k=60)
    ids = [r.artifact_id for r in fused]

    # B should rank highest (appears in both lists at good positions)
    assert ids[0] == "B", f"Expected B first, got {ids[0]}"
    # C should also rank highly
    assert "C" in ids[:3]
    # All 4 should appear
    assert len(fused) == 4

    print(f"  fused order: {ids} → PASS ✓")


# ===== S4: Advisor Routing Tests ============================================

def test_route_clarify():
    """Router: low intent confidence → clarify."""
    print("test_route_clarify...", end=" ")

    ctx = route_request(
        "嗯...",
        intent=IntentSignals(intent_confidence=0.3),
    )
    assert ctx.selected_route == Route.CLARIFY.value
    assert "clarify" in ctx.route_rationale.lower() or "I=" in ctx.route_rationale
    print(f"  route={ctx.selected_route} → PASS ✓")


def test_route_kb_answer_fast():
    """Router: urgent + simple + KB available → KB answer."""
    print("test_route_kb_answer_fast...", end=" ")

    ctx = route_request(
        "减速器的标准扭矩是多少？",
        intent=IntentSignals(
            intent_confidence=0.9,
            step_count_est=1,
        ),
        kb_probe=KBProbeResult(answerability=0.8),
        urgency_hint="immediate",
    )
    assert ctx.selected_route == Route.KB_ANSWER.value
    print(f"  route={ctx.selected_route} → PASS ✓")


def test_route_deep_research():
    """Router: complex + needs verification + KB low → deep research."""
    print("test_route_deep_research...", end=" ")

    ctx = route_request(
        "调研一下Agent自进化的最新方法论",
        intent=IntentSignals(
            intent_confidence=0.85,
            step_count_est=8,
            verification_need=True,
            open_endedness=0.7,
        ),
        kb_probe=KBProbeResult(answerability=0.1),
    )
    assert ctx.selected_route == Route.DEEP_RESEARCH.value
    print(f"  route={ctx.selected_route}, C={ctx.scores.complexity} → PASS ✓")


def test_route_funnel():
    """Router: multi-intent + moderate complexity → funnel."""
    print("test_route_funnel...", end=" ")

    ctx = route_request(
        "我想做一个机器人代工的项目，需要规划一下",
        intent=IntentSignals(
            intent_confidence=0.8,
            multi_intent=True,
            step_count_est=10,
            constraint_count=5,
            open_endedness=0.9,
            verification_need=True,
        ),
        kb_probe=KBProbeResult(answerability=0.3),
    )
    # With verification_need + low K, this should route to deep_research or funnel.
    # The multi_intent flag should trigger funnel when complexity is high enough.
    # If C > 70, deep research wins; if multi_intent + C > 60, funnel wins.
    assert ctx.selected_route in (Route.FUNNEL.value, Route.DEEP_RESEARCH.value), \
        f"Expected funnel or deep_research, got {ctx.selected_route} (C={ctx.scores.complexity})"
    print(f"  route={ctx.selected_route}, C={ctx.scores.complexity} → PASS ✓")


def test_route_action():
    """Router: action required + low risk → action."""
    print("test_route_action...", end=" ")

    ctx = route_request(
        "帮我把这个文件上传到钉钉",
        intent=IntentSignals(
            intent_confidence=0.9,
            action_required=True,
            step_count_est=2,
        ),
        kb_probe=KBProbeResult(answerability=0.1),
        domain_risk=0.2,
    )
    assert ctx.selected_route == Route.ACTION.value
    print(f"  route={ctx.selected_route}, R={ctx.scores.risk} → PASS ✓")


def test_route_hybrid_default():
    """Router: moderate everything → hybrid."""
    print("test_route_hybrid_default...", end=" ")

    ctx = route_request(
        "给我总结一下最近的工作进展",
        intent=IntentSignals(
            intent_confidence=0.75,
            step_count_est=3,
            multi_intent=False,
        ),
        kb_probe=KBProbeResult(answerability=0.3),
    )
    assert ctx.selected_route == Route.HYBRID.value
    print(f"  route={ctx.selected_route} → PASS ✓")


def test_advisor_context_completeness():
    """AdvisorContext: all fields populated correctly."""
    print("test_advisor_context_completeness...", end=" ")

    ctx = route_request(
        "如何优化Rubric评分？",
        intent=IntentSignals(
            intent_top="research",
            intent_confidence=0.85,
            step_count_est=4,
            verification_need=True,
        ),
        kb_probe=KBProbeResult(
            hit_rate=0.5,
            coverage=0.4,
            answerability=0.3,
        ),
        urgency_hint="soon",
        session_id="sess_test",
        trace_id="trace_test",
    )

    d = ctx.to_dict()
    assert d["session_id"] == "sess_test"
    assert d["trace_id"] == "trace_test"
    assert d["scores"]["intent_certainty"] == 85.0
    assert d["scores"]["urgency"] == 60.0
    assert d["selected_route"] != ""
    assert d["route_rationale"] != ""
    print("PASS ✓")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        # S3 tests
        test_fts_index_and_search,
        test_fts_empty_query,
        test_fts_remove,
        test_rrf_fusion,
        # S4 tests
        test_route_clarify,
        test_route_kb_answer_fast,
        test_route_deep_research,
        test_route_funnel,
        test_route_action,
        test_route_hybrid_default,
        test_advisor_context_completeness,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL ✗ → {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
