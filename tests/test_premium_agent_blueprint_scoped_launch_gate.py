from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate import (
    render_premium_agent_blueprint_scoped_launch_gate_markdown,
    run_premium_agent_blueprint_scoped_launch_gate,
    write_premium_agent_blueprint_scoped_launch_gate_report,
)


def _write_report(dir_path: Path, *, version: int, payload: dict[str, object]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"report_v{version}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_premium_agent_blueprint_scoped_launch_gate_passes_with_green_inputs(tmp_path: Path, monkeypatch) -> None:
    google_dir = tmp_path / "google"
    phase10_dir = tmp_path / "phase10"
    phase11_dir = tmp_path / "phase11"
    live_cutover_dir = tmp_path / "live"
    effects_dir = tmp_path / "effects"
    phase27_dir = tmp_path / "phase27"
    for path in (google_dir, phase10_dir, phase11_dir, live_cutover_dir, effects_dir, phase27_dir):
        _write_report(path, version=1, payload={"num_failed": 0, "num_checks": 1, "num_items": 1})
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.GOOGLE_WORKSPACE_DIR",
        google_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE10_DIR",
        phase10_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE11_DIR",
        phase11_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.LIVE_CUTOVER_DIR",
        live_cutover_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.EFFECTS_DIR",
        effects_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE27_DIR",
        phase27_dir,
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._run_config_checker",
        lambda: {"ok": True, "num_checked": 10, "num_failed": 0},
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._load_tokens",
        lambda _env_file: {"OPENMIND_API_KEY": "test-key", "CHATGPTREST_API_TOKEN": ""},
    )

    def _fake_post_turn(*, base_url: str, headers: dict[str, str]) -> dict[str, object]:
        return {"status_code": 403, "error": "coding_agent_direct_rest_blocked", "route": "", "agent_status": ""}

    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._post_turn", _fake_post_turn)

    report = run_premium_agent_blueprint_scoped_launch_gate()

    assert report.overall_passed is True
    assert report.num_failed == 0


def test_premium_agent_blueprint_scoped_launch_gate_writer_emits_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    google_dir = tmp_path / "google"
    phase10_dir = tmp_path / "phase10"
    phase11_dir = tmp_path / "phase11"
    live_cutover_dir = tmp_path / "live"
    effects_dir = tmp_path / "effects"
    phase27_dir = tmp_path / "phase27"
    for path in (google_dir, phase10_dir, phase11_dir, live_cutover_dir, effects_dir, phase27_dir):
        _write_report(path, version=1, payload={"num_failed": 0, "num_checks": 1, "num_items": 1})
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.GOOGLE_WORKSPACE_DIR", google_dir)
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE10_DIR", phase10_dir)
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE11_DIR", phase11_dir)
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.LIVE_CUTOVER_DIR", live_cutover_dir)
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.EFFECTS_DIR", effects_dir)
    monkeypatch.setattr("chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate.PHASE27_DIR", phase27_dir)
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._run_config_checker",
        lambda: {"ok": True, "num_checked": 10, "num_failed": 0},
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._load_tokens",
        lambda _env_file: {"OPENMIND_API_KEY": "test-key", "CHATGPTREST_API_TOKEN": ""},
    )
    monkeypatch.setattr(
        "chatgptrest.eval.premium_agent_blueprint_scoped_launch_gate._post_turn",
        lambda *, base_url, headers: {"status_code": 403, "error": "coding_agent_direct_rest_blocked", "route": "", "agent_status": ""},
    )

    report = run_premium_agent_blueprint_scoped_launch_gate()
    json_path, md_path = write_premium_agent_blueprint_scoped_launch_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_premium_agent_blueprint_scoped_launch_gate_markdown(report)
    assert "Premium Agent Blueprint Scoped Launch Gate Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
