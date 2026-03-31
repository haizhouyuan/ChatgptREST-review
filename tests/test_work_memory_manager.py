from __future__ import annotations

from chatgptrest.kernel.memory_manager import MemoryManager
from chatgptrest.kernel.work_memory_manager import WorkMemoryManager
from chatgptrest.kernel.work_memory_policy import load_work_memory_governance


def test_work_memory_manager_writes_decision_ledger_into_episodic() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="decision_ledger",
        title="Freeze baseline",
        content="Freeze the new cost baseline for the current project.",
        summary="Freeze the new cost baseline.",
        payload={
            "decision_id": "dec-001",
            "statement": "Freeze the new cost baseline.",
            "domain": "planning",
            "review_status": "approved",
        },
        source_ref="doc://decision-freeze",
        source_system="advisor_agent",
        source_agent="advisor",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-1",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    record = memory.get_by_record_id(result.record_id)
    assert result.ok is True
    assert result.tier == "episodic"
    assert result.review_status == "approved"
    assert result.active is True
    assert record is not None
    assert record.category == "decision_ledger"
    assert record.value["kind"] == "decision_ledger"
    assert record.value["schema_version"] == "v1"
    assert result.governance["approved_by_policy"] is True


def test_work_memory_manager_blocks_missing_source_refs() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="handoff",
        title="handoff",
        content="Continue with the retrieval tests.",
        summary="Continue with the retrieval tests.",
        payload={
            "handoff_id": "handoff-001",
            "from_agent": "codex",
            "from_session": "sess-1",
            "current_situation": "Phase 2 is almost done.",
            "next_pickup": "Finish Phase 3.",
        },
        source_ref="",
        source_system="advisor_agent",
        source_agent="advisor",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-1",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    assert result.ok is False
    assert result.blocked_by == ["missing_source_refs"]
    assert result.promotion_state == "blocked_validation"


