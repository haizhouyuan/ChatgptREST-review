#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "candidate_id",
    "atom_id",
    "lineage_family_id",
    "task_ref",
    "trace_id",
    "source",
    "episode_type",
    "experience_kind",
    "title",
    "summary",
    "groundedness",
    "time_sensitivity",
    "review_decision",
]


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _read_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def export_pack(
    *,
    candidates_path: str | Path,
    decisions_path: str | Path | None,
    output_dir: str | Path,
) -> dict[str, Any]:
    candidates = {str(row.get("candidate_id") or ""): row for row in _read_candidates(Path(candidates_path))}
    decisions = _read_tsv(Path(decisions_path) if decisions_path else None)

    accepted_rows: list[dict[str, Any]] = []
    for decision in decisions:
        if str(decision.get("review_decision") or "").strip() != "accept":
            continue
        candidate_id = str(decision.get("candidate_id") or "").strip()
        candidate = candidates.get(candidate_id, {})
        accepted_rows.append(
            {
                "candidate_id": candidate_id,
                "atom_id": str(decision.get("atom_id") or candidate.get("atom_id") or ""),
                "lineage_family_id": str(decision.get("lineage_family_id") or candidate.get("lineage_family_id") or ""),
                "task_ref": str(decision.get("task_ref") or candidate.get("task_ref") or ""),
                "trace_id": str(decision.get("trace_id") or candidate.get("trace_id") or ""),
                "source": str(decision.get("source") or candidate.get("source") or ""),
                "episode_type": str(decision.get("episode_type") or candidate.get("episode_type") or ""),
                "experience_kind": str(decision.get("experience_kind") or candidate.get("experience_kind") or ""),
                "title": str(decision.get("title") or candidate.get("title") or ""),
                "summary": str(decision.get("summary") or candidate.get("summary") or ""),
                "groundedness": str(decision.get("groundedness") or ""),
                "time_sensitivity": str(decision.get("time_sensitivity") or ""),
                "review_decision": "accept",
            }
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    accepted_json = out / "accepted_candidates.json"
    accepted_tsv = out / "accepted_candidates.tsv"
    accepted_json.write_text(json.dumps(accepted_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_tsv(accepted_tsv, accepted_rows)

    manifest = {
        "ok": True,
        "scope": {
            "review_plane_only": True,
            "default_runtime_cutover": False,
            "active_knowledge_promotion": False,
        },
        "source": {
            "candidates_path": str(candidates_path),
            "decisions_path": str(decisions_path) if decisions_path else "",
        },
        "counts": {
            "accepted_candidates": len(accepted_rows),
        },
        "checks": {
            "accept_only_decisions_ok": all(row["review_decision"] == "accept" for row in accepted_rows),
        },
        "files": {
            "accepted_candidates_json": str(accepted_json),
            "accepted_candidates_tsv": str(accepted_tsv),
        },
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    smoke_manifest = {
        "accepted_candidates": len(accepted_rows),
        "candidate_ids": [row["candidate_id"] for row in accepted_rows[:20]],
        "atom_ids": [row["atom_id"] for row in accepted_rows[:20]],
    }
    smoke_manifest_path = out / "smoke_manifest.json"
    smoke_manifest_path.write_text(json.dumps(smoke_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "output_dir": str(out),
        "manifest_path": str(manifest_path),
        "smoke_manifest_path": str(smoke_manifest_path),
        "accepted_candidates": len(accepted_rows),
        "files": [
            str(accepted_json),
            str(accepted_tsv),
            str(manifest_path),
            str(smoke_manifest_path),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a review-plane-only accepted execution experience pack.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decisions", default="")
    args = parser.parse_args()

    result = export_pack(
        candidates_path=args.candidates,
        decisions_path=Path(args.decisions) if args.decisions else None,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
