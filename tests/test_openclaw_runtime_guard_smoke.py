from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops import run_openclaw_runtime_guard_smoke as module


def test_run_smoke_detects_expected_detectors(tmp_path: Path) -> None:
    report = module.run_smoke(tmp_path)

    assert report["ok"] is True
    assert report["missing_detectors"] == []
    assert sorted(report["actual_detectors"]) == sorted(module.EXPECTED_DETECTORS)
    assert Path(str(report["artifact_dir"])).exists()


def test_main_writes_smoke_report(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"
    monkeypatch.setattr(module, "parse_args", lambda: argparse.Namespace(output_dir=str(output_dir)))

    assert module.main() == 0

    payload = json.loads((output_dir / "runtime_guard_smoke.json").read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["missing_detectors"] == []