def test_work_memory_manager_updates_supersede_chain() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    first = manager.write_from_capture(
        category="decision_ledger",
        title="Old decision",
        content="Keep the old conclusion active.",
        summary="Old decision",
        payload={
            "decision_id": "dec-old",
            "statement": "Keep the old conclusion active.",
            "domain": "planning",
            "review_status": "approved",
            "valid_from": "2026-03-30T00:00:00+00:00",
        },
        source_ref="doc://old",
        source_system="advisor_agent",
        source_agent="advisor",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-old",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )
    second = manager.write_from_capture(
        category="decision_ledger",
        title="New decision",
        content="Replace the old conclusion with the new one.",
        summary="New decision",
        payload={
            "decision_id": "dec-new",
            "statement": "Replace the old conclusion with the new one.",
            "domain": "planning",
            "review_status": "approved",
            "valid_from": "2026-03-31T00:00:00+00:00",
            "supersedes_decision_id": "dec-old",
        },
        source_ref="doc://new",
        source_system="advisor_agent",
        source_agent="advisor",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-new",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    old_record = memory.get_by_key("dec-old")
    new_record = memory.get_by_key("dec-new")
    assert first.ok is True
    assert second.ok is True
    assert second.superseded_record_id == first.record_id
    assert old_record is not None
    assert new_record is not None
    assert old_record.value["valid_to"] == "2026-03-31T00:00:00+00:00"
    assert old_record.value["superseded_by"] == "dec-new"
    assert old_record.value["review_status"] == "superseded"


def test_work_memory_manager_reports_promotion_failure() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="active_project",
        title="project",
        content="Project status changed.",
        summary="Project status changed.",
        payload={
            "project_id": "prj-001",
            "name": "Alpha",
            "phase": "P1",
            "status": "active",
            "review_status": "approved",
        },
        source_ref="doc://project",
        source_system="advisor_agent",
        source_agent="advisor",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-1",
        confidence=0.2,
        provenance_quality="complete",
        identity_gaps=[],
    )

    record = memory.get_by_record_id(result.record_id)
    assert result.ok is False
    assert result.blocked_by == ["promotion"]
    assert result.tier == "staging"
    assert record is not None
    assert record.tier == "staging"
    assert result.governance["approved_by_policy"] is True


def test_work_memory_manager_coerces_untrusted_approved_status_to_staged() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="active_project",
        title="project",
        content="Project status changed.",
        summary="Project status changed.",
        payload={
            "project_id": "prj-002",
            "name": "Beta",
            "phase": "P2",
            "status": "active",
            "review_status": "approved",
        },
        source_ref="doc://project-beta",
        source_system="unknown-system",
        source_agent="unknown-system",
        role_id="planning",
        session_id="sess-1",
        account_id="acc-1",
        thread_id="thread-1",
        trace_id="trace-2",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    record = memory.get_by_record_id(result.record_id)
    assert result.ok is True
    assert result.review_status == "staged"
    assert result.active is False
    assert result.promotion_state == "promoted_requires_review"
    assert result.governance["approved_by_policy"] is False
    assert "source_not_allowlisted" in result.governance["reasons"]
    assert record is not None
    assert record.value["review_status"] == "staged"


def test_work_memory_manager_retrieves_cross_session_active_context_by_account_role() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    project = manager.write_from_capture(
        category="active_project",
        title="Project state",
        content="Project moved into execution.",
        summary="Project moved into execution.",
        payload={
            "project_id": "prj-001",
            "name": "Alpha",
            "phase": "execution",
            "status": "active",
            "review_status": "approved",
        },
        source_ref="doc://project-state",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-codex",
        account_id="acct-1",
        thread_id="thread-codex",
        trace_id="trace-project",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )
    handoff = manager.write_from_capture(
        category="handoff",
        title="Handoff",
        content="Pick up the project review.",
        summary="Pick up the project review.",
        payload={
            "handoff_id": "handoff-001",
            "from_agent": "codex",
            "from_session": "sess-codex",
            "current_situation": "Execution has started.",
            "next_pickup": "Validate supplier readiness.",
            "review_status": "approved",
        },
        source_ref="doc://handoff",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-codex",
        account_id="acct-1",
        thread_id="thread-codex",
        trace_id="trace-handoff",
        confidence=0.95,
        provenance_quality="complete",
        identity_gaps=[],
    )

    text, metadata = manager.build_active_context(
        query="What is active right now?",
        session_id="sess-antigravity",
        account_id="acct-1",
        agent_id="antigravity",
        role_id="planning",
        thread_id="thread-antigravity",
    )

    assert project.ok is True
    assert handoff.ok is True
    assert "### Active Project Map" in text
    assert "Alpha" in text
    assert "### Recent Handoff" in text
    assert metadata["scope_hits"]["active_project"] == "account_role"
    assert metadata["scope_hits"]["handoff"] == "account_role"
    assert metadata["identity_gaps"] == []


def test_work_memory_manager_missing_thread_degrades_but_keeps_account_scope() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    manager.write_from_capture(
        category="decision_ledger",
        title="Decision",
        content="Freeze the current baseline.",
        summary="Freeze the current baseline.",
        payload={
            "decision_id": "dec-001",
            "statement": "Freeze the current baseline.",
            "domain": "planning",
            "review_status": "approved",
        },
        source_ref="doc://decision",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-codex",
        account_id="acct-1",
        thread_id="thread-codex",
        trace_id="trace-decision",
        confidence=0.95,
        provenance_quality="complete",
        identity_gaps=[],
    )

    text, metadata = manager.build_active_context(
        query="What is still active?",
        session_id="sess-2",
        account_id="acct-1",
        agent_id="claude_code",
        role_id="planning",
        thread_id="",
    )

    assert "### Decision Ledger" in text
    assert "dec-001" in text
    assert metadata["scope_hits"]["decision_ledger"] == "account_role"
    assert metadata["identity_gaps"] == ["missing_thread_id"]


def test_work_memory_manager_prefers_query_matching_project_within_scope() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    manager.write_from_capture(
        category="active_project",
        title="Beta project",
        content="Beta vendor migration now needs procurement approval.",
        summary="Beta migration blocked by procurement.",
        payload={
            "project_id": "prj-beta",
            "name": "Beta Project",
            "phase": "execution",
            "status": "active",
            "blockers": ["procurement approval"],
            "review_status": "approved",
        },
        source_ref="doc://beta-project",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-beta",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )
    manager.write_from_capture(
        category="active_project",
        title="Alpha project",
        content="Alpha rollout remains active and was updated more recently.",
        summary="Alpha rollout remains active.",
        payload={
            "project_id": "prj-alpha",
            "name": "Alpha Project",
            "phase": "execution",
            "status": "active",
            "blockers": ["none"],
            "review_status": "approved",
        },
        source_ref="doc://alpha-project",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-alpha",
        confidence=0.95,
        provenance_quality="complete",
        identity_gaps=[],
    )

    text, metadata = manager.build_active_context(
        query="beta procurement blocker",
        session_id="sess-2",
        account_id="acct-1",
        agent_id="antigravity",
        role_id="planning",
        thread_id="thread-2",
        item_limit=1,
    )

    assert "Beta Project" in text
    assert "Alpha Project" not in text
    assert metadata["query_sensitive"] is True


def test_work_memory_manager_query_window_can_surface_older_relevant_project() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    manager.write_from_capture(
        category="active_project",
        title="FZ4 project",
        content="FZ4 current baseline remains the minimum investment plan.",
        summary="FZ4 minimum investment baseline.",
        payload={
            "project_id": "prj-fz4",
            "name": "两轮车车身量产线规划（FZ4 最小投入）",
            "phase": "G1 执行版",
            "status": "active_conditional",
            "blockers": ["客户边界 A/B/C 未冻结"],
            "next_steps": ["维持最小投入方案"],
            "review_status": "approved",
        },
        source_ref="doc://fz4-project",
        source_system="advisor_agent",
        source_agent="codex",
        role_id="planning",
        session_id="sess-old",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-fz4",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    for idx in range(8):
        manager.write_from_capture(
            category="active_project",
            title=f"Recent project {idx}",
            content=f"Recent generic planning project {idx}.",
            summary=f"Recent generic planning project {idx}.",
            payload={
                "project_id": f"prj-recent-{idx}",
                "name": f"Recent Project {idx}",
                "phase": "execution",
                "status": "active",
                "blockers": ["none"],
                "review_status": "approved",
            },
            source_ref=f"doc://recent-project-{idx}",
            source_system="advisor_agent",
            source_agent="codex",
            role_id="planning",
            session_id=f"sess-recent-{idx}",
            account_id="acct-1",
            thread_id="thread-1",
            trace_id=f"trace-recent-{idx}",
            confidence=0.8,
            provenance_quality="complete",
            identity_gaps=[],
        )

    text, metadata = manager.build_active_context(
        query="FZ4 最小投入 当前唯一口径",
        session_id="sess-2",
        account_id="acct-1",
        agent_id="claude_code",
        role_id="planning",
        thread_id="thread-2",
        item_limit=1,
    )

    assert "FZ4 最小投入" in text
    assert "Recent Project" not in text
    assert metadata["query_sensitive"] is True


def test_work_memory_manager_can_read_governance_policy_from_config(tmp_path) -> None:
    config_path = tmp_path / "work_memory_governance.yaml"
    config_path.write_text(
        (
            "version: 2\n"
            "approval:\n"
            "  policy_name: test_policy\n"
            "  allow_approved_sources:\n"
            "    - reviewer-bot\n"
            "  require_identity_fields:\n"
            "    - account_id\n"
            "  require_provenance_quality: complete\n"
        ),
        encoding="utf-8",
    )

    policy = load_work_memory_governance(config_path)
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory, governance_policy=policy)

    result = manager.write_from_capture(
        category="decision_ledger",
        title="Decision",
        content="Promote only from reviewer-bot.",
        summary="Promote only from reviewer-bot.",
        payload={
            "decision_id": "dec-config",
            "statement": "Promote only from reviewer-bot.",
            "domain": "planning",
            "review_status": "approved",
        },
        source_ref="doc://config-policy",
        source_system="advisor_agent",
        source_agent="advisor_agent",
        role_id="planning",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-config",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )

    assert policy.approval_policy == "test_policy"
    assert result.review_status == "staged"
    assert result.governance["approval_policy"] == "test_policy"
    assert "source_not_allowlisted" in result.governance["reasons"]


def test_work_memory_manager_preserves_import_metadata_and_audit() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)

    result = manager.write_from_capture(
        category="active_project",
        title="Imported project",
        content="Imported from planning backfill manifest.",
        summary="Imported project summary.",
        payload={
            "project_id": "PRJ-IMPORT-1",
            "name": "Imported Alpha",
            "phase": "execution",
            "status": "active",
            "review_status": "approved",
        },
        source_ref="00_入口/项目台账.md",
        source_system="manual_review",
        source_agent="manual_review",
        role_id="planning",
        session_id="wm-import::acct-1::planning::manifest-1",
        account_id="acct-1",
        thread_id="wm-import::planning::active_project::manifest-1",
        trace_id="wm-import-seed-1",
        confidence=0.95,
        provenance_quality="complete",
        identity_gaps=[],
        import_metadata={
            "manifest_id": "manifest-1",
            "seed_id": "AP-001",
            "import_gate": "ready",
            "conditions": ["still conditional"],
        },
        import_audit={
            "mode": "execute",
            "source_identity": "manual_review",
        },
    )

    record = memory.get_by_record_id(result.record_id)
    assert result.ok is True
    assert result.governance["approved_by_policy"] is True
    assert record is not None
    assert record.value["import_metadata"]["manifest_id"] == "manifest-1"
    assert record.value["import_metadata"]["seed_id"] == "AP-001"
    assert record.value["import_audit"]["mode"] == "execute"
    assert record.value["import_audit"]["source_identity"] == "manual_review"


def test_work_memory_manager_replay_is_idempotent_with_stable_import_identity() -> None:
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)
    kwargs = {
        "category": "decision_ledger",
        "title": "Imported decision",
        "content": "Imported from planning backfill manifest.",
        "summary": "Imported decision summary.",
        "payload": {
            "decision_id": "DCL-REPLAY-1",
            "statement": "Keep the current rollout baseline.",
            "domain": "planning",
            "review_status": "approved",
            "confidence": 0.9,
            "valid_from": "2026-03-30T00:00:00+00:00",
        },
        "source_ref": "00_入口/项目台账.md",
        "source_system": "manual_review",
        "source_agent": "manual_review",
        "role_id": "planning",
        "session_id": "wm-import::acct-1::planning::manifest-1",
        "account_id": "acct-1",
        "thread_id": "wm-import::planning::decision_ledger::manifest-1",
        "trace_id": "wm-import-dcl-replay-1",
        "confidence": 0.9,
        "provenance_quality": "complete",
        "identity_gaps": [],
        "import_metadata": {
            "manifest_id": "manifest-1",
            "seed_id": "DCL-001",
            "import_gate": "ready",
        },
    }

    first = manager.write_from_capture(**kwargs)
    second = manager.write_from_capture(**kwargs)

    records = memory.get_episodic(
        category="decision_ledger",
        account_id="acct-1",
        role_id="planning",
        session_id="wm-import::acct-1::planning::manifest-1",
        thread_id="wm-import::planning::decision_ledger::manifest-1",
    )
    assert first.ok is True
    assert second.ok is True
    assert second.duplicate is True
    assert first.record_id == second.record_id
    assert len(records) == 1
