#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_read_db_path
from chatgptrest.evomap.actuators import kb_scorer as kb_scorer_mod
from chatgptrest.evomap.actuators.kb_scorer import KBScorer
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.telemetry import TelemetryRecorder
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.kernel.event_bus import EventBus, TraceEvent


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_feedback_event_smoke"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _init_registry(path: Path, artifact_ids: tuple[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                quality_score REAL NOT NULL DEFAULT 0.5,
                stability TEXT NOT NULL DEFAULT 'draft'
            )
            """
        )
        for artifact_id in artifact_ids:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts (artifact_id, title, path, quality_score, stability)
                VALUES (?, ?, ?, ?, ?)
                """,
                (artifact_id, artifact_id, f"/tmp/{artifact_id}.md", 0.5, "draft"),
            )
        conn.commit()
    finally:
        conn.close()


def _artifact_score(path: Path, artifact_id: str) -> float:
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("SELECT quality_score FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return float(row[0] or 0.0) if row else 0.0
    finally:
        conn.close()


def run_feedback_smoke(
    *,
    knowledge_db_path: str,
    output_root: Path,
    query: str,
) -> dict[str, Any]:
    stamp = _now_stamp()
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    recorder = TelemetryRecorder(KnowledgeDB(knowledge_db_path))
    recorder.init_schema()
    conn = sqlite3.connect(str(knowledge_db_path))
    try:
        before_feedback = int(conn.execute("SELECT COUNT(*) FROM answer_feedback").fetchone()[0])
        before_queries = int(conn.execute("SELECT COUNT(*) FROM query_events").fetchone()[0])
    finally:
        conn.close()

    negative_artifact = f"kb-feedback-negative-{stamp}"
    positive_artifact = f"kb-feedback-positive-{stamp}"

    query_event = recorder.record_search_results(
        query=query,
        hits=[
            {"artifact_id": negative_artifact, "score": 0.91, "source": "kb"},
            {"artifact_id": positive_artifact, "score": 0.82, "source": "kb"},
        ],
        session_id=f"feedback-smoke-session-{stamp}",
        trace_id=f"feedback-smoke-trace-{stamp}",
        run_id=f"feedback-smoke-run-{stamp}",
        domain="planning",
        intent="feedback_smoke",
    )
    recorder.record_feedback(
        query_event.query_id,
        "corrected",
        "format",
        [negative_artifact],
    )

    temp_root = Path(tempfile.mkdtemp(prefix="evomap-feedback-smoke-"))
    signals_db = temp_root / "signals.db"
    registry_db = temp_root / "kb_registry.db"
    event_bus_db = temp_root / "event_bus.db"
    _init_registry(registry_db, (negative_artifact, positive_artifact))

    previous_registry = os.environ.get("OPENMIND_KB_DB", "")
    previous_window = kb_scorer_mod._RETRY_WINDOW_SECONDS
    observer = EvoMapObserver(db_path=str(signals_db))
    event_bus = EventBus(db_path=str(event_bus_db))
    try:
        os.environ["OPENMIND_KB_DB"] = str(registry_db)
        kb_scorer_mod._RETRY_WINDOW_SECONDS = 0.2
        scorer = KBScorer(observer=observer)
        event_bus.subscribe(scorer.on_event)

        event_bus.emit(
            TraceEvent.create(
                source="advisor",
                event_type="advisor_ask.kb_direct",
                trace_id=query_event.trace_id,
                data={"artifact_ids": [negative_artifact], "artifact_id": negative_artifact},
                session_id=query_event.session_id,
            )
        )
        event_bus.emit(
            TraceEvent.create(
                source="advisor",
                event_type="user.rapid_retry",
                trace_id=query_event.trace_id,
                data={"artifact_ids": [negative_artifact], "artifact_id": negative_artifact},
                session_id=query_event.session_id,
            )
        )

        positive_trace = f"{query_event.trace_id}-positive"
        event_bus.emit(
            TraceEvent.create(
                source="advisor",
                event_type="advisor_ask.kb_direct",
                trace_id=positive_trace,
                data={"artifact_ids": [positive_artifact], "artifact_id": positive_artifact},
                session_id=query_event.session_id,
            )
        )
        time.sleep(0.35)
    finally:
        if previous_registry:
            os.environ["OPENMIND_KB_DB"] = previous_registry
        else:
            os.environ.pop("OPENMIND_KB_DB", None)
        kb_scorer_mod._RETRY_WINDOW_SECONDS = previous_window
        try:
            event_bus.close()
        except Exception:
            pass
        observer.close()

    conn = sqlite3.connect(str(knowledge_db_path))
    try:
        after_feedback = int(conn.execute("SELECT COUNT(*) FROM answer_feedback").fetchone()[0])
        after_queries = int(conn.execute("SELECT COUNT(*) FROM query_events").fetchone()[0])
        feedback_row = conn.execute(
            "SELECT feedback_type, correction_type, atom_ids_json FROM answer_feedback ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    signal_conn = sqlite3.connect(str(signals_db))
    try:
        signal_rows = signal_conn.execute(
            "SELECT signal_type, data FROM signals ORDER BY rowid ASC"
        ).fetchall()
    finally:
        signal_conn.close()

    summary = {
        "ok": after_feedback > before_feedback and after_queries > before_queries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_db_path": str(knowledge_db_path),
        "query_id": query_event.query_id,
        "answer_feedback_delta": after_feedback - before_feedback,
        "query_event_delta": after_queries - before_queries,
        "latest_feedback": {
            "feedback_type": str(feedback_row[0] or "") if feedback_row else "",
            "correction_type": str(feedback_row[1] or "") if feedback_row else "",
            "atom_ids_json": str(feedback_row[2] or "") if feedback_row else "",
        },
        "negative_artifact_score": _artifact_score(registry_db, negative_artifact),
        "positive_artifact_score": _artifact_score(registry_db, positive_artifact),
        "signal_types": [str(row[0] or "") for row in signal_rows],
        "artifacts": {
            "signals_db": str(signals_db),
            "registry_db": str(registry_db),
            "event_bus_db": str(event_bus_db),
            "summary_json": str(run_dir / "summary.json"),
            "report_md": str(run_dir / "report.md"),
        },
    }

    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(
        "\n".join(
            [
                "# EvoMap Feedback Event Smoke",
                "",
                f"- `query_id`: `{summary['query_id']}`",
                f"- `answer_feedback_delta`: `{summary['answer_feedback_delta']}`",
                f"- `query_event_delta`: `{summary['query_event_delta']}`",
                f"- `negative_artifact_score`: `{summary['negative_artifact_score']}`",
                f"- `positive_artifact_score`: `{summary['positive_artifact_score']}`",
                f"- `signal_types`: `{', '.join(summary['signal_types'])}`",
                f"- `ok`: `{summary['ok']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test answer_feedback writes plus KBScorer event wiring.")
    parser.add_argument("--knowledge-db", default=resolve_evomap_knowledge_read_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--query", default="kb planning feedback smoke")
    args = parser.parse_args()
    summary = run_feedback_smoke(
        knowledge_db_path=str(args.knowledge_db),
        output_root=Path(args.output_root),
        query=str(args.query),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
