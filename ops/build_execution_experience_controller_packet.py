#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_packet(
    *,
    output_path: str | Path,
    governance_snapshot: dict[str, Any],
    attention_manifest: dict[str, Any],
    review_brief_path: str | Path,
    review_reply_draft: dict[str, Any],
) -> dict[str, Any]:
    packet = {
        "ok": True,
        "summary": {
            "recommended_action": str(review_reply_draft.get("recommended_action") or ""),
            "reason": str(review_reply_draft.get("reason") or ""),
            "total_candidates": int((governance_snapshot.get("totals") or {}).get("total_candidates", 0)),
            "backlog_candidates": int((governance_snapshot.get("totals") or {}).get("backlog_candidates", 0)),
            "followup_candidates": int((governance_snapshot.get("totals") or {}).get("followup_candidates", 0)),
            "validation_available": bool((governance_snapshot.get("validation_state") or {}).get("available", False)),
        },
        "paths": {
            "governance_snapshot": str(governance_snapshot.get("output_path") or ""),
            "attention_manifest": str(attention_manifest.get("output_path") or ""),
            "review_brief": str(review_brief_path),
            "review_reply_draft": str(review_reply_draft.get("output_path") or ""),
        },
        "flags": dict(governance_snapshot.get("attention_flags") or {}),
        "followup": dict((attention_manifest.get("followup") or {})),
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
    parser = argparse.ArgumentParser(description="Build a controller packet for execution experience review status.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--governance-snapshot", required=True)
    parser.add_argument("--attention-manifest", required=True)
    parser.add_argument("--review-brief", required=True)
    parser.add_argument("--review-reply-draft", required=True)
    args = parser.parse_args()

    governance_snapshot = _load_json(Path(args.governance_snapshot))
    governance_snapshot["output_path"] = args.governance_snapshot
    attention_manifest = _load_json(Path(args.attention_manifest))
    attention_manifest["output_path"] = args.attention_manifest
    review_reply_draft = _load_json(Path(args.review_reply_draft))
    review_reply_draft["output_path"] = args.review_reply_draft

    result = build_packet(
        output_path=args.output,
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
        review_brief_path=args.review_brief,
        review_reply_draft=review_reply_draft,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
