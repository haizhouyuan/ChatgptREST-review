#!/usr/bin/env python3
"""Smoke-test cc_executor EventBus emission into canonical EvoMap atoms."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from chatgptrest.evomap.activity_ingest import ActivityIngestService
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.kernel.cc_executor import CcExecutor, CcResult, CcTask
from chatgptrest.kernel.event_bus import EventBus


def run_smoke() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cc-executor-smoke-") as tmp:
        db_path = str(Path(tmp) / "evomap.db")
        db = KnowledgeDB(db_path)
        db.init_schema()
        observer = EvoMapObserver(db_path=db_path)
        bus = EventBus()
        service = ActivityIngestService(db=db, observer=observer)
        service.register_bus_handlers(bus)
        executor = CcExecutor(observer=observer, event_bus=bus)

        try:
            task = CcTask(
                task_type="code_review",
                description="smoke execution telemetry",
                files=["chatgptrest/kernel/cc_executor.py"],
                trace_id="trace-cc-executor-smoke",
            )
            result = CcResult(
                ok=True,
                agent="cc_executor",
                task_type="code_review",
                output="found 2 medium issues",
                elapsed_seconds=1.25,
                findings_count=2,
                files_modified=1,
                template_used="v1_structured",
                quality_score=0.82,
                trace_id=task.trace_id,
                model_used="sonnet",
                input_tokens=120,
                output_tokens=80,
                cost_usd=0.05,
                dispatch_mode="headless",
            )

            executor._emit_completion(task, result)
            executor._emit(
                "task.failed",
                task.trace_id,
                {
                    "agent": "cc_executor",
                    "task_type": task.task_type,
                    "error": "synthetic smoke failure",
                    "elapsed_s": 0.1,
                },
            )

            conn = db.connect()
            created = conn.execute(
                """
                SELECT canonical_question, applicability
                FROM atoms
                WHERE canonical_question IN ('activity: task.completed', 'activity: task.failed')
                ORDER BY canonical_question
                """
            ).fetchall()
            rows = [
                {
                    "canonical_question": canonical_question,
                    "applicability": json.loads(applicability or "{}"),
                }
                for canonical_question, applicability in created
            ]
            return {
                "ok": len(rows) == 2,
                "row_count": len(rows),
                "rows": rows,
            }
        finally:
            bus.close()
            observer.close()
            db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", default="")
    args = parser.parse_args()
    report = run_smoke()
    if args.report_json:
        Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
