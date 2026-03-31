from __future__ import annotations

import json

import pytest

from chatgptrest.advisor.runtime import get_advisor_runtime, reset_advisor_runtime
from chatgptrest.cognitive.context_service import ContextResolveOptions, ContextResolver
from chatgptrest.kernel.memory_manager import MemoryRecord, MemorySource, MemoryTier, SourceType
from chatgptrest.kernel.work_memory_importer import WorkMemoryImporter


@pytest.fixture(autouse=True)
def _isolated_runtime() -> None:
    reset_advisor_runtime()
    yield
    reset_advisor_runtime()


def _seed_runtime() -> None:
    runtime = get_advisor_runtime()
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="active_project",
            key="prj-001",
            value={
                "kind": "active_project",
                "schema_version": "v1",
                "object_id": "prj-001",
                "project_id": "prj-001",
                "name": "Alpha Project",
                "phase": "execution",
                "status": "active",
                "blockers": ["budget freeze"],
                "next_steps": ["confirm supplier"],
                "source_refs": ["doc://project"],
                "review_status": "approved",
                "valid_from": "2026-03-30T00:00:00+00:00",
            },
            confidence=0.9,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="advisor",
                role="planning",
                session_id="sess-1",
                account_id="acct-1",
                thread_id="thread-1",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed active project",
    )
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="decision_ledger",
            key="dec-001",
            value={
                "kind": "decision_ledger",
                "schema_version": "v1",
                "object_id": "dec-001",
                "decision_id": "dec-001",
                "statement": "Freeze the current cost baseline.",
                "domain": "planning",
                "confidence": 0.95,
                "source_refs": ["doc://decision"],
                "review_status": "approved",
                "valid_from": "2026-03-30T00:00:00+00:00",
            },
            confidence=0.95,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="advisor",
                role="planning",
                session_id="sess-1",
                account_id="acct-1",
                thread_id="thread-1",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed active decision",
    )
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="captured_memory",
            key="remembered-guidance",
            value={
                "title": "Remembered guidance",
                "summary": "Keep answers short and decision-first.",
                "content": "Keep answers short and decision-first.",
            },
            confidence=0.85,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="advisor",
                role="planning",
                session_id="sess-1",
                account_id="acct-1",
                thread_id="thread-1",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed captured memory",
    )
    runtime.kb_hub.index_document(
        artifact_id="kb-generic",
        title="Generic planning note",
        content="Generic planning knowledge block for retrieval order regression tests.",
        source_path="/tmp/generic-planning.md",
        content_type="markdown",
        quality_score=0.9,
        auto_embed=False,
    )


def _write_import_manifest(tmp_path, *, manifest_id: str, object_type: str, entries: list[dict]) -> str:  # noqa: ANN001
    path = tmp_path / f"{manifest_id}.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": manifest_id,
                "schema_version": "planning-backfill-import-manifest-v1",
                "object_type": object_type,
                "generated_at": "2026-03-30",
                "source_repo": "planning",
                "contract_basis": ["docs/2026-03-30_长期工作记忆_v1_总体开发计划.md"],
                "normalization_rules_ref": "docs/backfill/work_memory_import_normalization_rules_v1.md",
                "entry_count": len(entries),
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(path)


def test_context_resolver_prioritizes_active_context_before_captured_memory() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="What changed in the current planning project?",
            session_id="sess-1",
            account_id="acct-1",
            agent_id="advisor",
            role_id="planning",
            thread_id="thread-1",
            sources=("memory", "knowledge", "policy"),
        )
    )

    assert result.ok is True
    assert "## Active Context" in result.prompt_prefix
    assert "### Active Project Map" in result.prompt_prefix
    assert "### Decision Ledger" in result.prompt_prefix
    assert "## Remembered Guidance" in result.prompt_prefix
    assert result.prompt_prefix.index("## Active Context") < result.prompt_prefix.index("## Remembered Guidance")
    assert any(block.source_type == "work_memory_active" for block in result.context_blocks)


def test_context_resolver_keeps_planning_pack_priority_for_planning_role(monkeypatch) -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    resolver = ContextResolver(runtime)

    def _fake_search_planning_runtime_pack(query: str, top_k: int = 5):  # noqa: ANN001
        return [
            {
                "artifact_id": "planning-pack-1",
                "title": "Planning Pack",
                "snippet": "Approved planning runtime pack guidance.",
                "score": 0.99,
                "planning_pack_meta": {"pack_version": "v1", "review_domain": "planning"},
            }
        ]

    monkeypatch.setattr(
        "chatgptrest.evomap.knowledge.planning_runtime_pack_search.search_planning_runtime_pack",
        _fake_search_planning_runtime_pack,
    )

    result = resolver.resolve(
        ContextResolveOptions(
            query="approved planning runtime pack guidance",
            session_id="sess-1",
            account_id="acct-1",
            agent_id="advisor",
            role_id="planning",
            thread_id="thread-1",
            sources=("memory", "knowledge"),
        )
    )

    assert result.ok is True
    assert "## Planning Runtime Pack" in result.prompt_prefix
    assert "## Active Context" in result.prompt_prefix
    assert result.prompt_prefix.index("## Planning Runtime Pack") < result.prompt_prefix.index("## Active Context")


