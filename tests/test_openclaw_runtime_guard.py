from __future__ import annotations

import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus, Stability
from ops import openclaw_runtime_guard as module


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _seed_event_bus(path: Path, events: list[dict[str, object]]) -> None:
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
    conn.executemany(
        """
        INSERT INTO trace_events (
            event_id, source, event_type, trace_id, timestamp, data, session_id, parent_event_id, security_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                str(item["event_id"]),
                str(item["source"]),
                str(item["event_type"]),
                str(item["trace_id"]),
                str(item["timestamp"]),
                json.dumps(item.get("data") or {}, ensure_ascii=False),
                str(item.get("session_id") or ""),
                "",
                "internal",
            )
            for item in events
        ],
    )
    conn.commit()
    conn.close()


def _seed_lane_db(path: Path, *, lane_id: str, heartbeat_at: float, desired_state: str = "observed", run_state: str = "working") -> None:
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
    now = time.time()
    conn.execute(
        """
        INSERT INTO lanes (
            lane_id, purpose, lane_kind, cwd, desired_state, run_state, session_key,
            stale_after_seconds, restart_cooldown_seconds, heartbeat_at, pid,
            launch_cmd, resume_cmd, last_summary, last_artifact_path, last_error,
            checkpoint_pending, restart_count, last_launch_at, last_exit_code,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, '', ?, 0, 0, ?, 0, ?, ?)
        """,
        (
            lane_id,
            "observe",
            "worker",
            "/tmp",
            desired_state,
            run_state,
            "sess-lane",
            900,
            300,
            heartbeat_at,
            123,
            "lane heartbeat",
            "",
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
            {
                "pack_dir": str(pack),
                "ready_for_explicit_consumption": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return bundle


def _seed_evomap_runtime_db(path: Path) -> None:
    db = KnowledgeDB(db_path=str(path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_plan",
            source="planning",
            project="planning",
            raw_ref="/planning/report.md",
            title="机器人代工合同与商务底线",
            meta_json=json.dumps(
                {
                    "planning_review": {
                        "review_domain": "business_104",
                        "source_bucket": "planning_outputs",
                    }
                },
                ensure_ascii=False,
            ),
        )
    )
    db.put_episode(Episode(episode_id="ep_active", doc_id="doc_plan", episode_type="md_section", title="合同"))
    db.put_atom(
        Atom(
            atom_id="at_active",
            episode_id="ep_active",
            atom_type="decision",
            question="合同与商务底线怎么设",
            answer="底线应包含付款节点、验收标准和违约退出条件。",
            canonical_question="合同与商务底线怎么设",
            stability=Stability.VERSIONED.value,
            promotion_status=PromotionStatus.ACTIVE.value,
            quality_auto=0.92,
            groundedness=0.9,
        )
    )
    db.commit()


def test_run_guard_detects_all_phase1_failures(tmp_path: Path) -> None:
    now = time.time()
    event_bus_db = tmp_path / "events.db"
    lane_db = tmp_path / "lanes.db"
    evomap_db = tmp_path / "missing_evomap.db"
    bundle_dir = _write_planning_bundle(tmp_path / "planning")

    _seed_event_bus(
        event_bus_db,
        [
            {
                "event_id": "evt-start",
                "source": "openclaw",
                "event_type": "team.run.created",
                "trace_id": "trace-stale",
                "timestamp": _iso(now - 4000),
                "session_id": "sess-1",
                "data": {
                    "task_ref": "runtime-guard/stale-run",
                    "lane_id": "lane-stale",
                },
            },
            {
                "event_id": "evt-tool-1",
                "source": "openclaw",
                "event_type": "tool.failed",
                "trace_id": "trace-tool",
                "timestamp": _iso(now - 120),
                "session_id": "sess-1",
                "data": {"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"},
            },
            {
                "event_id": "evt-tool-2",
                "source": "openclaw",
                "event_type": "tool.failed",
                "trace_id": "trace-tool",
                "timestamp": _iso(now - 110),
                "session_id": "sess-1",
                "data": {"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"},
            },
            {
                "event_id": "evt-tool-3",
                "source": "openclaw",
                "event_type": "tool.failed",
                "trace_id": "trace-tool",
                "timestamp": _iso(now - 100),
                "session_id": "sess-1",
                "data": {"task_ref": "runtime-guard/tool", "tool": "openmind_memory_capture", "lane_id": "lane-stale"},
            },
        ],
    )
    _seed_lane_db(lane_db, lane_id="lane-stale", heartbeat_at=now - 3600)

    report = module.run_guard(
        module.GuardConfig(
            event_bus_db_path=event_bus_db,
            controller_lane_db_path=lane_db,
            evomap_db_path=evomap_db,
            output_root=tmp_path / "artifacts",
            lookback_seconds=7200,
            heartbeat_stale_seconds=900,
            workflow_sla_seconds=1800,
            tool_failure_ratio_threshold=0.5,
            tool_failure_min_samples=3,
            planning_probe_queries=("不会命中的查询",),
            planning_bundle_dir=str(bundle_dir),
            base_url="",
        )
    )

    detector_ids = {hit["detector_id"] for hit in report["detector_hits"]}
    assert report["ok"] is False
    assert detector_ids == {
        "missing_heartbeat",
        "started_without_terminal",
        "tool_failure_spike",
        "telemetry_contract_violation",
        "planning_opt_in_zero_hit",
        "evomap_runtime_visibility_regression",
    }
    assert report["incident_summary"]["highest_severity"] == "P1"


def test_run_guard_writes_artifacts_for_healthy_state(tmp_path: Path) -> None:
    now = time.time()
    event_bus_db = tmp_path / "events.db"
    lane_db = tmp_path / "lanes.db"
    evomap_db = tmp_path / "evomap_knowledge.db"
    bundle_dir = _write_planning_bundle(tmp_path / "planning")
    _seed_evomap_runtime_db(evomap_db)

    _seed_event_bus(
        event_bus_db,
        [
            {
                "event_id": "evt-start",
                "source": "openclaw",
                "event_type": "team.run.created",
                "trace_id": "trace-ok",
                "timestamp": _iso(now - 60),
                "session_id": "sess-ok",
                "data": {
                    "task_ref": "runtime-guard/ok",
                    "lane_id": "lane-ok",
                    "role_id": "planner",
                    "executor_kind": "codex",
                },
            },
            {
                "event_id": "evt-end",
                "source": "openclaw",
                "event_type": "team.run.completed",
                "trace_id": "trace-ok",
                "timestamp": _iso(now - 30),
                "session_id": "sess-ok",
                "data": {
                    "task_ref": "runtime-guard/ok",
                    "lane_id": "lane-ok",
                    "role_id": "planner",
                    "executor_kind": "codex",
                },
            },
            {
                "event_id": "evt-tool",
                "source": "openclaw",
                "event_type": "tool.completed",
                "trace_id": "trace-ok",
                "timestamp": _iso(now - 20),
                "session_id": "sess-ok",
                "data": {
                    "task_ref": "runtime-guard/ok",
                    "tool": "openmind_memory_capture",
                    "lane_id": "lane-ok",
                    "role_id": "planner",
                    "executor_kind": "codex",
                },
            },
        ],
    )
    _seed_lane_db(lane_db, lane_id="lane-ok", heartbeat_at=now - 60)

    report = module.run_guard(
        module.GuardConfig(
            event_bus_db_path=event_bus_db,
            controller_lane_db_path=lane_db,
            evomap_db_path=evomap_db,
            output_root=tmp_path / "artifacts",
            lookback_seconds=3600,
            heartbeat_stale_seconds=900,
            workflow_sla_seconds=1800,
            planning_bundle_dir=str(bundle_dir),
            planning_probe_queries=("合同 商务 底线",),
            base_url="",
        )
    )

    assert report["ok"] is True
    assert report["incident_summary"]["hit_count"] == 0
    assert report["state_summary"]["counts"]["runtime_visible_atoms"] == 1
    assert report["state_summary"]["counts"]["planning_probe_total_hits"] == 1

    artifact_dir = module.write_artifacts(report, output_root=tmp_path / "runtime_guard")
    assert (artifact_dir / "state_summary.json").exists()
    assert (artifact_dir / "incident_summary.json").exists()
    assert (artifact_dir / "detector_hits.json").exists()
    assert (artifact_dir / "runtime_guard_latest.md").exists()
    latest = json.loads((tmp_path / "runtime_guard" / "latest.json").read_text(encoding="utf-8"))
    assert latest["ok"] is True
