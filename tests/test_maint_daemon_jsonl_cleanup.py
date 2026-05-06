from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ops import maint_daemon_jsonl_cleanup


def _write_jsonl(path: Path, *, day: datetime, count: int = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for idx in range(count):
        lines.append(
            json.dumps(
                {
                    "ts": day.replace(hour=idx, minute=0, second=0).isoformat().replace("+00:00", "Z"),
                    "type": "heartbeat",
                    "idx": idx,
                },
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_classify_actions_respects_protected_hot_and_summary_windows(tmp_path: Path) -> None:
    base = datetime(2026, 3, 28, tzinfo=UTC)
    files = []
    for offset in range(8):
        day = base - timedelta(days=offset)
        path = tmp_path / f"maint_{day.strftime('%Y%m%d')}.jsonl"
        _write_jsonl(path, day=day)
        files.append(maint_daemon_jsonl_cleanup._parse_file(path))
    parsed = [item for item in files if item is not None]

    rows = maint_daemon_jsonl_cleanup._classify_actions(
        parsed,
        protected_files=2,
        hot_raw_files=2,
        warm_window_days=4,
        now_utc=base,
    )

    by_name = {row["file_name"]: row for row in rows}
    assert by_name["maint_20260328.jsonl"]["action"] == "protected"
    assert by_name["maint_20260327.jsonl"]["action"] == "protected"
    assert by_name["maint_20260326.jsonl"]["action"] == "keep_raw"
    assert by_name["maint_20260325.jsonl"]["action"] == "keep_raw"
    assert by_name["maint_20260324.jsonl"]["action"] == "compress"
    assert by_name["maint_20260321.jsonl"]["action"] == "summarize_only"


def test_main_writes_dry_run_reports(tmp_path: Path) -> None:
    monitor_dir = tmp_path / "maint_daemon"
    reports_root = tmp_path / "reports"
    base = datetime(2026, 3, 28, tzinfo=UTC)
    for offset in range(6):
        day = base - timedelta(days=offset)
        _write_jsonl(monitor_dir / f"maint_{day.strftime('%Y%m%d')}.jsonl", day=day, count=20)

    rc = maint_daemon_jsonl_cleanup.main(
        [
            "--monitor-dir",
            str(monitor_dir),
            "--reports-root",
            str(reports_root),
            "--timestamp",
            "20260328T010203Z",
            "--protected-files",
            "1",
            "--hot-raw-files",
            "1",
            "--warm-window-days",
            "2",
            "--sample-limit",
            "2",
            "--sample-bytes-per-file",
            "4096",
        ]
    )

    assert rc == 0
    out_dir = reports_root / "20260328T010203Z"
    inventory = json.loads((out_dir / "inventory_before.json").read_text(encoding="utf-8"))
    sample = json.loads((out_dir / "compression_sample.json").read_text(encoding="utf-8"))
    plan = json.loads((out_dir / "dry_run_plan.json").read_text(encoding="utf-8"))

    assert inventory["file_count"] == 6
    assert len(sample["sampled_files"]) >= 1
    assert sample["sample_population"] in {"compress", "summarize_only"}
    assert plan["projection_mode"] == "dry_run_only"
    assert "would_compress_files" in plan
    assert "would_summarize_only_files" in plan
    assert (out_dir / "inventory_before.md").exists()
    assert (out_dir / "dry_run_plan.md").exists()
