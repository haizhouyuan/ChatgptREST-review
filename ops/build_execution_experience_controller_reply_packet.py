#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _reply_kind(action: str) -> str:
    return {
        "fix_review_outputs": "review_repair_request",
        "collect_missing_reviews": "missing_review_request",
        "continue_review": "review_progress_update",
        "route_followups": "followup_routing_update",
        "park": "parked_status_update",
    }.get(action, "manual_review_update")


def _comment_markdown(
    *,
    manifest: dict[str, Any],
    action_plan: dict[str, Any],
    update_note_path: str | Path,
) -> str:
    summary = manifest.get("summary") if isinstance(manifest, dict) else {}
    raw_paths = manifest.get("paths") if isinstance(manifest, dict) else {}
    paths = raw_paths if isinstance(raw_paths, dict) else {}
    steps = list(action_plan.get("steps") or []) if isinstance(action_plan, dict) else []

    lines = [
        "Execution experience review-plane update:",
        f"- recommended_action={str(summary.get('recommended_action') or '')}",
        f"- reason={str(summary.get('reason') or '')}",
        f"- progress_signal={str(summary.get('progress_signal') or '-')}",
        f"- validation_available={bool(summary.get('validation_available', False))}",
        f"- followup_candidates={int(summary.get('followup_candidates', 0) or 0)}",
        "",
        "Next steps:",
    ]
    if steps:
        lines.extend(f"- {step}" for step in steps)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Artifacts:",
            f"- controller_rollup_manifest={str(manifest.get('output_path') or '')}",
            f"- controller_update_note={str(update_note_path)}",
            f"- review_brief={str(paths.get('review_brief') or '')}",
            f"- review_reply_draft={str(paths.get('review_reply_draft') or '')}",
        ]
    )
    progress_delta_path = str(paths.get("progress_delta") or "")
    if progress_delta_path:
        lines.append(f"- progress_delta={progress_delta_path}")
    return "\n".join(lines) + "\n"


def build_packet(
    *,
    output_path: str | Path,
    controller_rollup_manifest: dict[str, Any],
    controller_action_plan: dict[str, Any],
    controller_update_note_path: str | Path,
) -> dict[str, Any]:
    summary = controller_rollup_manifest.get("summary") if isinstance(controller_rollup_manifest, dict) else {}
    action = str(summary.get("recommended_action") or "")
    packet = {
        "ok": True,
        "decision": {
            "recommended_action": action,
            "reason": str(summary.get("reason") or ""),
            "progress_signal": str(summary.get("progress_signal") or ""),
            "reply_kind": _reply_kind(action),
            "manual_send_required": True,
            "auto_send_allowed": False,
        },
        "reply": {
            "channel": "coordination_issue_comment",
            "comment_markdown": _comment_markdown(
                manifest=controller_rollup_manifest,
                action_plan=controller_action_plan,
                update_note_path=controller_update_note_path,
            ),
        },
        "paths": {
            "controller_rollup_manifest": str(controller_rollup_manifest.get("output_path") or ""),
            "controller_action_plan": str(controller_action_plan.get("output_path") or ""),
            "controller_update_note": str(controller_update_note_path),
            **dict(controller_rollup_manifest.get("paths") or {}),
        },
        "constraints": list(controller_action_plan.get("constraints") or []),
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    packet["output_path"] = str(out)
    return packet


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a manual-send controller reply packet for execution experience review status.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--controller-rollup-manifest", required=True)
    parser.add_argument("--controller-action-plan", required=True)
    parser.add_argument("--controller-update-note", required=True)
    args = parser.parse_args()

    controller_rollup_manifest = _load_json(Path(args.controller_rollup_manifest))
    controller_rollup_manifest["output_path"] = args.controller_rollup_manifest
    controller_action_plan = _load_json(Path(args.controller_action_plan))
    controller_action_plan["output_path"] = args.controller_action_plan

    result = build_packet(
        output_path=args.output,
        controller_rollup_manifest=controller_rollup_manifest,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=args.controller_update_note,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
