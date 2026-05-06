"""
Tests for the contracts package (S1: Unified Trace Events and Contracts).

Covers:
- Schema creation and serialization
- Event log CRUD operations
- Rubric computation and gate thresholds
"""

import json
import sys
import tempfile
from pathlib import Path

# Ensure chatgptrest package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatgptrest.contracts.schemas import (
    AdvisorContext,
    AnswerArtifact,
    Claim,
    EvidenceItem,
    EvidencePack,
    EventType,
    FunnelStage,
    IntentSignals,
    KBProbeResult,
    ProjectCard,
    Risk,
    Route,
    RouteScores,
    RubricSnapshot,
    SuccessMetric,
    Task,
    TraceEvent,
)
from chatgptrest.contracts.event_log import EventLogStore
from chatgptrest.contracts.rubric import (
    Gate,
    RubricInput,
    RubricResult,
    compute_rubric,
)


def test_schema_creation_and_serialization():
    """All schemas can be created and serialized to dict/JSON."""
    print("test_schema_creation_and_serialization...", end=" ")

    ctx = AdvisorContext(
        user_message="如何优化需求漏斗的收敛评分？",
        session_id="sess_001",
        intent=IntentSignals(
            intent_top="research",
            intent_confidence=0.85,
            multi_intent=False,
            verification_need=True,
        ),
        kb_probe=KBProbeResult(
            hit_rate=0.3,
            answerability=0.2,
        ),
        scores=RouteScores(
            intent_certainty=85,
            complexity=70,
            kb_score=20,
            urgency=40,
            risk=10,
        ),
        selected_route=Route.DEEP_RESEARCH.value,
    )

    d = ctx.to_dict()
    assert d["user_message"] == "如何优化需求漏斗的收敛评分？"
    assert d["intent"]["intent_confidence"] == 0.85
    assert d["scores"]["complexity"] == 70
    assert d["selected_route"] == "deep_research"

    # JSON round-trip
    j = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(j)
    assert parsed["scores"]["kb_score"] == 20
    print("PASS ✓")


def test_evidence_pack():
    """EvidencePack with claims and evidence items."""
    print("test_evidence_pack...", end=" ")

    pack = EvidencePack(
        trace_id="trace_001",
        provenance="deep_research",
        claims=[
            Claim(text="Rubric v1 should use 6 dimensions", criticality="high"),
            Claim(text="Gate A threshold is 55", criticality="medium"),
        ],
        evidence=[
            EvidenceItem(
                evidence_type="source",
                quality="measurement",
                quality_score=0.9,
                source_title="Funnel DR Answer",
                snippet="Define a 0-100 score...",
            )
        ],
    )

    d = pack.to_dict()
    assert len(d["claims"]) == 2
    assert d["claims"][0]["criticality"] == "high"
    assert d["evidence"][0]["quality_score"] == 0.9
    print("PASS ✓")


def test_project_card():
    """ProjectCard schema from Funnel DR."""
    print("test_project_card...", end=" ")

    card = ProjectCard(
        title="KB 入库流水线",
        problem_statement="散落知识需要系统化收集和索引",
        job_to_be_done="Finding any past research in seconds",
        success_metrics=[
            SuccessMetric(
                metric="检索召回率",
                target=">90%",
                measurement_method="20 known doc test set",
            )
        ],
        in_scope=["文件发现", "归一化", "去重", "索引"],
        out_of_scope=["多人协作", "外部API"],
        risks=[
            Risk(
                description="大量文件导致索引过慢",
                probability=0.3,
                impact=0.6,
                mitigation="增量索引 + 批处理",
                detection_signal="索引时间 > 10分钟",
            )
        ],
        tasks=[
            Task(
                title="文件发现扫描器",
                estimated_effort_hours=4,
                agent_role="developer",
            )
        ],
        rubric_snapshot=RubricSnapshot(total=82.5, gate="B"),
    )

    d = card.to_dict()
    assert d["title"] == "KB 入库流水线"
    assert len(d["success_metrics"]) == 1
    assert d["rubric_snapshot"]["gate"] == "B"

    j = json.dumps(d, ensure_ascii=False, indent=2)
    assert "文件发现扫描器" in j
    print("PASS ✓")


