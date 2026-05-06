from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_progress_delta import build_delta


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_progress_delta_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _materialize(base: Path, payload: dict) -> dict:
    data = json.loads(json.dumps(payload, ensure_ascii=False))
    output_path = data.get("output_path")
    if isinstance(output_path, str) and output_path:
        data["output_path"] = str(base / output_path)
    return data


def _normalize_delta(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    inputs = normalized.get("inputs") or {}
    for key, value in list(inputs.items()):
        if isinstance(value, str) and value:
            inputs[key] = Path(value).name
    return normalized


def test_execution_experience_progress_delta_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    for case in ("improved", "regressed"):
        previous_governance_snapshot = _materialize(
            tmp_path, _load_json(FIXTURE_DIR / f"{case}_previous_governance_snapshot_input_v1.json")
        )
        current_governance_snapshot = _materialize(
            tmp_path, _load_json(FIXTURE_DIR / f"{case}_current_governance_snapshot_input_v1.json")
        )
        previous_controller_action_plan = _materialize(
            tmp_path, _load_json(FIXTURE_DIR / f"{case}_previous_controller_action_plan_input_v1.json")
        )
        current_controller_action_plan = _materialize(
            tmp_path, _load_json(FIXTURE_DIR / f"{case}_current_controller_action_plan_input_v1.json")
        )

        result = build_delta(
            output_path=tmp_path / f"{case}_progress_delta.json",
            previous_governance_snapshot=previous_governance_snapshot,
            current_governance_snapshot=current_governance_snapshot,
            previous_controller_action_plan=previous_controller_action_plan,
            current_controller_action_plan=current_controller_action_plan,
        )

        expected = _load_json(FIXTURE_DIR / f"{case}_progress_delta_v1.json")
        written = _load_json(tmp_path / f"{case}_progress_delta.json")

        assert _normalize_delta(written) == expected
        returned = dict(result)
        returned.pop("output_path", None)
        assert _normalize_delta(returned) == expected
