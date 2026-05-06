#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.advisor.interaction_learning import (  # noqa: E402
    extract_user_correction_signals,
    load_interaction_learning,
    merge_learning_payload,
    record_interaction_learning,
)
from chatgptrest.advisor.runtime import get_advisor_runtime, get_advisor_runtime_if_ready  # noqa: E402
from ops.report_crystallized_learning_governance import (  # noqa: E402
    build_crystallized_learning_governance_report,
    write_crystallized_learning_governance_artifacts,
)

DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_live_crystal_evidence"
DEFAULT_CASE_FILE = REPO_ROOT / "ops" / "data" / "openmind_live_crystal_evidence_cases_v1.json"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_memory_db() -> Path:
    raw = os.environ.get("OPENMIND_MEMORY_DB", "").strip() or "~/.openmind/memory.db"
    return Path(raw).expanduser()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _user_correction_count(db_path: str | Path) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "select count(*) as c from memory_records where category='user_correction'"
        ).fetchone()
        return int(row["c"] or 0)
    finally:
        conn.close()


def _load_cases(path: str | Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("crystal evidence case file must contain a list")
    cases: list[dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"case #{idx} must be an object")
        message = str(item.get("message") or "").strip()
        account_id = str(item.get("account_id") or "").strip()
        thread_id = str(item.get("thread_id") or "").strip()
        if not message or not account_id or not thread_id:
            raise ValueError(f"case #{idx} must include message/account_id/thread_id")
        cases.append(
            {
                "message": message,
                "account_id": account_id,
                "thread_id": thread_id,
                "session_id": str(item.get("session_id") or f"{thread_id}-session").strip(),
                "agent_id": str(item.get("agent_id") or "advisor").strip(),
                "role_id": str(item.get("role_id") or "planning").strip(),
                "project_id": str(item.get("project_id") or "").strip(),
            }
        )
    return cases


def run_live_crystal_evidence(
    *,
    memory_db: str | Path,
    cases_file: str | Path,
    output_root: str | Path,
    sample_size: int = 10,
) -> dict[str, Any]:
    runtime = get_advisor_runtime_if_ready() or get_advisor_runtime()
    memory = getattr(runtime, "memory", None)
    cases = _load_cases(cases_file)
    before_user_correction = _user_correction_count(memory_db)
    before_report = build_crystallized_learning_governance_report(
        db_path=memory_db,
        sample_size=max(1, int(sample_size or 1)),
    )

    applied_cases: list[dict[str, Any]] = []
    for case in cases:
        inline = extract_user_correction_signals(case["message"])
        if not inline:
            continue
        stored = load_interaction_learning(
            memory,
            account_id=case["account_id"],
            thread_id=case["thread_id"],
        )
        merged = merge_learning_payload(stored, inline)
        recorded = record_interaction_learning(
            memory,
            account_id=case["account_id"],
            thread_id=case["thread_id"],
            session_id=case["session_id"],
            agent_id=case["agent_id"],
            role_id=case["role_id"],
            project_id=case["project_id"],
            learning_payload=merged,
        )
        applied_cases.append(
            {
                "account_id": case["account_id"],
                "thread_id": case["thread_id"],
                "project_id": case["project_id"],
                "message": case["message"],
                "signals": dict(inline),
                "recorded": bool(recorded),
                "stable_keys_after_write": sorted(
                    key
                    for key in (
                        "raw_ingress_mode",
                        "quality_bar",
                        "preferred_executor_family",
                        "closure_style",
                        "brevity_preference",
                        "depth_preference",
                        "focus_preference",
                        "reply_first_preference",
                    )
                    if recorded and str(dict(recorded).get(key) or "").strip()
                ),
            }
        )

    after_user_correction = _user_correction_count(memory_db)
    after_report = build_crystallized_learning_governance_report(
        db_path=memory_db,
        sample_size=max(1, int(sample_size or 1)),
    )

    stamp = _stamp()
    out_dir = Path(output_root) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "memory_db": str(memory_db),
        "cases_file": str(cases_file),
        "before": {
            "user_correction_records": before_user_correction,
            "records_scanned": int(before_report.get("records_scanned") or 0),
            "active_crystal_count": int(dict(before_report.get("crystal_generation") or {}).get("active_crystal_count") or 0),
        },
        "after": {
            "user_correction_records": after_user_correction,
            "records_scanned": int(after_report.get("records_scanned") or 0),
            "active_crystal_count": int(dict(after_report.get("crystal_generation") or {}).get("active_crystal_count") or 0),
        },
        "applied_cases": applied_cases,
        "delta": {
            "user_correction_records": after_user_correction - before_user_correction,
            "records_scanned": int(after_report.get("records_scanned") or 0) - int(before_report.get("records_scanned") or 0),
            "active_crystal_count": int(dict(after_report.get("crystal_generation") or {}).get("active_crystal_count") or 0)
            - int(dict(before_report.get("crystal_generation") or {}).get("active_crystal_count") or 0),
        },
        "manual_review_note": (
            "Live evidence uses the same interaction-learning helpers as the route hot path, "
            "but the traffic is synthetic canary evidence rather than organic end-user traffic."
        ),
    }
    summary_path = out_dir / f"openmind_live_crystal_evidence_{stamp}.json"
    summary_path.write_text(json.dumps(evidence_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = out_dir / f"openmind_live_crystal_evidence_{stamp}.md"
    report_path.write_text(
        "\n".join(
            [
                "# OpenMind Live Crystal Evidence",
                "",
                f"- `before_user_correction_records`: `{evidence_summary['before']['user_correction_records']}`",
                f"- `after_user_correction_records`: `{evidence_summary['after']['user_correction_records']}`",
                f"- `before_active_crystal_count`: `{evidence_summary['before']['active_crystal_count']}`",
                f"- `after_active_crystal_count`: `{evidence_summary['after']['active_crystal_count']}`",
                f"- `manual_review_note`: {evidence_summary['manual_review_note']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    governance_artifacts = write_crystallized_learning_governance_artifacts(after_report, out_dir / "governance", stamp)
    return {
        "ok": True,
        "output_dir": str(out_dir),
        "artifacts": [str(summary_path), str(report_path), *[str(path) for path in governance_artifacts]],
        "summary": evidence_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate live shadow crystal evidence by replaying interaction-learning helper writes.")
    parser.add_argument("--memory-db", default=str(_default_memory_db()))
    parser.add_argument("--cases-file", default=str(DEFAULT_CASE_FILE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--sample-size", type=int, default=10)
    args = parser.parse_args()
    result = run_live_crystal_evidence(
        memory_db=args.memory_db,
        cases_file=args.cases_file,
        output_root=args.output_root,
        sample_size=max(1, int(args.sample_size or 1)),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "summary"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