def test_trace_event_creation():
    """TraceEvent with CloudEvents envelope."""
    print("test_trace_event_creation...", end=" ")

    ev = TraceEvent(
        source="advisor/triage",
        event_type=EventType.ROUTE_SELECTED.value,
        trace_id="trace_abc",
        session_id="sess_001",
        data={
            "route": "deep_research",
            "scores": {"C": 70, "K": 20, "U": 40},
        },
    )

    d = ev.to_dict()
    assert d["source"] == "advisor/triage"
    assert d["data"]["route"] == "deep_research"
    assert ev.content_hash()  # non-empty hash
    print("PASS ✓")


def test_event_log_store_basic():
    """EventLogStore: append, query, count."""
    print("test_event_log_store_basic...", end=" ")

    store = EventLogStore(":memory:")

    # Append
    ev1 = TraceEvent(
        source="advisor/triage",
        event_type="route_selected",
        trace_id="t1",
        session_id="s1",
        data={"route": "funnel"},
    )
    eid = store.append(ev1)
    assert eid == ev1.event_id

    ev2 = TraceEvent(
        source="funnel/frame",
        event_type="workflow_step_finished",
        trace_id="t1",
        session_id="s1",
        data={"stage": "frame", "rubric_total": 62},
    )
    store.append(ev2)

    ev3 = TraceEvent(
        source="kb/query",
        event_type="kb_query_finished",
        trace_id="t2",
        session_id="s2",
        data={"hit_rate": 0.8},
    )
    store.append(ev3)

    # Count
    assert store.count(trace_id="t1") == 2
    assert store.count(trace_id="t2") == 1
    assert store.count(session_id="s1") == 2

    # Query by trace
    trace = store.get_trace("t1")
    assert len(trace) == 2
    assert trace[0].source == "advisor/triage"  # first chronologically

    # Query by type
    results = store.query(event_type="kb_query_finished")
    assert len(results) == 1
    assert results[0].data["hit_rate"] == 0.8

    print("PASS ✓")


def test_event_log_store_bulk():
    """EventLogStore: bulk append."""
    print("test_event_log_store_bulk...", end=" ")

    store = EventLogStore(":memory:")
    events = [
        TraceEvent(
            source=f"test/{i}",
            event_type="test_event",
            trace_id="bulk_trace",
            data={"index": i},
        )
        for i in range(100)
    ]
    count = store.append_many(events)
    assert count == 100
    assert store.count(trace_id="bulk_trace") == 100
    print("PASS ✓")


def test_event_log_store_persistence():
    """EventLogStore: data survives file reopen."""
    print("test_event_log_store_persistence...", end=" ")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store1 = EventLogStore(db_path)
    store1.append(TraceEvent(
        source="test",
        event_type="persist_test",
        trace_id="pt1",
        data={"value": 42},
    ))

    # Reopen
    store2 = EventLogStore(db_path)
    results = store2.query(trace_id="pt1")
    assert len(results) == 1
    assert results[0].data["value"] == 42

    Path(db_path).unlink(missing_ok=True)
    print("PASS ✓")


def test_rubric_below_gate_a():
    """Rubric: insufficient scores → no gate passed."""
    print("test_rubric_below_gate_a...", end=" ")

    inp = RubricInput(
        required_fields_total=10,
        required_fields_filled=3,
        agent_decision_agreement=0.3,
        rationale_overlap=0.1,
        iteration_stability=0.1,
        top_k_risks=5,
        risks_with_mitigation=1,
        has_in_scope=True,
        has_out_scope=False,
        has_assumptions=False,
        has_constraints=False,
        has_interfaces=False,
        has_test_plan=False,
        task_decomposition_quality=0.2,
        critical_claims=5,
        critical_claims_with_evidence=1,
        avg_evidence_quality=0.3,
    )

    result = compute_rubric(inp)
    assert result.gate == "none"
    assert result.total < 55
    print(f"  total={result.total}, gate={result.gate} → PASS ✓")


