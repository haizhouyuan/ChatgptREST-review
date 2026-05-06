from __future__ import annotations

from chatgptrest.kernel.skill_manager import get_canonical_registry


def test_capability_gap_recorder_aggregates_repeated_unmet(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    recorder = market_gate.get_capability_gap_recorder()

    unmet = [
        {
            "capability_id": "market_research",
            "reason": "bundle_missing",
            "required_by_task": "market_research",
            "candidate_bundles": ["research_core"],
            "candidate_skills": ["chatgptrest-call"],
        }
    ]

    first = recorder.promote_unmet(
        trace_id="trace-1",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        unmet_capabilities=unmet,
        suggested_agent="finbot",
    )
    second = recorder.promote_unmet(
        trace_id="trace-2",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        unmet_capabilities=unmet,
        suggested_agent="finbot",
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].gap_id == second[0].gap_id
    latest = recorder.fetch_gaps(status="open")
    assert latest[0].hit_count == 2
    assert latest[0].suggested_agent == "finbot"


def test_record_gap_legacy_wrapper_promotes_real_gap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    recorder = market_gate.get_capability_gap_recorder()

    gap = recorder.record_gap(
        "remote_storage",
        "maintagent",
        "sess-1",
        context={"task_type": "ops_maintenance", "platform": "openclaw", "reason": "missing"},
    )

    assert gap.capability_id == "remote_storage"
    assert gap.task_type == "ops_maintenance"
    assert recorder.fetch_gaps(status="open")[0].gap_id == gap.gap_id


def test_skill_signal_helpers_write_expected_evomap_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(tmp_path / "evomap.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_skill_platform_observer.cache_clear()
    market_gate.emit_skill_resolution_signals(
        trace_id="trace-skill",
        source="test.market_gate",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        recommended_skills=["chatgptrest-call"],
        recommended_bundles=["research_core"],
        unmet_capabilities=[{"capability_id": "market_research"}],
    )
    market_gate.emit_skill_execution_signals(
        trace_id="trace-skill",
        source="test.market_gate",
        agent_id="finbot",
        task_type="market_research",
        platform="openclaw",
        selected_skills=["chatgptrest-call"],
        selected_bundles=["research_core"],
        success=True,
    )

    observer = market_gate.get_skill_platform_observer()
    signal_types = [signal.signal_type for signal in observer.by_trace("trace-skill")]

    assert "skill.suggested" in signal_types
    assert "skill.executed" in signal_types
    assert "skill.succeeded" in signal_types
    assert "skill.helpful" in signal_types


def test_quarantine_gate_accepts_stable_skill_and_rejects_missing() -> None:
    from chatgptrest.kernel.market_gate import QuarantineGate

    gate = QuarantineGate(get_canonical_registry())

    assert gate.check_trust("chatgptrest-call") is True
    assert gate.check_trust("missing-skill") is False


def test_market_candidate_register_and_update_are_auditable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    recorder = market_gate.get_capability_gap_recorder()

    candidate = recorder.register_market_candidate(
        skill_id="community-skill",
        source_market="clawhub",
        source_uri="https://example.invalid/community-skill",
        capability_ids=["web_search"],
        summary="candidate under quarantine",
    )
    updated = recorder.update_market_candidate(
        candidate.candidate_id,
        status="evaluated",
        trust_level="smoke_passed",
        quarantine_state="approved",
        evidence_patch={"smoke": "passed"},
    )

    assert updated.status == "evaluated"
    assert updated.trust_level == "smoke_passed"
    assert updated.quarantine_state == "approved"
    assert updated.evidence["smoke"] == "passed"
    listed = recorder.list_market_candidates(status="evaluated")
    assert listed[0].candidate_id == candidate.candidate_id


def test_market_candidate_promotion_requires_quarantine_approval_and_closes_gap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(tmp_path / "evomap.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    market_gate.get_skill_platform_observer.cache_clear()
    recorder = market_gate.get_capability_gap_recorder()

    gap = recorder.promote_unmet(
        trace_id="trace-gap-open",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        unmet_capabilities=[
            {
                "capability_id": "web_search",
                "reason": "bundle_missing",
                "required_by_task": "market_research",
                "candidate_bundles": ["market_scan_quarantine"],
                "candidate_skills": ["community-web-search"],
            }
        ],
        suggested_agent="finbot",
    )[0]
    candidate = recorder.register_market_candidate(
        skill_id="community-web-search",
        source_market="clawhub",
        source_uri="https://example.invalid/community-web-search",
        capability_ids=["web_search"],
        linked_gap_id=gap.gap_id,
        summary="candidate awaiting evaluation",
    )

    try:
        recorder.promote_market_candidate(candidate.candidate_id, promoted_by="main", real_use_trace_id="trace-real")
    except ValueError as exc:
        assert str(exc) == "candidate_not_quarantine_approved"
    else:
        raise AssertionError("promotion should require quarantine approval")

    recorder.evaluate_market_candidate(
        candidate.candidate_id,
        platform="codex",
        smoke_passed=True,
        compatibility_passed=True,
        summary="smoke + compatibility passed",
    )
    promoted = recorder.promote_market_candidate(
        candidate.candidate_id,
        promoted_by="main",
        real_use_trace_id="trace-real",
        real_use_notes="used successfully in codex smoke",
    )

    assert promoted.status == "promoted"
    assert promoted.quarantine_state == "released"
    assert promoted.evidence["real_use_trace_id"] == "trace-real"
    closed = recorder.fetch_gaps(status="closed")
    assert closed[0].gap_id == gap.gap_id
    gap_signal_types = [signal.signal_type for signal in market_gate.get_skill_platform_observer().by_trace("trace-gap-open")]
    assert "capability.gap.opened" in gap_signal_types
    signal_types = [signal.signal_type for signal in market_gate.get_skill_platform_observer().by_trace("trace-real")]
    assert "skill.promoted" in signal_types


def test_market_candidate_deprecation_reopens_linked_gap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(tmp_path / "evomap.db"))

    import chatgptrest.kernel.market_gate as market_gate

    market_gate.get_capability_gap_recorder.cache_clear()
    market_gate.get_skill_platform_observer.cache_clear()
    recorder = market_gate.get_capability_gap_recorder()

    gap = recorder.promote_unmet(
        trace_id="trace-gap-open-2",
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
        unmet_capabilities=[{"capability_id": "document_rendering", "reason": "bundle_missing", "required_by_task": "market_research"}],
    )[0]
    candidate = recorder.register_market_candidate(
        skill_id="community-rendering",
        source_market="awesome-openclaw-skills",
        source_uri="https://example.invalid/community-rendering",
        capability_ids=["document_rendering"],
        linked_gap_id=gap.gap_id,
    )
    recorder.evaluate_market_candidate(
        candidate.candidate_id,
        platform="antigravity",
        smoke_passed=True,
        compatibility_passed=True,
    )
    recorder.promote_market_candidate(candidate.candidate_id, promoted_by="main", real_use_trace_id="trace-real-2")
    deprecated = recorder.deprecate_market_candidate(
        candidate.candidate_id,
        deprecated_by="maintagent",
        reason="regression after promotion",
        reopen_linked_gap=True,
    )

    assert deprecated.status == "deprecated"
    reopened = recorder.fetch_gaps(status="open")
    assert reopened[0].gap_id == gap.gap_id
    signal_types = [signal.signal_type for signal in market_gate.get_skill_platform_observer().by_trace("trace-real-2")]
    assert "skill.promoted" in signal_types
    assert "skill.deprecated" in signal_types
