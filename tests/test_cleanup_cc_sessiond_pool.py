from __future__ import annotations

from pathlib import Path

from chatgptrest.kernel.cc_sessiond.registry import SessionRegistry
from ops.cleanup_cc_sessiond_pool import apply_cleanup_plan, build_cleanup_plan


def _make_registry_fixture(tmp_path: Path):
    db_path = tmp_path / "cc-sessions.db"
    artifacts_dir = tmp_path / "artifacts"
    registry = SessionRegistry(db_path)

    valid_doc = tmp_path / "task_packet_v1.md"
    valid_doc.write_text("# task\n", encoding="utf-8")
    missing_doc = tmp_path / "missing_task_packet_v1.md"

    keep = registry.create(str(valid_doc), {"prompt_doc_path": str(valid_doc)})
    invalid = registry.create("Test prompt", {})
    missing = registry.create(str(missing_doc), {"prompt_doc_path": str(missing_doc)})

    for session_id in [keep.session_id, invalid.session_id, missing.session_id]:
        (artifacts_dir / session_id).mkdir(parents=True, exist_ok=True)
    orphan_dir = artifacts_dir / "orphan-session"
    orphan_dir.mkdir(parents=True, exist_ok=True)

    registry.close()
    return {
        "db_path": db_path,
        "artifacts_dir": artifacts_dir,
        "keep_id": keep.session_id,
        "invalid_id": invalid.session_id,
        "missing_id": missing.session_id,
        "orphan_dir": orphan_dir,
    }


def test_build_cleanup_plan_classifies_registry_and_orphans(tmp_path: Path) -> None:
    env = _make_registry_fixture(tmp_path)

    plan = build_cleanup_plan(
        db_path=env["db_path"],
        artifacts_dir=env["artifacts_dir"],
        preserve_session_ids={env["invalid_id"]},
    )

    assert plan["summary"]["registry_total"] == 3
    assert plan["summary"]["registry_delete"] == 1
    assert plan["summary"]["artifact_dirs_delete"] == 2

    delete_ids = {item["session_id"] for item in plan["registry_delete"]}
    assert env["missing_id"] in delete_ids
    assert env["keep_id"] not in delete_ids
    assert env["invalid_id"] not in delete_ids

    artifact_delete_ids = {item["session_id"] for item in plan["artifact_delete"]}
    assert env["missing_id"] in artifact_delete_ids
    assert "orphan-session" in artifact_delete_ids


def test_apply_cleanup_plan_removes_registry_rows_and_artifacts(tmp_path: Path) -> None:
    env = _make_registry_fixture(tmp_path)

    plan = build_cleanup_plan(
        db_path=env["db_path"],
        artifacts_dir=env["artifacts_dir"],
        preserve_session_ids=set(),
    )
    applied = apply_cleanup_plan(plan)

    assert set(applied["deleted_registry_ids"]) == {env["invalid_id"], env["missing_id"]}
    assert str(env["orphan_dir"]) in set(applied["deleted_artifact_paths"])

    registry = SessionRegistry(env["db_path"])
    try:
        assert registry.get(env["keep_id"]) is not None
        assert registry.get(env["invalid_id"]) is None
        assert registry.get(env["missing_id"]) is None
    finally:
        registry.close()

    assert (env["artifacts_dir"] / env["keep_id"]).exists()
    assert not (env["artifacts_dir"] / env["invalid_id"]).exists()
    assert not (env["artifacts_dir"] / env["missing_id"]).exists()
    assert not env["orphan_dir"].exists()


def test_build_cleanup_plan_marks_tmp_dot_task_packets_as_volatile(tmp_path: Path) -> None:
    db_path = tmp_path / "cc-sessions.db"
    artifacts_dir = tmp_path / "artifacts"
    registry = SessionRegistry(db_path)
    volatile_doc = tmp_path / "tmp.fake123" / "task_packet_v1.md"
    volatile_doc.parent.mkdir(parents=True, exist_ok=True)
    volatile_doc.write_text("# tmp task\n", encoding="utf-8")
    record = registry.create(str(volatile_doc), {"prompt_doc_path": str(volatile_doc)})
    registry.close()

    (artifacts_dir / record.session_id).mkdir(parents=True, exist_ok=True)

    plan = build_cleanup_plan(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        preserve_session_ids=set(),
    )

    delete_items = {item["session_id"]: item for item in plan["registry_delete"]}
    assert delete_items[record.session_id]["reason"] == "volatile_tmp_task_packet"
