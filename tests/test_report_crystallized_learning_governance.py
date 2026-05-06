from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.advisor.interaction_learning import record_interaction_learning
from chatgptrest.kernel.memory_manager import MemoryManager
from ops.report_crystallized_learning_governance import (
    build_crystallized_learning_governance_report,
    write_crystallized_learning_governance_artifacts,
)


def _seed_memory(path: Path) -> None:
    memory = MemoryManager(str(path))
    for session_id, executor in (
        ("sess-1", "codex"),
        ("sess-2", "codex"),
        ("sess-3", "claude"),
        ("sess-4", "claude"),
        ("sess-5", "claude"),
    ):
        record_interaction_learning(
            memory,
            account_id="acct-1",
            thread_id="thread-1",
            session_id=session_id,
            agent_id="advisor",
            role_id="planning",
            project_id="prj-beta",
            learning_payload={
                "preferred_executor_family": executor,
                "source_message": f"switch to {executor}",
            },
        )
    record_interaction_learning(
        memory,
        account_id="acct-2",
        thread_id="thread-2",
        session_id="sess-6",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-gamma",
        learning_payload={
            "brevity_preference": "short",
            "source_message": "太长了",
        },
    )
    memory.close()


def test_build_crystallized_learning_governance_report_tracks_shadow_and_supersession(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    _seed_memory(db_path)

    summary = build_crystallized_learning_governance_report(db_path=db_path, sample_size=5)

    assert summary["records_scanned"] == 2
    assert summary["crystal_generation"]["active_crystal_count"] == 1
    assert summary["crystal_generation"]["no_crystal_record_count"] == 1
    assert summary["projection_mode"] == "shadow"
    assert summary["governance"]["active_crystals_by_key"]["preferred_executor_family"] == 1
    assert summary["governance"]["superseded_candidate_count"] == 1
    assert summary["manual_review"]["sample_size"] == 1
    assert summary["samples"][0]["stable_preferences"]["preferred_executor_family"] == "claude"


def test_write_crystallized_learning_governance_artifacts_writes_expected_files(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    _seed_memory(db_path)
    summary = build_crystallized_learning_governance_report(db_path=db_path, sample_size=5)

    written = write_crystallized_learning_governance_artifacts(summary, tmp_path / "out", "sample")

    assert len(written) == 3
    assert all(path.exists() for path in written)
    summary_json = json.loads((tmp_path / "out" / "crystallized_learning_governance_sample.json").read_text(encoding="utf-8"))
    assert summary_json["crystal_generation"]["active_crystal_count"] == 1
