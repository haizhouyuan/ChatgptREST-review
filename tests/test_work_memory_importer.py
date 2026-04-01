from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest.kernel.memory_manager import MemoryManager, MemoryTier
from chatgptrest.kernel.work_memory_importer import (
    WORK_MEMORY_IMPORT_REVIEW_CATEGORY,
    WorkMemoryImportValidationError,
    WorkMemoryImporter,
    load_work_memory_import_manifest,
)
from chatgptrest.kernel.work_memory_manager import WorkMemoryManager


def _write_manifest(
    tmp_path: Path,
    *,
    manifest_id: str = "manifest-active-v1",
    object_type: str = "active_project",
    entries: list[dict] | None = None,
) -> Path:
    if entries is None:
        entries = [
            {
                "seed_id": "AP-001",
                "import_gate": "ready",
                "payload": {
                    "project_id": "PRJ-1",
                    "name": "Alpha Project",
                    "phase": "execution",
                    "status": "active",
                    "blockers": ["budget freeze"],
                    "next_steps": ["confirm supplier"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "approved",
                },
                "metadata": {
                    "source_seed_doc": "docs/seed.md",
                    "conditions": ["customer boundary still conditional"],
                    "provenance_grade": "P-A",
                    "do_not_infer": "不要推断为已量产",
                },
            }
        ]
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
    return path


def test_load_work_memory_import_manifest_validates_top_level_object_type(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, object_type="handoff")

    with pytest.raises(WorkMemoryImportValidationError) as exc:
        load_work_memory_import_manifest(path)

    assert exc.value.blocked_by == "object_type"


def test_work_memory_importer_dry_run_routes_ready_and_manual_review_entries(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        entries=[
            {
                "seed_id": "AP-001",
                "import_gate": "ready",
                "payload": {
                    "project_id": "PRJ-1",
                    "name": "Alpha Project",
                    "phase": "execution",
                    "status": "active",
                    "blockers": [],
                    "next_steps": ["confirm supplier"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "approved",
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            },
            {
                "seed_id": "AP-002",
                "import_gate": "manual_review_required",
                "payload": {
                    "project_id": "PRJ-2",
                    "name": "Beta Project",
                    "phase": "negotiation",
                    "status": "active_conditional",
                    "blockers": ["contract freeze"],
                    "next_steps": ["wait for contract evidence"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "staged",
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            },
        ],
    )

    result = WorkMemoryImporter(MemoryManager(":memory:")).dry_run([path], only_gate="all")

    assert result.ok is True
    assert [entry.plan_status for entry in result.entries] == ["ready_to_write", "manual_review_required"]
    assert all(entry.selected for entry in result.entries)


def test_work_memory_importer_blocks_payload_validation_failure(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        entries=[
            {
                "seed_id": "AP-001",
                "import_gate": "ready",
                "payload": {
                    "project_id": "PRJ-1",
                    "name": "Alpha Project",
                    "phase": "execution",
                    "status": "active",
                    "blockers": [],
                    "next_steps": ["confirm supplier"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "review_status": "approved",
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            }
        ],
    )

    result = WorkMemoryImporter(MemoryManager(":memory:")).dry_run([path], only_gate="all")

    assert result.ok is False
    assert result.entries[0].status == "blocked"
    assert result.entries[0].blocked_by == ["missing_source_refs"]


def test_work_memory_importer_fails_closed_on_unknown_gate(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        entries=[
            {
                "seed_id": "AP-001",
                "import_gate": "hold",
                "payload": {
                    "project_id": "PRJ-1",
                    "name": "Alpha Project",
                    "phase": "execution",
                    "status": "active",
                    "blockers": [],
                    "next_steps": ["confirm supplier"],
                    "key_files": ["00_入口/项目台账.md"],
                    "last_updated": "2026-03-30",
                    "owner": "YHZ / planning",
                    "source_refs": ["00_入口/项目台账.md"],
                    "review_status": "approved",
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            }
        ],
    )

    result = WorkMemoryImporter(MemoryManager(":memory:")).dry_run([path], only_gate="all")

    assert result.ok is False
    assert result.entries[0].status == "blocked"
    assert result.entries[0].blocked_by == ["import_gate"]


def test_work_memory_importer_execute_preserves_import_metadata_and_replays_idempotently(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, manifest_id="manifest-ready-v1")
    memory = MemoryManager(":memory:")
    importer = WorkMemoryImporter(memory)

    first = importer.execute([path], account_id="acct-1", role_id="planning")
    second = importer.execute([path], account_id="acct-1", role_id="planning")

    first_entry = first.entries[0]
    second_entry = second.entries[0]
    record = memory.get_by_record_id(first_entry.record_id)

    assert first_entry.status == "written"
    assert second_entry.status == "written"
    assert second_entry.duplicate is True
    assert first_entry.record_id == second_entry.record_id
    assert record is not None
    assert record.tier == MemoryTier.EPISODIC.value
    assert record.value["import_metadata"]["manifest_id"] == "manifest-ready-v1"
    assert record.value["import_metadata"]["seed_id"] == "AP-001"
    assert record.value["import_audit"]["mode"] == "execute"
    assert record.value["import_audit"]["source_identity"] == "manual_review"


def test_work_memory_importer_execute_queues_manual_review_entries_without_active_write(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        manifest_id="manifest-manual-v1",
        entries=[
            {
                "seed_id": "DCL-001",
                "import_gate": "manual_review_required",
                "payload": {
                    "decision_id": "DCL-001",
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
                    "source_seed_doc": "docs/seed.md",
                    "conditions": ["boundary still pending"],
                    "do_not_infer": "do not infer mass production readiness",
                },
            }
        ],
        object_type="decision_ledger",
    )
    memory = MemoryManager(":memory:")
    importer = WorkMemoryImporter(memory)

    result = importer.execute(
        [path],
        account_id="acct-1",
        role_id="planning",
        only_gate="manual_review_required",
    )

    entry = result.entries[0]
    review_record = memory.get_by_record_id(entry.queue_record_id)
    active_records = memory.get_episodic(category="decision_ledger", account_id="acct-1", role_id="planning")

    assert entry.status == "queued_for_review"
    assert entry.record_id == ""
    assert review_record is not None
    assert review_record.category == WORK_MEMORY_IMPORT_REVIEW_CATEGORY
    assert review_record.tier == MemoryTier.META.value
    assert review_record.value["import_metadata"]["seed_id"] == "DCL-001"
    assert active_records == []


def test_work_memory_importer_review_list_and_promote_write_active_object(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        manifest_id="manifest-promote-v1",
        entries=[
            {
                "seed_id": "DCL-001",
                "import_gate": "manual_review_required",
                "payload": {
                    "decision_id": "DCL-001",
                    "statement": "FZ4 remains in validation.",
                    "domain": "manufacturing",
                    "valid_from": "2026-03-16",
                    "source_refs": ["两轮车车身业务/2026-03-16_九号合作项目进展.md"],
                    "review_status": "staged",
                    "confidence": 0.75,
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            }
        ],
        object_type="decision_ledger",
    )
    memory = MemoryManager(":memory:")
    importer = WorkMemoryImporter(memory)
    queued = importer.execute([path], account_id="acct-1", role_id="planning", only_gate="manual_review_required")
    queue_record_id = queued.entries[0].queue_record_id

    queue = importer.list_review_queue()
    resolution = importer.resolve_review(
        queue_record_id,
        action="promote",
        reviewer="reviewer-bot",
        reason="review complete",
    )
    review_record = memory.get_by_record_id(queue_record_id)
    active_records = memory.get_episodic(category="decision_ledger", account_id="acct-1", role_id="planning")

    assert queue.summary()["item_count"] == 1
    assert queue.items[0].record_id == queue_record_id
    assert resolution.ok is True
    assert resolution.review_state == "resolved"
    assert resolution.durable_record_id
    assert review_record is not None
    assert review_record.value["resolution_action"] == "promote"
    assert review_record.value["review_state"] == "resolved"
    assert len(active_records) == 1
    assert active_records[0].value["decision_id"] == "DCL-001"
    assert active_records[0].value["review_status"] == "approved"


def test_work_memory_importer_review_reject_keeps_item_out_of_active_context(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        manifest_id="manifest-reject-v1",
        entries=[
            {
                "seed_id": "DCL-002",
                "import_gate": "manual_review_required",
                "payload": {
                    "decision_id": "DCL-002",
                    "statement": "This conclusion is not yet frozen.",
                    "domain": "manufacturing",
                    "valid_from": "2026-03-16",
                    "source_refs": ["两轮车车身业务/2026-03-16_九号合作项目进展.md"],
                    "review_status": "staged",
                    "confidence": 0.6,
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            }
        ],
        object_type="decision_ledger",
    )
    memory = MemoryManager(":memory:")
    importer = WorkMemoryImporter(memory)
    queued = importer.execute([path], account_id="acct-1", role_id="planning", only_gate="manual_review_required")
    queue_record_id = queued.entries[0].queue_record_id

    resolution = importer.resolve_review(
        queue_record_id,
        action="reject",
        reviewer="reviewer-bot",
        reason="evidence still incomplete",
    )
    review_record = memory.get_by_record_id(queue_record_id)
    active_records = memory.get_episodic(category="decision_ledger", account_id="acct-1", role_id="planning")

    assert resolution.ok is True
    assert resolution.review_state == "resolved"
    assert resolution.durable_record_id == ""
    assert review_record is not None
    assert review_record.value["payload"]["review_status"] == "rejected"
    assert active_records == []


def test_work_memory_importer_review_supersede_then_rollback_restores_previous_decision(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        manifest_id="manifest-supersede-v1",
        entries=[
            {
                "seed_id": "DCL-NEW",
                "import_gate": "manual_review_required",
                "payload": {
                    "decision_id": "DCL-NEW",
                    "statement": "Switch to the updated production boundary.",
                    "domain": "manufacturing",
                    "valid_from": "2026-03-30",
                    "source_refs": ["两轮车车身业务/2026-03-30_边界更新.md"],
                    "review_status": "staged",
                    "confidence": 0.8,
                },
                "metadata": {"source_seed_doc": "docs/seed.md"},
            }
        ],
        object_type="decision_ledger",
    )
    memory = MemoryManager(":memory:")
    manager = WorkMemoryManager(memory)
    base = manager.write_from_capture(
        category="decision_ledger",
        title="Base decision",
        content="Base decision content",
        summary="Base decision",
        payload={
            "decision_id": "DCL-OLD",
            "statement": "Keep the previous production boundary.",
            "domain": "manufacturing",
            "valid_from": "2026-03-16",
            "source_refs": ["两轮车车身业务/2026-03-16_九号合作项目进展.md"],
            "review_status": "approved",
            "confidence": 0.9,
        },
        source_ref="两轮车车身业务/2026-03-16_九号合作项目进展.md",
        source_system="manual_review",
        source_agent="manual_review",
        role_id="planning",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        trace_id="trace-base",
        confidence=0.9,
        provenance_quality="complete",
        identity_gaps=[],
    )
    assert base.ok is True

    importer = WorkMemoryImporter(memory)
    queued = importer.execute([path], account_id="acct-1", role_id="planning", only_gate="manual_review_required")
    queue_record_id = queued.entries[0].queue_record_id

    supersede = importer.resolve_review(
        queue_record_id,
        action="supersede",
        reviewer="reviewer-bot",
        reason="new conclusion replaces old one",
        supersedes_decision_id="DCL-OLD",
    )
    old_record = memory.get_by_record_id(base.record_id)
    new_record = memory.get_by_record_id(supersede.durable_record_id)

    assert supersede.ok is True
    assert old_record is not None
    assert new_record is not None
    assert old_record.value["review_status"] == "superseded"
    assert old_record.value["superseded_by"] == "DCL-NEW"
    assert new_record.value["review_status"] == "approved"

    rollback = importer.resolve_review(
        queue_record_id,
        action="rollback",
        reviewer="reviewer-bot",
        reason="revert mistaken import",
    )
    rolled_back_new = memory.get_by_record_id(supersede.durable_record_id)
    restored_old = memory.get_by_record_id(base.record_id)
    review_record = memory.get_by_record_id(queue_record_id)

    assert rollback.ok is True
    assert rollback.review_state == "rolled_back"
    assert rolled_back_new is not None
    assert restored_old is not None
    assert review_record is not None
    assert rolled_back_new.value["review_status"] == "rejected"
    assert restored_old.value["review_status"] == "approved"
    assert restored_old.value["superseded_by"] == ""
    assert review_record.value["review_state"] == "rolled_back"
