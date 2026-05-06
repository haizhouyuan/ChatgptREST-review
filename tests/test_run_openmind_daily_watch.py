from __future__ import annotations

from pathlib import Path

from ops.run_openmind_daily_watch import run_daily_watch


def test_run_daily_watch_collects_all_stages(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def _fake_run(cmd, cwd, capture_output, text, check):  # noqa: ANN001
        calls.append(list(cmd))
        label = Path(str(cmd[1])).name
        if "canary_scorecard" in label:
            return _Proc('{"ok": true, "decision": "launch_canary_watch"}')
        if "graduation_gate" in label:
            return _Proc('{"ok": true, "decision": "hold"}')
        return _Proc(f'{{"ok": true, "label": "{label}"}}')

    monkeypatch.setattr("subprocess.run", _fake_run)

    summary = run_daily_watch(output_root=tmp_path)

    assert summary["ok"] is True
    assert [item["label"] for item in summary["runs"]] == [
        "regression",
        "health",
        "scorecard",
        "ledger",
        "gate",
    ]
    assert len(calls) == 5
    assert summary["decision"]["scorecard"] == "launch_canary_watch"
    assert summary["decision"]["gate"] == "hold"
    assert Path(summary["artifacts"]["summary_json"]).exists()
    assert Path(summary["artifacts"]["report_md"]).exists()
