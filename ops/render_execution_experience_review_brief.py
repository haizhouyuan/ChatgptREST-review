#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render_brief(
    *,
    output_path: str | Path,
    governance_snapshot: dict[str, Any],
    attention_manifest: dict[str, Any],
) -> dict[str, Any]:
    totals = governance_snapshot.get("totals") if isinstance(governance_snapshot, dict) else {}
    review_state = governance_snapshot.get("review_state") if isinstance(governance_snapshot, dict) else {}
    validation_state = governance_snapshot.get("validation_state") if isinstance(governance_snapshot, dict) else {}
    queue_state = governance_snapshot.get("queue_state") if isinstance(governance_snapshot, dict) else {}
    attention_flags = governance_snapshot.get("attention_flags") if isinstance(governance_snapshot, dict) else {}
    review_routes = attention_manifest.get("review") if isinstance(attention_manifest, dict) else {}
    governance_routes = attention_manifest.get("governance") if isinstance(attention_manifest, dict) else {}
    followup_routes = attention_manifest.get("followup") if isinstance(attention_manifest, dict) else {}

    lines = [
        "# Execution Experience Review Brief",
        "",
        "## Totals",
        f"- total_candidates: {int(totals.get('total_candidates', 0))}",
        f"- reviewed_candidates: {int(totals.get('reviewed_candidates', 0))}",
        f"- backlog_candidates: {int(totals.get('backlog_candidates', 0))}",
        f"- followup_candidates: {int(totals.get('followup_candidates', 0))}",
        "",
        "## Validation",
        f"- available: {bool(validation_state.get('available', False))}",
        f"- structurally_valid: {validation_state.get('structurally_valid')}",
        f"- complete: {validation_state.get('complete')}",
        f"- missing_reviewers: {', '.join(validation_state.get('missing_reviewers') or []) or '-'}",
        f"- total_validation_issues: {int(validation_state.get('total_validation_issues', 0))}",
        "",
        "## Governance",
        f"- by_state: {json.dumps(queue_state.get('by_state') or {}, ensure_ascii=False, sort_keys=True)}",
        f"- by_action: {json.dumps(queue_state.get('by_action') or {}, ensure_ascii=False, sort_keys=True)}",
        f"- disputed_candidates: {int(review_state.get('disputed_candidates', 0))}",
        f"- under_reviewed_candidates: {int(review_state.get('under_reviewed_candidates', 0))}",
        "",
        "## Followup",
        f"- by_branch: {json.dumps(queue_state.get('followup_by_branch') or {}, ensure_ascii=False, sort_keys=True)}",
        f"- total_followup_routes: {int(followup_routes.get('total_candidates', 0))}",
        "",
        "## Flags",
        f"- backlog_open: {bool(attention_flags.get('backlog_open', False))}",
        f"- reviewer_coverage_gaps: {bool(attention_flags.get('reviewer_coverage_gaps', False))}",
        f"- invalid_review_outputs: {bool(attention_flags.get('invalid_review_outputs', False))}",
        f"- followup_work_present: {bool(attention_flags.get('followup_work_present', False))}",
        "",
        "## Routes",
        f"- review_pack: {str(review_routes.get('pack_path') or '-')}",
        f"- review_backlog: {str(review_routes.get('review_backlog_path') or '-')}",
        f"- review_decision_scaffold: {str(review_routes.get('review_decision_scaffold_path') or '-')}",
        f"- review_output_validation: {str(review_routes.get('review_output_validation_path') or '-')}",
        f"- governance_summary: {str(governance_routes.get('summary_path') or '-')}",
        f"- reviewer_manifest: {str(review_routes.get('reviewer_manifest_path') or '-')}",
    ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_path": str(out),
        "sections": ["totals", "validation", "governance", "followup", "flags", "routes"],
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a human-readable execution experience review brief.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--governance-snapshot", required=True)
    parser.add_argument("--attention-manifest", required=True)
    args = parser.parse_args()

    result = render_brief(
        output_path=args.output,
        governance_snapshot=_load_json(Path(args.governance_snapshot)),
        attention_manifest=_load_json(Path(args.attention_manifest)),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
