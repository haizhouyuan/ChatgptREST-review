from __future__ import annotations

import json

import ops.run_openclaw_dynamic_replay_gate as runner
from chatgptrest.eval.openclaw_dynamic_replay_gate import OpenClawDynamicReplayCheck, OpenClawDynamicReplayReport


def _report(*, num_failed: int, num_passed: int) -> OpenClawDynamicReplayReport:
    return OpenClawDynamicReplayReport(
        base_url="http://127.0.0.1:18711",
        plugin_source="/tmp/plugin/index.ts",
        num_checks=1,
        num_passed=num_passed,
        num_failed=num_failed,
        checks=[OpenClawDynamicReplayCheck(name="dynamic_tool_registration", passed=num_failed == 0)],
    )


def test_main_returns_zero_only_for_green_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_EVAL_OUT_DIR", str(tmp_path))
    monkeypatch.setattr(runner, "run_openclaw_dynamic_replay_gate", lambda: _report(num_failed=0, num_passed=1))
    monkeypatch.setattr(
        runner,
        "write_openclaw_dynamic_replay_report",
        lambda report, out_dir, basename: (tmp_path / f"{basename}.json", tmp_path / f"{basename}.md"),
    )

    exit_code = runner.main()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert manifest["ok"] is True
    assert manifest["num_failed"] == 0


def test_main_returns_nonzero_for_failed_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_EVAL_OUT_DIR", str(tmp_path))
    monkeypatch.setattr(runner, "run_openclaw_dynamic_replay_gate", lambda: _report(num_failed=1, num_passed=0))
    monkeypatch.setattr(
        runner,
        "write_openclaw_dynamic_replay_report",
        lambda report, out_dir, basename: (tmp_path / f"{basename}.json", tmp_path / f"{basename}.md"),
    )

    exit_code = runner.main()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert manifest["ok"] is False
    assert manifest["num_failed"] == 1
