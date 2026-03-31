#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    output_path: str | Path,
    controller_packet: dict[str, Any],
    controller_action_plan: dict[str, Any],
    controller_update_note_path: str | Path,
    progress_delta: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = controller_packet.get("summary") if isinstance(controller_packet, dict) else {}
    paths = controller_packet.get("paths") if isinstance(controller_packet, dict) else {}
    status = progress_delta.get("status") if isinstance(progress_delta, dict) else {}

    manifest = {
        "ok": True,
        "summary": {
            "recommended_action": str(summary.get("recommended_action") or ""),
            "reason": str(summary.get("reason") or ""),
            "progress_signal": str(status.get("progress_signal") or ""),
            "validation_available": bool(summary.get("validation_available", False)),
            "followup_candidates": int(summary.get("followup_candidates", 0) or 0),
        },
        "paths": {
            "controller_packet": str(controller_packet.get("output_path") or ""),
            "controller_action_plan": str(controller_action_plan.get("output_path") or ""),
            "controller_update_note": str(controller_update_note_path),
            "progress_delta": str((progress_delta or {}).get("output_path") or ""),
            "governance_snapshot": str(paths.get("governance_snapshot") or ""),
            "attention_manifest": str(paths.get("attention_manifest") or ""),
            "review_brief": str(paths.get("review_brief") or ""),
            "review_reply_draft": str(paths.get("review_reply_draft") or ""),
        },
        "availability": {
            "progress_delta": bool(progress_delta),
            "controller_update_note": bool(controller_update_note_path),
        },
        "artifacts": list(controller_action_plan.get("artifacts") or []),
        "constraints": list(controller_action_plan.get("constraints") or []),
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["output_path"] = str(out)
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a machine-readable rollup manifest for execution experience controller surfaces.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--controller-packet", required=True)
    parser.add_argument("--controller-action-plan", required=True)
    parser.add_argument("--controller-update-note", required=True)
    parser.add_argument("--progress-delta", default="")
    args = parser.parse_args()

    controller_packet = _load_json(Path(args.controller_packet))
    controller_packet["output_path"] = args.controller_packet
    controller_action_plan = _load_json(Path(args.controller_action_plan))
    controller_action_plan["output_path"] = args.controller_action_plan
    progress_delta = _load_json(Path(args.progress_delta)) if args.progress_delta else None
    if progress_delta:
        progress_delta["output_path"] = args.progress_delta

    result = build_manifest(
        output_path=args.output,
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=args.controller_update_note,
        progress_delta=progress_delta,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