def test_context_resolver_marks_partial_work_memory_identity_as_degraded() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="What is the active project context?",
            session_id="sess-1",
            agent_id="advisor",
            role_id="planning",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert result.degraded is True
    assert "work_memory_identity_partial" in result.degraded_sources
    assert set(result.metadata["work_memory_identity_gaps"]) == {"missing_account_id", "missing_thread_id"}


def test_context_resolver_retrieves_active_context_across_sessions_and_agents() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="What is the current project state?",
            session_id="sess-antigravity",
            account_id="acct-1",
            agent_id="antigravity",
            role_id="planning",
            thread_id="thread-antigravity",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert "## Active Context" in result.prompt_prefix
    assert "Alpha Project" in result.prompt_prefix
    assert "Freeze the current cost baseline." in result.prompt_prefix
    assert result.metadata["work_memory_identity_gaps"] == []


def test_context_resolver_missing_thread_degrades_without_losing_account_scoped_context() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="What is the current project state?",
            session_id="sess-antigravity",
            account_id="acct-1",
            agent_id="antigravity",
            role_id="planning",
            thread_id="",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert result.degraded is True
    assert "work_memory_identity_partial" in result.degraded_sources
    assert "Alpha Project" in result.prompt_prefix
    assert result.metadata["work_memory_identity_gaps"] == ["missing_thread_id"]


def test_context_resolver_prefers_query_matching_active_project_within_scope() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="active_project",
            key="prj-002",
            value={
                "kind": "active_project",
                "schema_version": "v1",
                "object_id": "prj-002",
                "project_id": "prj-002",
                "name": "Beta Project",
                "phase": "execution",
                "status": "active",
                "blockers": ["procurement approval"],
                "next_steps": ["finish supplier onboarding"],
                "source_refs": ["doc://beta-project"],
                "review_status": "approved",
                "valid_from": "2026-03-29T00:00:00+00:00",
            },
            confidence=0.91,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="codex",
                role="planning",
                session_id="sess-older",
                account_id="acct-1",
                thread_id="thread-older",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed beta active project",
    )
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="beta procurement blocker",
            session_id="sess-antigravity",
            account_id="acct-1",
            agent_id="antigravity",
            role_id="planning",
            thread_id="thread-antigravity",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert result.metadata["work_memory_identity_gaps"] == []
    assert result.prompt_prefix.index("Beta Project") < result.prompt_prefix.index("Alpha Project")


