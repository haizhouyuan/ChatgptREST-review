#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.compose_execution_activity_review_decisions import FIELDNAMES as ACTIVITY_FIELDNAMES
from ops.run_execution_experience_review_cycle import run_cycle


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_exec",
            source="agent_activity",
            project="ChatgptREST",
            raw_ref="/tmp/doc_exec.json",
            title="doc_exec",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec",
            doc_id="doc_exec",
            episode_type="workflow.completed",
            title="workflow.completed",
            summary="workflow.completed",
            start_ref="doc_exec:1",
            end_ref="doc_exec:1",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_exec",
            episode_id="ep_exec",
            atom_type="lesson",
            question="at_exec",
            answer="execution review cycle complete",
            canonical_question="activity: workflow.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps({"task_ref": "issue-115", "trace_id": "trace-115"}, ensure_ascii=False, sort_keys=True),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()


def _write_execution_decisions(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ACTIVITY_FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        )


def run_smoke(*, output_dir: str | Path, limit: int = 50) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "evomap.db"
    decisions = out / "execution_review_decisions_v1.tsv"

    _seed_db(db_path)
    _write_execution_decisions(decisions)

    first = run_cycle(
        db_path=db_path,
        output_root=out / "experience_cycle",
        activity_review_root=out / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=limit,
    )

    review_output = Path(first["reviewer_manifest"]["review_output_dir"]) / "gemini_no_mcp.json"
    review_output.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "candidate_id": "execxp_at_exec",
                        "decision": "accept",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable workflow lesson",
                        "groundedness": "high",
                        "time_sensitivity": "evergreen",
                        "note": "keep",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    second = run_cycle(
        db_path=db_path,
        output_root=out / "experience_cycle",
        activity_review_root=out / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[review_output],
        base_experience_decisions_path=None,
        limit=limit,
    )

    summary = {
        "ok": True,
        "output_dir": str(out),
        "mode": second["mode"],
        "recommended_action": second["controller_action_plan"]["recommended_action"],
        "reason": second["controller_action_plan"]["reason"],
        "paths": {
            "controller_packet": second["controller_packet_path"],
            "controller_action_plan": second["controller_action_plan_path"],
            "review_brief": second["review_brief_path"],
            "review_reply_draft": second["review_reply_draft_path"],
        },
    }
    summary_path = out / "controller_surfaces_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a seeded smoke for execution experience controller-facing review artifacts.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    result = run_smoke(output_dir=args.output_dir, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
