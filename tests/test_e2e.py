"""
End-to-End Integration Tests (S8) + Model Routing Benchmarks (S9).

Tests the full pipeline:
  Raw input → Advisor route → Funnel/DeepResearch → ProjectCard/Answer → KB writeback → EvoMap signals

Includes the real-world fuzzy transcript test case.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatgptrest.contracts.schemas import (
    AdvisorContext,
    IntentSignals,
    KBProbeResult,
    Route,
    RouteScores,
    TraceEvent,
)
from chatgptrest.contracts.event_log import EventLogStore
from chatgptrest.contracts.rubric import compute_rubric, RubricInput
from chatgptrest.advisor import route_request
from chatgptrest.kb.retrieval import KBRetriever
from chatgptrest.kb.registry import ArtifactRegistry
from chatgptrest.workflows import DeepResearchWorkflow, extract_evidence_from_answer
from chatgptrest.workflows.funnel import FunnelEngine, extract_intent_from_text, classify_request_type
from chatgptrest.workflows.evomap import EvoMapEngine


# ====== S8: End-to-End Tests ================================================

def test_e2e_full_pipeline():
    """E2E: user message → advisor → funnel → project card → KB → evomap."""
    print("test_e2e_full_pipeline...", end=" ")

    # Setup
    store = EventLogStore(":memory:")
    retriever = KBRetriever(":memory:")
    funnel = FunnelEngine(event_log=store)
    evomap = EvoMapEngine(event_log=store)

    # Step 1: Route the request
    ctx = route_request(
        "我想做一个记录自己奖励的APP",
        intent=IntentSignals(
            intent_confidence=0.8,
            multi_intent=True,
            step_count_est=10,
            verification_need=True,
        ),
        kb_probe=KBProbeResult(answerability=0.1),
        trace_id="e2e_001",
        session_id="sess_e2e",
    )

    # Emit route event
    store.append(TraceEvent(
        source="advisor/triage",
        event_type="route_selected",
        trace_id="e2e_001",
        session_id="sess_e2e",
        data={"route": ctx.selected_route},
    ))

    # Step 2: Run through funnel
    state = funnel.run(
        "我想做一个记录自己奖励的APP，让孩子可以看到自己赚了多少钱，"
        "花了多少钱，还有运动打球的记录。这是他提出来的想法。",
        trace_id="e2e_001",
        session_id="sess_e2e",
    )

    # Verify funnel produced a project card
    assert state.project_card is not None, "Funnel should produce a ProjectCard"
    assert state.current_stage == "execute_learn"
    assert len(state.stage_history) == 9  # All 9 stages ran
    assert state.rubric_history  # Has rubric scores

    card = state.project_card
    assert card.title
    assert card.risks
    assert card.tasks
    assert card.rubric_snapshot.total > 0

    # Step 3: Index result in KB
    retriever.index_text(
        "funnel_e2e_001",
        card.title,
        json.dumps(card.to_dict(), ensure_ascii=False),
        tags=["funnel", "project_card"],
        quality_score=0.7,
    )

    # Emit KB write event
    store.append(TraceEvent(
        source="kb/write",
        event_type="kb_write_committed",
        trace_id="e2e_001",
        data={"artifact_id": "funnel_e2e_001"},
    ))

    # Step 4: EvoMap extracts signals
    signals = evomap.extract_session_signals("e2e_001")
    assert len(signals) > 0, "EvoMap should extract signals from trace"

    # Verify trace completeness
    trace = store.get_trace("e2e_001")
    assert len(trace) >= 10, f"Expected ≥10 trace events, got {len(trace)}"

    print(f"  card='{card.title[:30]}', rubric={card.rubric_snapshot.total}, "
          f"signals={len(signals)}, events={len(trace)} → PASS ✓")


def test_e2e_deep_research_flow():
    """E2E: advisor routes to deep research → evidence extraction → KB writeback."""
    print("test_e2e_deep_research_flow...", end=" ")

    store = EventLogStore(":memory:")
    retriever = KBRetriever(":memory:")
    dr = DeepResearchWorkflow(event_log=store, kb_retriever=retriever)

    # Route to deep research
    ctx = route_request(
        "调研Agent自进化的最新方法论",
        intent=IntentSignals(
            intent_confidence=0.85,
            step_count_est=6,
            verification_need=True,
        ),
        kb_probe=KBProbeResult(answerability=0.05),
    )
    assert ctx.selected_route == Route.DEEP_RESEARCH.value

    # Execute workflow
    state = dr.execute("Agent自进化的最新方法论有哪些？", context=ctx, trace_id="dr_001")
    assert state.status == "plan_ready"
    assert state.enhanced_prompt

    # Simulate receiving an answer
    fake_answer = """
# Agent 自进化方法论综述

## 1. 核心范式

**Reflexion 是最广泛使用的内环自进化方法**，通过错误反思来改进行为。

