"""Deliverable Aggregator — consolidate scattered job answers into reports.

When multiple jobs are related to the same research topic (e.g., market research
on 8 brands), this module aggregates their answers into a single consolidated
report, registers it in the artifact store, and provides a permalink.

Part of the system-optimization-20260316 feature set.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _artifacts_root() -> Path:
    """Return the artifacts root directory."""
    return Path(
        os.environ.get(
            "CHATGPTREST_ARTIFACTS_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "artifacts"),
        )
    ).resolve()


def find_related_jobs(
    db_path: str,
    *,
    keyword: str = "",
    kind: str = "chatgpt_web.ask",
    status: str = "completed",
    since_hours: float = 48,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Find jobs related to a keyword in input_json."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cutoff = time.time() - since_hours * 3600

    query = """
        SELECT job_id, kind, status, answer_chars, created_at, input_json
        FROM jobs
        WHERE kind = ? AND status = ? AND created_at > ?
    """
    params: list[Any] = [kind, status, cutoff]

    if keyword:
        query += " AND input_json LIKE ?"
        params.append(f"%{keyword}%")

    query += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        q = ""
        try:
            inp = json.loads(r["input_json"]) if r["input_json"] else {}
            q = inp.get("question", "")[:200]
        except (json.JSONDecodeError, TypeError):
            pass
        result.append({
            "job_id": r["job_id"],
            "kind": r["kind"],
            "status": r["status"],
            "answer_chars": r["answer_chars"],
            "created_at": r["created_at"],
            "question_preview": q,
        })
    conn.close()
    return result


def aggregate_answers(
    job_ids: list[str],
    *,
    title: str = "Aggregated Research Report",
    output_name: str | None = None,
) -> dict[str, Any]:
    """Read answer files for given job IDs and produce a consolidated report.

    Returns:
        {
            "report_path": str,  # absolute path to the aggregated report
            "job_count": int,
            "total_chars": int,
            "jobs_included": [...],
        }
    """
    artifacts = _artifacts_root()
    sections: list[str] = []
    included: list[dict[str, Any]] = []
    total_chars = 0

    for jid in job_ids:
        answer_path = None
        for ext in ("md", "txt"):
            candidate = artifacts / "jobs" / jid / f"answer.{ext}"
            if candidate.exists():
                answer_path = candidate
                break

        if not answer_path:
            logger.warning("No answer file for job %s, skipping", jid[:12])
            continue

        content = answer_path.read_text(encoding="utf-8", errors="replace")
        total_chars += len(content)

        sections.append(
            f"\n---\n\n## Job: `{jid[:12]}`\n\n"
            f"*Source: {answer_path.name}* | *{len(content):,} chars*\n\n"
            f"{content}\n"
        )
        included.append({
            "job_id": jid,
            "chars": len(content),
            "source": str(answer_path),
        })

    if not sections:
        return {
            "report_path": None,
            "job_count": 0,
            "total_chars": 0,
            "jobs_included": [],
            "error": "No answer files found for the given job IDs",
        }

    # Build consolidated report.
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    header = (
        f"# {title}\n\n"
        f"*Aggregated on {timestamp}*  \n"
        f"*{len(included)} sources, {total_chars:,} total characters*\n\n"
        f"## Table of Contents\n\n"
    )
    for i, inc in enumerate(included, 1):
        header += f"{i}. Job `{inc['job_id'][:12]}` ({inc['chars']:,} chars)\n"

    report = header + "\n" + "\n".join(sections)

    # Write report.
    if output_name is None:
        output_name = f"aggregated_report_{int(time.time())}.md"

    report_dir = artifacts / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / output_name
    report_path.write_text(report, encoding="utf-8")

    logger.info(
        "Aggregated report: %s (%d jobs, %d chars)",
        report_path,
        len(included),
        total_chars,
    )

    return {
        "report_path": str(report_path),
        "job_count": len(included),
        "total_chars": total_chars,
        "jobs_included": included,
    }


def aggregate_by_keyword(
    db_path: str,
    keyword: str,
    *,
    title: str | None = None,
    since_hours: float = 48,
) -> dict[str, Any]:
    """Convenience: find related jobs by keyword and aggregate their answers.

    Example::

        result = aggregate_by_keyword(
            "state/jobdb.sqlite3",
            keyword="两轮",
            title="中国两轮电动车市场调研报告",
        )
        print(result["report_path"])
    """
    jobs = find_related_jobs(
        db_path,
        keyword=keyword,
        since_hours=since_hours,
    )
    if not jobs:
        return {
            "report_path": None,
            "job_count": 0,
            "error": f"No completed jobs found matching '{keyword}'",
        }

    job_ids = [j["job_id"] for j in jobs]
    report_title = title or f"Research Report: {keyword}"
    return aggregate_answers(job_ids, title=report_title)
