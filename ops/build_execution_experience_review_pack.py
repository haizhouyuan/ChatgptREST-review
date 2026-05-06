#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def build_review_pack(
    *,
    candidates_path: str | Path,
    output_dir: str | Path,
    limit: int = 120,
    pack_id: str = "execution_experience_review_pack_v1",
) -> dict[str, Any]:
    candidates = _read_candidates(Path(candidates_path))
    kind_rank = {"lesson": 0, "procedure": 1, "correction": 2}
    picked = sorted(
        candidates,
        key=lambda row: (
            kind_rank.get(str(row.get("experience_kind") or ""), 99),
            str(row.get("source") or ""),
            str(row.get("episode_type") or ""),
            str(row.get("candidate_id") or ""),
        ),
    )[:limit]

    pack = {
        "pack_id": pack_id,
        "pack_type": "execution_experience_candidate_review",
        "candidate_source": str(candidates_path),
        "instructions": {
            "decision_values": ["accept", "revise", "reject", "defer"],
            "fields": [
                "candidate_id",
                "decision",
                "experience_kind",
                "title",
                "summary",
                "groundedness",
                "time_sensitivity",
                "note",
            ],
            "rules": [
                "Accept only when the candidate is standalone, reusable, and grounded enough for future review-plane reuse.",
                "Use revise when the underlying candidate is valuable but the title, summary, or kind needs tightening.",
                "Use reject for thin event chatter, low-signal summaries, or candidates that are too local to the original trace.",
                "Use defer when available evidence is insufficient to decide without inventing facts.",
                "Do not promote anything to active knowledge. This pack stays in candidate/review plane only.",
            ],
        },
        "items": picked,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pack_path = out / f"{pack_id}.json"
    prompt_path = out / f"{pack_id}_prompt.txt"
    summary_path = out / "summary.json"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompt_path.write_text(
        "Review this execution experience candidate pack. Return JSON only with shape:\n"
        "{\n"
        f'  "pack_id": "{pack_id}",\n'
        '  "items": [{"candidate_id":"...","decision":"accept|revise|reject|defer","experience_kind":"lesson|procedure|correction","title":"...","summary":"...","groundedness":"high|medium|low","time_sensitivity":"evergreen|versioned|ephemeral","note":"..."}]\n'
        "}\n"
        "Do not add prose outside JSON. If unsure, choose defer.\n\n"
        + json.dumps(pack, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = {
        "candidate_source": str(candidates_path),
        "selected_candidates": len(picked),
        "candidate_count": len(candidates),
        "by_kind": dict(Counter(str(row.get("experience_kind") or "") for row in picked)),
        "pack_path": str(pack_path),
        "prompt_path": str(prompt_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_dir": str(out),
        "pack_path": str(pack_path),
        "prompt_path": str(prompt_path),
        "summary_path": str(summary_path),
        "selected_candidates": len(picked),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a review pack from execution experience candidates.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--pack-id", default="execution_experience_review_pack_v1")
    args = parser.parse_args()

    result = build_review_pack(
        candidates_path=args.candidates,
        output_dir=args.output_dir,
        limit=args.limit,
        pack_id=args.pack_id,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
