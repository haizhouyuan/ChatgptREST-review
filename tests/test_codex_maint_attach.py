from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_attach_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "codex_maint_attach.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_codex_maint_attach", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_attach_payload_uses_lane_dir() -> None:
    mod = _load_attach_module()
    lane_dir = Path("/tmp/lane-1")
    payload = mod.build_attach_payload(lane_id="lane-1", lane_dir=lane_dir, all_sessions=False)
    assert payload["lane_id"] == "lane-1"
    assert payload["lane_dir"] == str(lane_dir)
    assert payload["cmd"][-2:] == ["--cd", str(lane_dir)]


def test_attach_cli_resolves_lane_from_incident_pointer(tmp_path: Path, capsys, monkeypatch) -> None:
    mod = _load_attach_module()
    lane_dir = tmp_path / "state" / "sre_lanes" / "lane-42"
    lane_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CHATGPTREST_SRE_LANES_ROOT", str(tmp_path / "state" / "sre_lanes"))
    incident_dir = tmp_path / "incident"
    (incident_dir / "codex").mkdir(parents=True, exist_ok=True)
    (incident_dir / "codex" / "source_lane.json").write_text(
        json.dumps({"source_lane_id": "lane-42"}),
        encoding="utf-8",
    )

    rc = mod.main(["--incident-dir", str(incident_dir), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lane_dir"] == str(lane_dir)
