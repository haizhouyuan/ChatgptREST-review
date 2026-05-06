from __future__ import annotations

import json
from pathlib import Path

from ops.run_execution_experience_controller_surfaces_smoke import run_smoke


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_experience_controller_surfaces_smoke_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _normalize_path(value: str, *, root: Path, cycle_dir: str) -> str:
    normalized = value.replace(str(root), ".")
    normalized = normalized.replace(f"./experience_cycle/{cycle_dir}", "experience_cycle/CYCLE_DIR")
    return normalized


def _normalize_summary(payload: dict, *, root: Path, cycle_dir: str) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["output_dir"] = "."
    for key, value in list((normalized.get("paths") or {}).items()):
        if isinstance(value, str) and value:
            normalized["paths"][key] = _normalize_path(value, root=root, cycle_dir=cycle_dir)
    return normalized


def _normalize_packet(payload: dict, *, root: Path, cycle_dir: str) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    for key, value in list((normalized.get("paths") or {}).items()):
        if isinstance(value, str) and value:
            normalized["paths"][key] = _normalize_path(value, root=root, cycle_dir=cycle_dir)
    routes = ((normalized.get("followup") or {}).get("routes") or {})
    for route in routes.values():
        if not isinstance(route, dict):
            continue
        for key, value in list(route.items()):
            if isinstance(value, str) and value:
                route[key] = _normalize_path(value, root=root, cycle_dir=cycle_dir)
    return normalized


def _normalize_action_plan(payload: dict, *, root: Path, cycle_dir: str) -> dict:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["artifacts"] = [
        _normalize_path(item, root=root, cycle_dir=cycle_dir) for item in normalized.get("artifacts") or []
    ]
    return normalized


def _normalize_text(text: str, *, root: Path, cycle_dir: str) -> str:
    normalized = text.replace(str(root), ".")
    normalized = normalized.replace(f"./experience_cycle/{cycle_dir}", "experience_cycle/CYCLE_DIR")
    return normalized


def test_execution_experience_controller_surfaces_smoke_fixture_bundle_matches_expected_outputs(tmp_path: Path) -> None:
    result = run_smoke(output_dir=tmp_path / "smoke")

    root = Path(result["output_dir"])
    summary_path = Path(result["summary_path"])
    packet_path = Path(result["paths"]["controller_packet"])
    action_plan_path = Path(result["paths"]["controller_action_plan"])
    review_brief_path = Path(result["paths"]["review_brief"])
    review_reply_draft_path = Path(result["paths"]["review_reply_draft"])
    cycle_dir = packet_path.parent.name

    assert summary_path.exists()
    assert packet_path.exists()
    assert action_plan_path.exists()
    assert review_brief_path.exists()
    assert review_reply_draft_path.exists()

    assert _normalize_summary(_load_json(summary_path), root=root, cycle_dir=cycle_dir) == _load_json(
        FIXTURE_DIR / "controller_surfaces_smoke_summary_v1.json"
    )
    assert _normalize_packet(_load_json(packet_path), root=root, cycle_dir=cycle_dir) == _load_json(
        FIXTURE_DIR / "controller_packet_v1.json"
    )
    assert _normalize_action_plan(_load_json(action_plan_path), root=root, cycle_dir=cycle_dir) == _load_json(
        FIXTURE_DIR / "controller_action_plan_v1.json"
    )
    assert _normalize_text(review_brief_path.read_text(encoding="utf-8"), root=root, cycle_dir=cycle_dir) == (
        FIXTURE_DIR / "review_brief_v1.md"
    ).read_text(encoding="utf-8")
    assert _normalize_text(review_reply_draft_path.read_text(encoding="utf-8"), root=root, cycle_dir=cycle_dir) == (
        FIXTURE_DIR / "review_reply_draft_v1.md"
    ).read_text(encoding="utf-8")
