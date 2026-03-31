#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from ops import openclaw_runtime_guard as guard


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "runtime_guard_smoke"
EXPECTED_DETECTORS = [
    "missing_heartbeat",
    "started_without_terminal",
    "tool_failure_spike",
    "telemetry_contract_violation",
    "planning_opt_in_zero_hit",
    "evomap_runtime_visibility_regression",
]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _seed_event_bus(path: Path, *, now: float) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE trace_events (
            event_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            data TEXT NOT NULL DEFAULT '{}',
            session_id TEXT DEFAULT '',
            parent_event_id TEXT DEFAULT '',
            security_label TEXT DEFAULT 'internal'
        )
        """
    )
    rows = [
        (
            "evt-start",
            "openclaw",
            "team.run.created",
            "trace-stale",
            _iso(now - 4000),
            json.dumps({"task_ref": "runtime-guard/stale-run", "lane_id": "lane-stale"}, ensure_ascii=False),
            "sess-1",
            "",
            "internal",
        ),
        (
            "evt-tool-1",
            "openclaw",
            "tool.failed",
            "trace-tool",
            _iso(now - 120),
            json.dumps({"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"}, ensure_ascii=False),
            "sess-1",
            "",
            "internal",
        ),
        (
            "evt-tool-2",
            "openclaw",
            "tool.failed",
            "trace-tool",
            _iso(now - 110),
            json.dumps({"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"}, ensure_ascii=False),
            "sess-1",
            "",
            "internal",
        ),
        (
            "evt-tool-3",
            "openclaw",
            "tool.failed",
            "trace-tool",
            _iso(now - 100),
            json.dumps({"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"}, ensure_ascii=False),
            "sess-1",
            "",
            "internal",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO trace_events (
            event_id, source, event_type, trace_id, timestamp, data, session_id, parent_event_id, security_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def _seed_lane_db(path: Path, *, now: float) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE lanes (
            lane_id TEXT PRIMARY KEY,
            purpose TEXT NOT NULL,
            lane_kind TEXT NOT NULL,
            cwd TEXT NOT NULL,
            desired_state TEXT NOT NULL,
            run_state TEXT NOT NULL,
            session_key TEXT NOT NULL DEFAULT '',
            stale_after_seconds INTEGER NOT NULL DEFAULT 900,
            restart_cooldown_seconds INTEGER NOT NULL DEFAULT 300,
            heartbeat_at REAL,
            pid INTEGER,
            launch_cmd TEXT NOT NULL DEFAULT '',
            resume_cmd TEXT NOT NULL DEFAULT '',
            last_summary TEXT NOT NULL DEFAULT '',
            last_artifact_path TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            checkpoint_pending INTEGER NOT NULL DEFAULT 0,
            restart_count INTEGER NOT NULL DEFAULT 0,
            last_launch_at REAL,
            last_exit_code INTEGER,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO lanes (
            lane_id, purpose, lane_kind, cwd, desired_state, run_state, session_key,
            stale_after_seconds, restart_cooldown_seconds, heartbeat_at, pid, launch_cmd,
            resume_cmd, last_summary, last_artifact_path, last_error, checkpoint_pending,
            restart_count, last_launch_at, last_exit_code, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, '', '', 0, 0, ?, 0, ?, ?)
        """,
        (
            "lane-stale",
            "observe",
            "worker",
            "/tmp",
            "observed",
            "working",
            "sess-lane",
            900,
            300,
            now - 3600,
            321,
            "lane stale",
            now - 600,
            now - 600,
            now - 600,
        ),
    )
    conn.commit()
    conn.close()


def _write_planning_bundle(base: Path) -> Path:
    bundle = base / "bundle"
    pack = base / "pack"
    bundle.mkdir(parents=True, exist_ok=True)
    pack.mkdir(parents=True, exist_ok=True)
    with (pack / "docs.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doc_id",
                "title",
                "raw_ref",
                "family_id",
                "review_domain",
                "source_bucket",
                "document_role",
                "final_bucket",
                "service_readiness",
                "is_latest_output",
                "updated_at",
                "updated_at_iso",
                "live_active_atoms",
                "live_candidate_atoms",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "title": "机器人代工合同与商务底线",
                "raw_ref": "/planning/report.md",
                "family_id": "business_104",
                "review_domain": "business_104",
                "source_bucket": "planning_outputs",
                "document_role": "service_candidate",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "is_latest_output": 1,
                "updated_at": 1,
                "updated_at_iso": "2026-03-11T00:00:00+00:00",
                "live_active_atoms": 1,
                "live_candidate_atoms": 0,
            }
        )
    with (pack / "atoms.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doc_id",
                "atom_id",
                "episode_id",
                "atom_type",
                "promotion_status",
                "promotion_reason",
                "quality_auto",
                "value_auto",
                "question",
                "canonical_question",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "atom_id": "at_active",
                "episode_id": "ep_active",
                "atom_type": "decision",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.9,
                "value_auto": 0.6,
                "question": "合同与商务底线怎么设",
                "canonical_question": "合同与商务底线怎么设",
            }
        )
    (pack / "retrieval_pack.json").write_text(
        json.dumps(
            {
                "pack_type": "planning_reviewed_runtime_pack_v1",
                "doc_ids": ["doc_plan"],
                "atom_ids": ["at_active"],
                "review_domains": ["business_104"],
                "source_buckets": ["planning_outputs"],
                "opt_in_only": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle / "release_bundle_manifest.json").write_text(
        json.dumps(
            {"pack_dir": str(pack), "ready_for_explicit_consumption": True},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return bundle


def run_smoke(output_root: Path) -> dict[str, object]:
    now = time.time()
    fixture_dir = output_root / "fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    event_bus_db = fixture_dir / "events.db"
    lane_db = fixture_dir / "lanes.db"
    evomap_db = fixture_dir / "missing_evomap.db"
    bundle_dir = _write_planning_bundle(fixture_dir / "planning")
    _seed_event_bus(event_bus_db, now=now)
    _seed_lane_db(lane_db, now=now)

    report = guard.run_guard(
        guard.GuardConfig(
            event_bus_db_path=event_bus_db,
            controller_lane_db_path=lane_db,
            evomap_db_path=evomap_db,
            output_root=output_root / "guard",
            lookback_seconds=7200,
            heartbeat_stale_seconds=900,
            workflow_sla_seconds=1800,
            tool_failure_ratio_threshold=0.5,
            tool_failure_min_samples=3,
            planning_bundle_dir=str(bundle_dir),
            planning_probe_queries=("不会命中的查询",),
            base_url="",
        )
    )
    artifact_dir = guard.write_artifacts(report, output_root=output_root / "guard")
    actual_detectors = sorted({hit["detector_id"] for hit in report["detector_hits"]})
    missing = [name for name in EXPECTED_DETECTORS if name not in actual_detectors]
    smoke = {
        "ok": not missing,
        "generated_at": guard._utc_now_iso(),
        "artifact_dir": str(artifact_dir),
        "expected_detectors": EXPECTED_DETECTORS,
        "actual_detectors": actual_detectors,
        "missing_detectors": missing,
        "incident_summary": report["incident_summary"],
    }
    (output_root / "runtime_guard_smoke.json").write_text(json.dumps(smoke, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return smoke


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a synthetic OpenClaw runtime guard smoke test.")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.output_dir:
        tempfile.tempdir = str(output_dir / "tmp")
    report = run_smoke(output_dir)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
