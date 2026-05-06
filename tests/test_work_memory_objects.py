from __future__ import annotations

import pytest

from chatgptrest.kernel.work_memory_objects import (
    WORK_MEMORY_SCHEMA_VERSION,
    DecisionLedgerObject,
    HandoffObject,
    WorkMemoryValidationError,
    build_work_memory_object,
)


def test_build_decision_ledger_object_injects_kind_schema_and_object_id() -> None:
    obj = build_work_memory_object(
        "decision_ledger",
        {
            "decision_id": "dec-001",
            "statement": "Freeze the new cost baseline.",
            "domain": "planning",
            "review_status": "approved",
        },
        fallback_source_ref="doc://freeze-point",
    )

    assert isinstance(obj, DecisionLedgerObject)
    assert obj.kind == "decision_ledger"
    assert obj.schema_version == WORK_MEMORY_SCHEMA_VERSION
    assert obj.object_id == "dec-001"
    assert obj.source_refs == ["doc://freeze-point"]
    assert obj.review_status == "approved"
    assert obj.valid_from


def test_build_handoff_requires_required_fields() -> None:
    with pytest.raises(WorkMemoryValidationError, match="current_situation is required"):
        build_work_memory_object(
            "handoff",
            {
                "handoff_id": "handoff-001",
                "from_agent": "codex",
                "from_session": "sess-1",
                "next_pickup": "Continue phase 2",
            },
            fallback_source_ref="doc://handoff",
        )


def test_build_work_memory_object_rejects_kind_mismatch() -> None:
    with pytest.raises(WorkMemoryValidationError, match="kind/category mismatch"):
        build_work_memory_object(
            "active_project",
            {
                "kind": "decision_ledger",
                "project_id": "prj-001",
                "name": "Alpha",
                "phase": "P1",
                "status": "active",
                "source_refs": ["doc://project"],
            },
        )


def test_build_work_memory_object_rejects_missing_source_refs() -> None:
    with pytest.raises(WorkMemoryValidationError, match="source_refs is required"):
        build_work_memory_object(
            "handoff",
            {
                "handoff_id": "handoff-001",
                "from_agent": "codex",
                "from_session": "sess-1",
                "current_situation": "Need to finish receipt tests",
                "next_pickup": "Write the API tests",
            },
        )
