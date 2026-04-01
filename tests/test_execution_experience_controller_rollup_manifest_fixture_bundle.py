from __future__ import annotations

import json
from pathlib import Path

from ops.run_execution_experience_controller_surfaces_smoke import _seed_db, _write_execution_decisions
from ops.run_execution_experience_review_cycle import run_cycle


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_controller_rollup_manifest_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _normalize_manifest(payload: dict, *, root: Path, first_dir: Path, second_dir: Path) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))

    def _normalize_path(value: str) -> str:
        result = value.replace(str(second_dir), "experience_cycle/CYCLE_DIR_01")
        result = result.replace(str(first_dir), "experience_cycle/CYCLE_DIR")
        result = result.replace(str(root), ".")
        return result

    for key, value in list((normalized.get("paths") or {}).items()):
        if isinstance(value, str) and value:
            normalized["paths"][key] = _normalize_path(value)
    normalized["artifacts"] = [
        _normalize_path(item) for item in normalized.get("artifacts") or [] if isinstance(item, str) and item
    ]
    return normalized


def test_execution_experience_controller_rollup_manifest_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
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

    first_manifest_path = Path(first["controller_rollup_manifest_path"])
    second_manifest_path = Path(second["controller_rollup_manifest_path"])
    first_dir = first_manifest_path.parent
    second_dir = second_manifest_path.parent

    assert first_manifest_path.exists()
    assert second_manifest_path.exists()

    assert _normalize_manifest(_load_json(first_manifest_path), root=tmp_path, first_dir=first_dir, second_dir=second_dir) == _load_json(
        FIXTURE_DIR / "first_cycle_controller_rollup_manifest_v1.json"
    )
    assert _normalize_manifest(_load_json(second_manifest_path), root=tmp_path, first_dir=first_dir, second_dir=second_dir) == _load_json(
        FIXTURE_DIR / "second_cycle_controller_rollup_manifest_v1.json"
    )