def test_rubric_gate_a():
    """Rubric: moderate scores → Gate A passed."""
    print("test_rubric_gate_a...", end=" ")

    inp = RubricInput(
        required_fields_total=10,
        required_fields_filled=6,
        agent_decision_agreement=0.6,
        rationale_overlap=0.4,
        iteration_stability=0.5,
        top_k_risks=5,
        risks_with_mitigation=3,
        has_in_scope=True,
        has_out_scope=True,
        has_assumptions=True,
        has_constraints=False,
        has_interfaces=False,
        total_requirement_words=100,
        ambiguous_word_count=3,
        has_test_plan=True,
        task_decomposition_quality=0.5,
        critical_claims=5,
        critical_claims_with_evidence=3,
        avg_evidence_quality=0.5,
    )

    result = compute_rubric(inp)
    assert result.gate == "A"
    assert 55 <= result.total < 80
    assert result.scope_boundary_clarity >= 0.5
    assert result.information_completeness >= 0.5
    print(f"  total={result.total}, gate={result.gate} → PASS ✓")


def test_rubric_gate_b():
    """Rubric: high scores → Gate B passed (ready for handoff)."""
    print("test_rubric_gate_b...", end=" ")

    inp = RubricInput(
        required_fields_total=10,
        required_fields_filled=9,
        agent_decision_agreement=0.9,
        rationale_overlap=0.8,
        iteration_stability=0.9,
        top_k_risks=5,
        risks_with_mitigation=4,
        has_in_scope=True,
        has_out_scope=True,
        has_assumptions=True,
        has_constraints=True,
        has_interfaces=True,
        total_requirement_words=200,
        ambiguous_word_count=1,
        has_test_plan=True,
        task_decomposition_quality=0.9,
        critical_claims=5,
        critical_claims_with_evidence=5,
        avg_evidence_quality=0.85,
    )

    result = compute_rubric(inp)
    assert result.gate == "B"
    assert result.total >= 80
    assert result.executability >= 0.8
    assert result.evidence_sufficiency >= 0.7
    assert result.risk_controllability >= 0.75
    print(f"  total={result.total}, gate={result.gate} → PASS ✓")


def test_rubric_all_dimensions_output():
    """Rubric: verify all dimension scores are in [0,1] and total in [0,100]."""
    print("test_rubric_all_dimensions_output...", end=" ")

    # Perfect scores
    inp = RubricInput(
        required_fields_total=10,
        required_fields_filled=10,
        agent_decision_agreement=1.0,
        rationale_overlap=1.0,
        iteration_stability=1.0,
        top_k_risks=3,
        risks_with_mitigation=3,
        has_in_scope=True,
        has_out_scope=True,
        has_assumptions=True,
        has_constraints=True,
        has_interfaces=True,
        has_test_plan=True,
        task_decomposition_quality=1.0,
        critical_claims=3,
        critical_claims_with_evidence=3,
        avg_evidence_quality=1.0,
    )

    result = compute_rubric(inp)
    assert 0 <= result.information_completeness <= 1
    assert 0 <= result.controversy_convergence <= 1
    assert 0 <= result.risk_controllability <= 1
    assert 0 <= result.scope_boundary_clarity <= 1
    assert 0 <= result.executability <= 1
    assert 0 <= result.evidence_sufficiency <= 1
    assert 0 <= result.total <= 100
    assert result.total == 100.0  # perfect scores should give 100
    print(f"  total={result.total} → PASS ✓")


def test_enums():
    """All enums work correctly."""
    print("test_enums...", end=" ")

    assert Route.DEEP_RESEARCH.value == "deep_research"
    assert FunnelStage.VALIDATE.value == "validate"
    assert EventType.ROUTE_SELECTED.value == "route_selected"
    assert Gate.B.value == "B"
    print("PASS ✓")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_schema_creation_and_serialization,
        test_evidence_pack,
        test_project_card,
        test_trace_event_creation,
        test_event_log_store_basic,
        test_event_log_store_bulk,
        test_event_log_store_persistence,
        test_rubric_below_gate_a,
        test_rubric_gate_a,
        test_rubric_gate_b,
        test_rubric_all_dimensions_output,
        test_enums,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL ✗ → {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