def test_context_resolver_query_window_can_surface_older_relevant_imported_project() -> None:
    _seed_runtime()
    runtime = get_advisor_runtime()
    for idx in range(8):
        runtime.memory.stage_and_promote(
            MemoryRecord(
                category="active_project",
                key=f"recent-{idx}",
                value={
                    "kind": "active_project",
                    "schema_version": "v1",
                    "object_id": f"recent-{idx}",
                    "project_id": f"recent-{idx}",
                    "name": f"Recent Project {idx}",
                    "phase": "execution",
                    "status": "active",
                    "blockers": ["none"],
                    "source_refs": [f"doc://recent-{idx}"],
                    "review_status": "approved",
                    "valid_from": "2026-03-30T00:00:00+00:00",
                },
                confidence=0.85,
                source=MemorySource(
                    type=SourceType.USER_INPUT.value,
                    agent="manual_review",
                    role="planning",
                    session_id=f"recent-session-{idx}",
                    account_id="acct-1",
                    thread_id="thread-1",
                ).to_dict(),
            ),
            MemoryTier.EPISODIC,
            reason="seed recent distractor",
        )

    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="active_project",
            key="prj-fz4",
            value={
                "kind": "active_project",
                "schema_version": "v1",
                "object_id": "prj-fz4",
                "project_id": "prj-fz4",
                "name": "两轮车车身量产线规划（FZ4 最小投入）",
                "phase": "G1 执行版",
                "status": "active_conditional",
                "blockers": ["客户边界 A/B/C 未冻结"],
                "next_steps": ["维持最小投入方案"],
                "source_refs": ["00_入口/项目台账.md"],
                "review_status": "approved",
                "valid_from": "2026-03-10T00:00:00+00:00",
            },
            confidence=0.9,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="manual_review",
                role="planning",
                session_id="older-fz4-session",
                account_id="acct-1",
                thread_id="thread-1",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed older FZ4 project",
    )

    resolver = ContextResolver(runtime)
    result = resolver.resolve(
        ContextResolveOptions(
            query="FZ4 最小投入 当前唯一口径",
            session_id="sess-claude",
            account_id="acct-1",
            agent_id="claude_code",
            role_id="planning",
            thread_id="thread-claude",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert "FZ4 最小投入" in result.prompt_prefix
    assert result.prompt_prefix.index("FZ4 最小投入") < result.prompt_prefix.index("Recent Project 7")


def test_context_resolver_recalls_imported_work_memory_and_exposes_import_hits(tmp_path) -> None:  # noqa: ANN001
    runtime = get_advisor_runtime()
    importer = WorkMemoryImporter(runtime.memory)
    active_manifest = _write_import_manifest(
        tmp_path,
        manifest_id="manifest-active-v1",
        object_type="active_project",
        entries=[
            {
                "seed_id": "AP-001",
                "import_gate": "ready",
                "payload": {
                    "project_id": "PRJ-IMPORT-1",
                    "name": "Imported Alpha Project",
                    "phase": "execution",
                    "status": "active_conditional",
                    "blockers": ["procurement approval"],
                    "next_steps": ["confirm supplier recovery"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "approved",
                },
                "metadata": {
                    "source_seed_doc": "docs/active_seed.md",
                    "conditions": ["still conditional"],
                    "provenance_grade": "P-A",
                    "do_not_infer": "不要推断为已量产",
                },
            }
        ],
    )
    decision_manifest = _write_import_manifest(
        tmp_path,
        manifest_id="manifest-decision-v1",
        object_type="decision_ledger",
        entries=[
            {
                "seed_id": "DCL-001",
                "import_gate": "ready",
                "payload": {
                    "decision_id": "DCL-001",
                    "statement": "Keep the current rollout baseline.",
                    "domain": "planning",
                    "valid_from": "2026-03-30",
                    "valid_to": None,
                    "superseded_by": None,
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "approved",
                    "confidence": 0.9,
                },
                "metadata": {
                    "source_seed_doc": "docs/decision_seed.md",
                    "conditions": ["baseline only while procurement is unresolved"],
                    "provenance_grade": "P-A",
                    "do_not_infer": "不要推断为已放量",
                },
            }
        ],
    )
    importer.execute(
        [active_manifest, decision_manifest],
        account_id="acct-1",
        role_id="planning",
    )
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="captured_memory",
            key="remembered-guidance",
            value={
                "title": "Remembered guidance",
                "summary": "Keep answers short and decision-first.",
                "content": "Keep answers short and decision-first.",
            },
            confidence=0.85,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="advisor",
                role="planning",
                session_id="sess-1",
                account_id="acct-1",
                thread_id="thread-1",
            ).to_dict(),
        ),
        MemoryTier.EPISODIC,
        reason="seed captured memory",
    )
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="imported alpha procurement baseline",
            session_id="sess-antigravity",
            account_id="acct-1",
            agent_id="antigravity",
            role_id="planning",
            thread_id="thread-antigravity",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert "Imported Alpha Project" in result.prompt_prefix
    assert "Keep the current rollout baseline." in result.prompt_prefix
    assert result.prompt_prefix.index("### Active Project Map") < result.prompt_prefix.index("### Decision Ledger")
    assert result.metadata["work_memory_query_sensitive"] is True
    assert result.metadata["work_memory_scope_hits"]["active_project"] == "account_role"
    assert {hit["seed_id"] for hit in result.metadata["work_memory_import_hits"]} == {"AP-001", "DCL-001"}


def test_context_resolver_does_not_surface_manual_review_import_queue(tmp_path) -> None:  # noqa: ANN001
    runtime = get_advisor_runtime()
    importer = WorkMemoryImporter(runtime.memory)
    decision_manifest = _write_import_manifest(
        tmp_path,
        manifest_id="manifest-manual-v1",
        object_type="decision_ledger",
        entries=[
            {
                "seed_id": "DCL-002",
                "import_gate": "manual_review_required",
                "payload": {
                    "decision_id": "DCL-002",
                    "statement": "FZ4 is still in soft-mould validation.",
                    "domain": "manufacturing",
                    "valid_from": "2026-03-16",
                    "valid_to": None,
                    "superseded_by": None,
                    "source_refs": ["两轮车车身业务/2026-03-16_九号合作项目进展.md"],
                    "review_status": "staged",
                    "confidence": 0.75,
                },
                "metadata": {
                    "source_seed_doc": "docs/decision_seed.md",
                    "conditions": ["customer boundary still pending"],
                    "do_not_infer": "不要推断为已具备量产准备条件",
                },
            }
        ],
    )
    importer.execute(
        [decision_manifest],
        account_id="acct-1",
        role_id="planning",
        only_gate="manual_review_required",
    )
    resolver = ContextResolver(runtime)

    result = resolver.resolve(
        ContextResolveOptions(
            query="soft mould validation",
            session_id="sess-antigravity",
            account_id="acct-1",
            agent_id="antigravity",
            role_id="planning",
            thread_id="thread-antigravity",
            sources=("memory", "policy"),
        )
    )

    assert result.ok is True
    assert "FZ4 is still in soft-mould validation." not in result.prompt_prefix
    assert result.metadata["work_memory_import_hits"] == []
