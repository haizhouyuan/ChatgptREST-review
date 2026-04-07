#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _recommended_action(attention_flags: dict[str, Any]) -> tuple[str, str]:
    if bool(attention_flags.get("invalid_review_outputs", False)):
        return "fix_review_outputs", "validation issues are blocking review closure"
    if bool(attention_flags.get("reviewer_coverage_gaps", False)):
        return "collect_missing_reviews", "review coverage is incomplete"
    if bool(attention_flags.get("backlog_open", False)):
        return "continue_review", "candidate backlog is still open"
    if bool(attention_flags.get("followup_work_present", False)):
        return "route_followups", "reviewed candidates already need follow-up handling"
    return "park", "no immediate review-plane action is pending"


def build_draft(
    *,
    output_path: str | Path,
    governance_snapshot: dict[str, Any],
    review_brief_path: str | Path,
    attention_manifest_path: str | Path,
) -> dict[str, Any]:
    totals = governance_snapshot.get("totals") if isinstance(governance_snapshot, dict) else {}
    validation_state = governance_snapshot.get("validation_state") if isinstance(governance_snapshot, dict) else {}
    attention_flags = governance_snapshot.get("attention_flags") if isinstance(governance_snapshot, dict) else {}
    action, reason = _recommended_action(attention_flags if isinstance(attention_flags, dict) else {})

    lines = [
        "# Execution Experience Review Reply Draft",
        "",
        "Current status:",
        f"- total_candidates={int(totals.get('total_candidates', 0))}",
        f"- reviewed_candidates={int(totals.get('reviewed_candidates', 0))}",
        f"- backlog_candidates={int(totals.get('backlog_candidates', 0))}",
        f"- followup_candidates={int(totals.get('followup_candidates', 0))}",
        f"- validation_available={bool(validation_state.get('available', False))}",
        f"- structurally_valid={validation_state.get('structurally_valid')}",
        f"- complete={validation_state.get('complete')}",
        "",
        "Recommended next step:",
        f"- action={action}",
        f"- reason={reason}",
        "",
        "Artifacts:",
        f"- review_brief={str(review_brief_path)}",
        f"- attention_manifest={str(attention_manifest_path)}",
        f"- governance_snapshot={str(governance_snapshot.get('output_path') or '')}",
    ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_path": str(out),
        "recommended_action": action,
        "reason": reason,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a draft controller reply for execution experience review status.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--governance-snapshot", required=True)
    parser.add_argument("--review-brief", required=True)
    parser.add_argument("--attention-manifest", required=True)
    args = parser.parse_args()

    governance_snapshot = _load_json(Path(args.governance_snapshot))
    governance_snapshot["output_path"] = args.governance_snapshot
    result = build_draft(
        output_path=args.output,
        governance_snapshot=governance_snapshot,
        review_brief_path=args.review_brief,
        attention_manifest_path=args.attention_manifest,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
