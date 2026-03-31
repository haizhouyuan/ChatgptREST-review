#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_note(
    *,
    output_path: str | Path,
    controller_packet: dict[str, Any],
    controller_action_plan: dict[str, Any],
    progress_delta: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = controller_packet.get("summary") if isinstance(controller_packet, dict) else {}
    totals = summary if isinstance(summary, dict) else {}
    status = progress_delta.get("status") if isinstance(progress_delta, dict) else {}
    delta_totals = ((progress_delta or {}).get("delta") or {}).get("totals") or {}
    delta_validation = ((progress_delta or {}).get("delta") or {}).get("validation_state") or {}
    changed_flags = ((progress_delta or {}).get("delta") or {}).get("attention_flag_changes") or {}
    paths = controller_packet.get("paths") if isinstance(controller_packet, dict) else {}
    artifacts = list(controller_action_plan.get("artifacts") or []) if isinstance(controller_action_plan, dict) else []

    lines = [
        "# Execution Experience Controller Update",
        "",
        "## Current State",
        f"- recommended_action: {str(summary.get('recommended_action') or '')}",
        f"- reason: {str(summary.get('reason') or '')}",
        f"- total_candidates: {int(totals.get('total_candidates', 0))}",
        f"- backlog_candidates: {int(totals.get('backlog_candidates', 0))}",
        f"- followup_candidates: {int(totals.get('followup_candidates', 0))}",
        f"- validation_available: {bool(totals.get('validation_available', False))}",
        "",
        "## Progress Delta",
        f"- available: {bool(progress_delta)}",
        f"- progress_signal: {str(status.get('progress_signal') or '-')}",
        f"- recommended_action_changed: {bool(status.get('recommended_action_changed', False))}",
        f"- action_severity_delta: {status.get('action_severity_delta') if progress_delta else '-'}",
        f"- reviewed_candidates_delta: {int(delta_totals.get('reviewed_candidates', 0)) if progress_delta else 0}",
        f"- backlog_candidates_delta: {int(delta_totals.get('backlog_candidates', 0)) if progress_delta else 0}",
        f"- validation_issue_delta: {int(delta_validation.get('total_validation_issues', 0)) if progress_delta else 0}",
        f"- changed_flags: {json.dumps(changed_flags, ensure_ascii=False, sort_keys=True) if progress_delta else '{}'}",
        "",
        "## Next Steps",
    ]
    for step in controller_action_plan.get("steps") or []:
        lines.append(f"- {step}")
    if not (controller_action_plan.get("steps") or []):
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Artifacts",
            f"- controller_packet: {str((controller_packet or {}).get('output_path') or '')}",
            f"- controller_action_plan: {str((controller_action_plan or {}).get('output_path') or '')}",
            f"- progress_delta: {str((progress_delta or {}).get('output_path') or '-')}",
            f"- review_brief: {str(paths.get('review_brief') or '')}",
            f"- review_reply_draft: {str(paths.get('review_reply_draft') or '')}",
        ]
    )
    for artifact in artifacts:
        if artifact and artifact not in lines:
            lines.append(f"- referenced: {artifact}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_path": str(out),
        "progress_signal": str(status.get("progress_signal") or ""),
        "recommended_action": str(summary.get("recommended_action") or ""),
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a controller-facing update note for execution experience review status.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--controller-packet", required=True)
    parser.add_argument("--controller-action-plan", required=True)
    parser.add_argument("--progress-delta", default="")
    args = parser.parse_args()

    controller_packet = _load_json(Path(args.controller_packet))
    controller_packet["output_path"] = args.controller_packet
    controller_action_plan = _load_json(Path(args.controller_action_plan))
    controller_action_plan["output_path"] = args.controller_action_plan
    progress_delta = _load_json(Path(args.progress_delta)) if args.progress_delta else None
    if progress_delta:
        progress_delta["output_path"] = args.progress_delta

    result = build_note(
        output_path=args.output,
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        progress_delta=progress_delta,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
