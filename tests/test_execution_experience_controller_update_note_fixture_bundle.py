from __future__ import annotations

from pathlib import Path

from ops.run_execution_experience_controller_surfaces_smoke import _seed_db, _write_execution_decisions
from ops.run_execution_experience_review_cycle import run_cycle


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_controller_update_note_fixture_bundle_20260311")


def _normalize(text: str, *, root: Path, first_dir: Path, second_dir: Path) -> str:
    normalized = text.replace(str(second_dir), "experience_cycle/CYCLE_DIR_01")
    normalized = normalized.replace(str(first_dir), "experience_cycle/CYCLE_DIR")
    normalized = normalized.replace(str(root), ".")
    return normalized


def test_execution_experience_controller_update_note_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    decisions_path = tmp_path / "execution_review_decisions_v1.tsv"
    _seed_db(db_path)
    _write_execution_decisions(decisions_path)

    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions_path,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    second = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions_path,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )

    first_dir = Path(first["review_pack"]["output_dir"]).parent
    second_dir = Path(second["review_pack"]["output_dir"]).parent

    first_note = _normalize(Path(first["controller_update_note_path"]).read_text(encoding="utf-8"), root=tmp_path, first_dir=first_dir, second_dir=second_dir)
    second_note = _normalize(Path(second["controller_update_note_path"]).read_text(encoding="utf-8"), root=tmp_path, first_dir=first_dir, second_dir=second_dir)

    assert first_note == (FIXTURE_DIR / "first_cycle_controller_update_note_v1.md").read_text(encoding="utf-8")
    assert second_note == (FIXTURE_DIR / "second_cycle_controller_update_note_v1.md").read_text(encoding="utf-8")
