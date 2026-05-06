#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _artifacts_for_action(
    action: str,
    *,
    controller_packet: dict[str, Any],
    attention_manifest: dict[str, Any],
) -> list[str]:
    paths = controller_packet.get("paths") if isinstance(controller_packet, dict) else {}
    review = attention_manifest.get("review") if isinstance(attention_manifest, dict) else {}
    governance = attention_manifest.get("governance") if isinstance(attention_manifest, dict) else {}
    followup = attention_manifest.get("followup") if isinstance(attention_manifest, dict) else {}

    if action == "fix_review_outputs":
        candidates = [
            str(paths.get("review_reply_draft") or ""),
            str(paths.get("review_brief") or ""),
            str(review.get("review_output_validation_path") or ""),
            str(review.get("reviewer_manifest_path") or ""),
        ]
    elif action == "collect_missing_reviews":
        candidates = [
            str(paths.get("review_reply_draft") or ""),
            str(paths.get("review_brief") or ""),
            str(review.get("reviewer_manifest_path") or ""),
            str(review.get("pack_path") or ""),
            str(review.get("review_backlog_path") or ""),
        ]
    elif action == "continue_review":
        candidates = [
            str(paths.get("review_brief") or ""),
            str(review.get("pack_path") or ""),
            str(review.get("review_backlog_path") or ""),
            str(review.get("review_decision_scaffold_path") or ""),
        ]
    elif action == "route_followups":
        candidates = [str(paths.get("review_brief") or "")]
        routes = followup.get("routes") if isinstance(followup, dict) else {}
        for payload in routes.values():
            if not isinstance(payload, dict):
                continue
            for key in ("manifest_path", "smoke_manifest_path", "worklist_path", "queue_path", "summary_path"):
                value = str(payload.get(key) or "")
                if value:
                    candidates.append(value)
    else:
        candidates = [
            str(paths.get("review_reply_draft") or ""),
            str(paths.get("review_brief") or ""),
            str(governance.get("summary_path") or ""),
        ]
    result: list[str] = []
    for item in candidates:
        if item and item not in result:
            result.append(item)
    return result


def build_plan(
    *,
    output_path: str | Path,
    controller_packet: dict[str, Any],
    attention_manifest: dict[str, Any],
) -> dict[str, Any]:
    summary = controller_packet.get("summary") if isinstance(controller_packet, dict) else {}
    action = str(summary.get("recommended_action") or "")
    reason = str(summary.get("reason") or "")
    steps = {
        "fix_review_outputs": [
            "inspect validation summary for invalid or duplicate items",
            "repair reviewer outputs without changing cycle contracts",
            "rerun the review cycle after outputs are structurally valid",
        ],
        "collect_missing_reviews": [
            "send the current review pack and reviewer manifest to the remaining reviewers",
            "wait for missing review outputs to land",
            "rerun the review cycle after reviewer coverage improves",
        ],
        "continue_review": [
            "inspect backlog candidates in the current review pack",
            "prepare the next review pass without changing review-plane contracts",
        ],
        "route_followups": [
            "dispatch accepted, revise, defer, and reject follow-up artifacts to their owners",
            "keep the work inside review-plane handoff surfaces",
        ],
        "park": [
            "no controller action is currently required",
        ],
    }.get(action, ["review the current controller packet manually"])

    plan = {
        "ok": True,
        "recommended_action": action,
        "reason": reason,
        "artifacts": _artifacts_for_action(action, controller_packet=controller_packet, attention_manifest=attention_manifest),
        "steps": steps,
        "constraints": [
            "review-plane only",
            "no runtime adoption",
            "no active knowledge promotion",
            "no auto-commenting",
        ],
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan["output_path"] = str(out)
    return plan


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a controller action plan for execution experience review status.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--controller-packet", required=True)
    parser.add_argument("--attention-manifest", required=True)
    args = parser.parse_args()

    result = build_plan(
        output_path=args.output,
        controller_packet=_load_json(Path(args.controller_packet)),
        attention_manifest=_load_json(Path(args.attention_manifest)),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