**EvoPrompt 将进化算法应用于 prompt 优化**，实现了20%的准确率提升。

## 2. 推荐方案

1. 内环使用 Reflexion 进行会话内学习
2. 中环使用 APE/EvoPrompt 优化 prompt
3. 外环使用 DPO 进行偏好对齐

参考: https://arxiv.org/abs/2310.example
"""
    state = dr.process_answer(state, fake_answer)
    assert state.status == "written_back"
    assert state.evidence_pack is not None
    assert len(state.evidence_pack.claims) > 0
    assert state.answer_artifact is not None

    # Verify KB has the research
    results = retriever.search("Reflexion")
    assert len(results) >= 1

    print(f"  claims={len(state.evidence_pack.claims)}, "
          f"evidence={len(state.evidence_pack.evidence)}, "
          f"kb_indexed=True → PASS ✓")


def test_e2e_real_transcript_funnel():
    """E2E: Real fuzzy voice transcript → Funnel → ProjectCard.

    This is THE key test: a 24-minute parenting consultation voice transcript
    that the system must process into a structured project card.
    """
    print("test_e2e_real_transcript_funnel...", end=" ")

    # Load real transcript
    transcript_path = Path(__file__).parent / "fixtures" / "fuzzy_transcript_parenting.txt"
    if not transcript_path.exists():
        print("SKIP (transcript fixture not found)")
        return

    transcript = transcript_path.read_text(encoding="utf-8")
    assert len(transcript) > 1000, "Transcript should be substantive"

    store = EventLogStore(":memory:")
    funnel = FunnelEngine(event_log=store)

    # Step 1: Route the raw transcript
    ctx = route_request(
        transcript[:500],  # First 500 chars for routing
        intent=IntentSignals(
            intent_confidence=0.5,  # Voice transcript → lower confidence
            multi_intent=True,
            step_count_est=5,
            open_endedness=0.8,
        ),
        kb_probe=KBProbeResult(answerability=0.1),
    )

    # Step 2: Run full funnel
    state = funnel.run(transcript, trace_id="real_001")

    # Verify results
    assert state.project_card is not None, "Should produce a ProjectCard from real transcript"
    assert state.current_stage == "execute_learn"

    # Check intent extraction quality
    intent = extract_intent_from_text(transcript)
    assert len(intent["explicit_requests"]) > 0, "Should find explicit requests in transcript"
    assert len(intent["emotions"]) > 0, "Should detect emotions in transcript"
    
    req_type = classify_request_type(transcript)
    assert req_type == "consultation", f"Expected 'consultation', got '{req_type}'"

    card = state.project_card
    assert card.title
    assert card.risks
    assert card.rubric_snapshot.total > 0

    # Print detailed results for inspection
    print(f"\n    Intent extraction:")
    print(f"      requests: {intent['explicit_requests'][:3]}")
    print(f"      emotions: {intent['emotions']}")
    print(f"      type: {req_type}")
    print(f"    ProjectCard:")
    print(f"      title: {card.title[:60]}")
    print(f"      rubric: {card.rubric_snapshot.total} (gate {card.rubric_snapshot.gate})")
    print(f"      risks: {len(card.risks)}")
    print(f"      tasks: {len(card.tasks)}")
    print(f"    Trace events: {store.count(trace_id='real_001')}")
    print(f"    → PASS ✓")


def test_e2e_evomap_anomaly_detection():
    """E2E: inject trace events with anomalies → EvoMap detects and proposes fixes."""
    print("test_e2e_evomap_anomaly_detection...", end=" ")

    store = EventLogStore(":memory:")

    # Inject trace events simulating a system with issues
    for i in range(20):
        # Most routes go to clarify (bad intent detection)
        store.append(TraceEvent(
            source="advisor/triage",
            event_type="route_selected",
            trace_id=f"anomaly_{i:03d}",
            data={"route": "clarify" if i < 12 else "kb_answer"},
        ))
        # Many workflow failures
        store.append(TraceEvent(
            source="workflow/engine",
            event_type="workflow_started",
            trace_id=f"anomaly_{i:03d}",
            data={"workflow": "funnel"},
        ))
        if i < 6:  # 30% failure rate
            store.append(TraceEvent(
                source="workflow/engine",
                event_type="workflow_step_failed",
                trace_id=f"anomaly_{i:03d}",
                data={"error": "timeout"},
            ))
        else:
            store.append(TraceEvent(
                source="workflow/engine",
                event_type="workflow_finished",
                trace_id=f"anomaly_{i:03d}",
                data={"status": "completed"},
            ))

    evomap = EvoMapEngine(event_log=store)
    agg = evomap.aggregate_signals()

    assert agg.signal_count > 0
    assert len(agg.anomalies) > 0, "Should detect anomalies"

    # Propose evolution
    plans = evomap.propose_evolution(agg)
    assert len(plans) > 0, "Should propose at least one evolution plan"

    # Check plan quality
    for plan in plans:
        assert plan.plan_id
        assert plan.rationale
        assert plan.rollback_plan

    print(f"  anomalies={agg.anomalies}, plans={len(plans)} → PASS ✓")


def test_e2e_trace_propagation():
    """E2E: verify trace_id propagates through the entire pipeline."""
    print("test_e2e_trace_propagation...", end=" ")

    store = EventLogStore(":memory:")
    funnel = FunnelEngine(event_log=store)

    state = funnel.run(
        "测试trace传播",
        trace_id="propagation_test_123",
    )

    trace = store.get_trace("propagation_test_123")
    assert len(trace) > 5, f"Expected >5 events, got {len(trace)}"

    # All events should have the same trace_id
    for event in trace:
        assert event.trace_id == "propagation_test_123", \
            f"Event {event.event_type} has wrong trace_id: {event.trace_id}"

    # Should have workflow_started and workflow_finished
    event_types = {e.event_type for e in trace}
    assert "workflow_started" in event_types
    assert "workflow_finished" in event_types

    print(f"  {len(trace)} events, all with correct trace_id → PASS ✓")


# ====== S9: Model Routing Benchmarks ========================================

def test_s9_routing_accuracy_matrix():
    """S9: Verify routing accuracy across synthetic test cases."""
    print("test_s9_routing_accuracy_matrix...", end=" ")

    test_cases = [
        # (description, intent_signals, expected_routes, urgency)
        (
            "简单问答",
            IntentSignals(intent_confidence=0.95, step_count_est=1),
            KBProbeResult(answerability=0.9),
            "immediate",
            {Route.KB_ANSWER.value},
        ),
        (
            "意图模糊",
            IntentSignals(intent_confidence=0.2),
            KBProbeResult(answerability=0.5),
            "whenever",
            {Route.CLARIFY.value},
        ),
        (
            "深度调研",
            IntentSignals(
                intent_confidence=0.85,
                step_count_est=8,
                verification_need=True,
            ),
            KBProbeResult(answerability=0.1),
            "whenever",
            {Route.DEEP_RESEARCH.value},
        ),
        (
            "执行操作",
            IntentSignals(
                intent_confidence=0.9,
                action_required=True,
                step_count_est=2,
            ),
            KBProbeResult(answerability=0.1),
            "whenever",
            {Route.ACTION.value},
        ),
        (
            "默认混合",
            IntentSignals(
                intent_confidence=0.7,
                step_count_est=3,
            ),
            KBProbeResult(answerability=0.3),
            "whenever",
            {Route.HYBRID.value},
        ),
    ]

    correct = 0
    total = len(test_cases)

    for desc, intent, kb_probe, urgency, expected_routes in test_cases:
        ctx = route_request(
            desc,
            intent=intent,
            kb_probe=kb_probe,
            urgency_hint=urgency,
        )
        if ctx.selected_route in expected_routes:
            correct += 1
        else:
            print(f"\n    MISMATCH: '{desc}' → got {ctx.selected_route}, "
                  f"expected {expected_routes}")

    accuracy = correct / total
    assert accuracy >= 0.8, f"Routing accuracy {accuracy:.0%} below 80% threshold"
    print(f"  accuracy={accuracy:.0%} ({correct}/{total}) → PASS ✓")


def test_s9_routing_speed():
    """S9: Verify routing decision speed (should be <10ms)."""
    print("test_s9_routing_speed...", end=" ")

    import time

    iterations = 100
    start = time.monotonic()
    for _ in range(iterations):
        route_request(
            "测试路由速度",
            intent=IntentSignals(intent_confidence=0.8, step_count_est=5),
            kb_probe=KBProbeResult(answerability=0.5),
        )
    elapsed = (time.monotonic() - start) * 1000  # ms
    avg_ms = elapsed / iterations

    assert avg_ms < 10, f"Average routing time {avg_ms:.2f}ms exceeds 10ms"
    print(f"  avg={avg_ms:.3f}ms over {iterations} iterations → PASS ✓")


def test_s9_funnel_speed():
    """S9: Verify funnel execution speed for short inputs."""
    print("test_s9_funnel_speed...", end=" ")

    import time

    funnel = FunnelEngine()
    start = time.monotonic()
    state = funnel.run("我想做一个简单的APP")
    elapsed = (time.monotonic() - start) * 1000

    assert elapsed < 100, f"Funnel execution {elapsed:.0f}ms exceeds 100ms"
    assert state.project_card is not None
    print(f"  time={elapsed:.1f}ms → PASS ✓")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        # S8 E2E tests
        test_e2e_full_pipeline,
        test_e2e_deep_research_flow,
        test_e2e_real_transcript_funnel,
        test_e2e_evomap_anomaly_detection,
        test_e2e_trace_propagation,
        # S9 benchmarks
        test_s9_routing_accuracy_matrix,
        test_s9_routing_speed,
        test_s9_funnel_speed,
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
    print(f"S8-S9 Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
