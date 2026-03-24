#!/usr/bin/env python3
"""push_evomap.py — 将评分完成的 Q&A 数据导入 EvoMap SQLite.

读取 planning_qa_scored.jsonl 中 status=scored 的条目，
转换为 EvoMap Signal 记录并写入 evomap.db。

用法:
    python push_evomap.py                           # 推送已评分条目
    python push_evomap.py --db ~/.openmind/evomap.db # 指定DB路径
    python push_evomap.py --dry-run                  # 只预览不写入

输出: 更新 EvoMap SQLite 数据库
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCORED_FILE = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/planning_qa_scored.jsonl")
DEFAULT_DB = Path(os.path.expanduser("~/.openmind/evomap.db"))

# Signal types for Q&A data
SIGNAL_TYPE_QA_SCORED = "qa.scored"
SIGNAL_TYPE_QA_HIGH = "qa.high_quality"
SIGNAL_TYPE_QA_DIVERGENCE = "qa.divergence"
SIGNAL_SOURCE = "planning_qa_pipeline"
SIGNAL_DOMAIN = "qa_scoring"


def _init_db(conn: sqlite3.Connection) -> None:
    """Ensure the signals table exists."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            signal_id    TEXT PRIMARY KEY,
            trace_id     TEXT NOT NULL DEFAULT '',
            signal_type  TEXT NOT NULL,
            source       TEXT NOT NULL DEFAULT '',
            timestamp    TEXT NOT NULL DEFAULT '',
            domain       TEXT NOT NULL DEFAULT '',
            data         TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_signals_trace ON signals(trace_id);
        CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
        CREATE INDEX IF NOT EXISTS idx_signals_domain ON signals(domain);
        CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
    """)
    conn.commit()


def _signal_id(qa_id: str, signal_type: str) -> str:
    raw = f"{qa_id}:{signal_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def push_to_evomap(records: list[dict], db_path: Path, dry_run: bool = False) -> dict[str, int]:
    """Push scored Q&A records as EvoMap signals."""
    stats = {"scored": 0, "high_quality": 0, "divergence": 0, "skipped": 0}

    if dry_run:
        print("[DRY RUN] No data will be written.\n")

    conn = None
    if not dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        _init_db(conn)

    now = datetime.now(timezone.utc).isoformat()

    for rec in records:
        status = rec.get("status", "")
        if status not in ("scored", "needs_re_review", "approved"):
            stats["skipped"] += 1
            continue

        qa_id = rec.get("qa_id", "")
        human_scores = rec.get("scores_human", {})
        rubric_auto = rec.get("rubric_auto", {})
        overall = human_scores.get("overall")

        if overall is None:
            stats["skipped"] += 1
            continue

        # Signal 1: Q&A scored
        signal_data = {
            "qa_id": qa_id,
            "domain": rec.get("domain", ""),
            "source_type": rec.get("source_type", ""),
            "question_preview": rec.get("question", "")[:100],
            "scores_human": human_scores,
            "rubric_auto": rubric_auto,
            "route_auto": rec.get("route_auto", ""),
            "overall_human": overall,
            "source_file": rec.get("source_file", ""),
        }

        sig_id = _signal_id(qa_id, SIGNAL_TYPE_QA_SCORED)
        if conn:
            conn.execute(
                """INSERT OR REPLACE INTO signals
                   (signal_id, trace_id, signal_type, source, timestamp, domain, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sig_id, qa_id, SIGNAL_TYPE_QA_SCORED, SIGNAL_SOURCE,
                 now, SIGNAL_DOMAIN, json.dumps(signal_data, ensure_ascii=False)),
            )
        stats["scored"] += 1

        # Signal 2: High-quality Q&A (score ≥ 4) — candidates for KB
        if overall >= 4:
            sig_id_hq = _signal_id(qa_id, SIGNAL_TYPE_QA_HIGH)
            hq_data = {
                **signal_data,
                "recommendation": "promote_to_kb",
            }
            if conn:
                conn.execute(
                    """INSERT OR REPLACE INTO signals
                       (signal_id, trace_id, signal_type, source, timestamp, domain, data)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sig_id_hq, qa_id, SIGNAL_TYPE_QA_HIGH, SIGNAL_SOURCE,
                     now, SIGNAL_DOMAIN, json.dumps(hq_data, ensure_ascii=False)),
                )
            stats["high_quality"] += 1

        # Signal 3: Divergence detected
        divergence = rec.get("divergence", 0)
        if divergence and divergence > 1.5:
            sig_id_div = _signal_id(qa_id, SIGNAL_TYPE_QA_DIVERGENCE)
            div_data = {
                **signal_data,
                "divergence": divergence,
                "recommendation": "recalibrate_scoring_model",
            }
            if conn:
                conn.execute(
                    """INSERT OR REPLACE INTO signals
                       (signal_id, trace_id, signal_type, source, timestamp, domain, data)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sig_id_div, qa_id, SIGNAL_TYPE_QA_DIVERGENCE, SIGNAL_SOURCE,
                     now, SIGNAL_DOMAIN, json.dumps(div_data, ensure_ascii=False)),
                )
            stats["divergence"] += 1

    if conn:
        conn.commit()
        conn.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Push scored Q&A to EvoMap")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB),
                        help="EvoMap SQLite database path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing to DB")
    args = parser.parse_args()

    if not SCORED_FILE.exists():
        print(f"ERROR: {SCORED_FILE} not found. Run auto_score.py first.")
        return

    records = []
    for line in SCORED_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    db_path = Path(args.db)

    stats = push_to_evomap(records, db_path, dry_run=args.dry_run)

    print(f"\n{'='*60}")
    print(f"EvoMap Push {'(DRY RUN) ' if args.dry_run else ''}Complete")
    print(f"{'='*60}")
    print(f"Database: {db_path}")
    print(f"Total records processed: {len(records)}")
    print(f"  Scored signals pushed:     {stats['scored']}")
    print(f"  High-quality (≥4) signals: {stats['high_quality']}")
    print(f"  Divergence signals:        {stats['divergence']}")
    print(f"  Skipped (not yet scored):  {stats['skipped']}")
    print(f"{'='*60}")

    if stats["high_quality"] > 0:
        print(f"\n💡 {stats['high_quality']} high-quality Q&A pairs are candidates for KB promotion.")
    if stats["divergence"] > 0:
        print(f"\n⚠️  {stats['divergence']} entries had human-machine score divergence > 1.5")
        print("   Consider recalibrating the auto-scoring model.")


if __name__ == "__main__":
    main()
