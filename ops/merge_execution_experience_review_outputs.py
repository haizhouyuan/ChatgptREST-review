#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from chatgptrest.evomap.knowledge.review_experiment import load_review_json
from ops.compose_execution_experience_review_decisions import ACCEPT_DECISIONS, FIELDNAMES
from ops.execution_experience_review_reviewer_identity import load_expected_reviewers, resolve_reviewer_name


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _extract_review_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload

    for key in ("response", "text", "output", "message", "result"):
        raw = payload.get(key) if isinstance(payload, dict) else None
        if not raw or not isinstance(raw, str):
            continue
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        try:
            nested = json.loads(text)
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
        except Exception:
            pass
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                nested, _ = decoder.raw_decode(text[idx:])
            except Exception:
                continue
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
    return payload if isinstance(payload, dict) else {"items": []}


def _normalize_decision(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "keep": "accept",
        "accept_candidate": "accept",
        "approve": "accept",
        "revise_candidate": "revise",
        "rewrite": "revise",
        "reject_candidate": "reject",
        "archive": "reject",
        "review_only": "defer",
        "hold": "defer",
    }
    return aliases.get(text, text or "defer")


def _normalize_groundedness(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    return "medium"


def _normalize_time_sensitivity(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"evergreen", "versioned", "ephemeral"}:
        return text
    return "versioned"


def _winner(counter: Counter[str], *, default: str) -> str:
    if not counter:
        return default
    ranked = counter.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return default
    return ranked[0][0]


def _pick_text(reviews: list[dict[str, Any]], field: str, fallback: str) -> str:
    values = Counter(
        str(review.get(field, "")).strip()
        for review in reviews
        if review.get("decision") in ACCEPT_DECISIONS and str(review.get(field, "")).strip()
    )
    if values:
        return _winner(values, default=fallback)
    return fallback


def merge_review_outputs(
    *,
    candidates_path: str | Path,
    review_json_paths: list[Path],
    output_path: str | Path,
    reviewer_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    candidate_rows = _read_candidates(Path(candidates_path))
    candidate_lookup = {str(row["candidate_id"]): row for row in candidate_rows}
    by_candidate: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    expected_reviewers = load_expected_reviewers(Path(reviewer_manifest_path) if reviewer_manifest_path else None)

    for path in review_json_paths:
        payload = _extract_review_payload(load_review_json(path))
        reviewer = resolve_reviewer_name(path, payload, expected_reviewers)
        for item in payload.get("items", []):
            candidate_id = str(item.get("candidate_id") or "").strip()
            if not candidate_id or candidate_id not in candidate_lookup:
                continue
            by_candidate[candidate_id].append(
                {
                    "reviewer": reviewer,
                    "decision": _normalize_decision(item.get("decision")),
                    "experience_kind": str(item.get("experience_kind") or "").strip().lower(),
                    "title": str(item.get("title") or "").strip(),
                    "summary": str(item.get("summary") or "").strip(),
                    "groundedness": _normalize_groundedness(item.get("groundedness")),
                    "time_sensitivity": _normalize_time_sensitivity(item.get("time_sensitivity")),
                    "note": str(item.get("note") or "").strip(),
                }
            )

    merged_rows: list[dict[str, Any]] = []
    for candidate_id, reviews in sorted(by_candidate.items()):
        candidate = candidate_lookup[candidate_id]
        decision = _winner(Counter(review["decision"] for review in reviews), default="defer")
        kind = _pick_text(reviews, "experience_kind", str(candidate.get("experience_kind") or ""))
        title = _pick_text(reviews, "title", str(candidate.get("title") or ""))
        summary = _pick_text(reviews, "summary", str(candidate.get("summary") or ""))
        groundedness = _winner(Counter(review["groundedness"] for review in reviews), default="medium")
        time_sensitivity = _winner(Counter(review["time_sensitivity"] for review in reviews), default="versioned")
        merged_rows.append(
            {
                "candidate_id": candidate_id,
                "atom_id": str(candidate.get("atom_id") or ""),
                "lineage_family_id": str(candidate.get("lineage_family_id") or ""),
                "lineage_status": str(candidate.get("lineage_status") or ""),
                "task_ref": str(candidate.get("task_ref") or ""),
                "trace_id": str(candidate.get("trace_id") or ""),
                "source": str(candidate.get("source") or ""),
                "episode_type": str(candidate.get("episode_type") or ""),
                "experience_kind": kind,
                "title": title,
                "summary": summary,
                "review_decision": decision,
                "groundedness": groundedness,
                "time_sensitivity": time_sensitivity,
                "reviewers": json.dumps(reviews, ensure_ascii=False),
            }
        )

    out = Path(output_path)
    _write_tsv(out, merged_rows, FIELDNAMES)
    summary = {
        "candidate_source": str(candidates_path),
        "review_outputs": [str(path) for path in review_json_paths],
        "reviewed_candidates": len(merged_rows),
        "by_decision": Counter(row["review_decision"] for row in merged_rows),
    }
    out.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def materialize_reviewed_candidates(
    *,
    candidates_path: str | Path,
    decisions_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    candidates = {str(row["candidate_id"]): row for row in _read_candidates(Path(candidates_path))}
    decisions = _read_tsv(Path(decisions_path))

    reviewed_rows: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    for decision in decisions:
        candidate = candidates.get(decision["candidate_id"], {})
        row = {
            "candidate_id": decision["candidate_id"],
            "atom_id": decision.get("atom_id", "") or str(candidate.get("atom_id") or ""),
            "lineage_family_id": decision.get("lineage_family_id", "") or str(candidate.get("lineage_family_id") or ""),
            "task_ref": decision.get("task_ref", "") or str(candidate.get("task_ref") or ""),
            "trace_id": decision.get("trace_id", "") or str(candidate.get("trace_id") or ""),
            "source": decision.get("source", "") or str(candidate.get("source") or ""),
            "episode_type": decision.get("episode_type", "") or str(candidate.get("episode_type") or ""),
            "experience_kind": decision.get("experience_kind", "") or str(candidate.get("experience_kind") or ""),
            "title": decision.get("title", "") or str(candidate.get("title") or ""),
            "summary": decision.get("summary", "") or str(candidate.get("summary") or ""),
            "review_decision": decision.get("review_decision", ""),
            "groundedness": decision.get("groundedness", ""),
            "time_sensitivity": decision.get("time_sensitivity", ""),
            "reviewers": decision.get("reviewers", ""),
            "review_notes": str(candidate.get("review_notes") or ""),
        }
        reviewed_rows.append(row)
        if row["review_decision"] in ACCEPT_DECISIONS:
            accepted_rows.append(row)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    reviewed_json = out / "reviewed_experience_candidates.json"
    accepted_json = out / "accepted_review_candidates.json"
    reviewed_json.write_text(json.dumps(reviewed_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    accepted_json.write_text(json.dumps(accepted_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
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
        "review_decision",
        "groundedness",
        "time_sensitivity",
        "reviewers",
        "review_notes",
    ]
    _write_tsv(out / "reviewed_experience_candidates.tsv", reviewed_rows, fieldnames)
    _write_tsv(out / "accepted_review_candidates.tsv", accepted_rows, fieldnames)
    decision_dir = out / "by_decision"
    decision_dir.mkdir(parents=True, exist_ok=True)
    decision_files: dict[str, dict[str, str]] = {}
    for decision in sorted({row["review_decision"] for row in reviewed_rows if row["review_decision"]}):
        decision_rows = [row for row in reviewed_rows if row["review_decision"] == decision]
        decision_json = decision_dir / f"{decision}.json"
        decision_tsv = decision_dir / f"{decision}.tsv"
        decision_json.write_text(json.dumps(decision_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_tsv(decision_tsv, decision_rows, fieldnames)
        decision_files[decision] = {
            "json_path": str(decision_json),
            "tsv_path": str(decision_tsv),
        }
    summary = {
        "candidate_source": str(candidates_path),
        "decisions_path": str(decisions_path),
        "reviewed_candidates": len(reviewed_rows),
        "accepted_candidates": len(accepted_rows),
        "by_decision": {
            decision: sum(1 for row in reviewed_rows if row["review_decision"] == decision)
            for decision in sorted({row["review_decision"] for row in reviewed_rows})
        },
        "decision_files": decision_files,
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = [
        str(reviewed_json),
        str(accepted_json),
        str(out / "reviewed_experience_candidates.tsv"),
        str(out / "accepted_review_candidates.tsv"),
        str(summary_path),
    ]
    for item in decision_files.values():
        files.extend([item["json_path"], item["tsv_path"]])
    return {
        "ok": True,
        "output_dir": str(out),
        "summary_path": str(summary_path),
        "reviewed_candidates": len(reviewed_rows),
        "accepted_candidates": len(accepted_rows),
        "files": files,
        "decision_files": decision_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge execution experience reviewer outputs and materialize reviewed candidates.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True, help="Delta TSV output path.")
    parser.add_argument("--review-json", action="append", default=[], help="Reviewer JSON output paths.")
    parser.add_argument("--reviewer-manifest", default="")
    parser.add_argument("--materialize-output-dir", default="")
    parser.add_argument("--materialize-decisions", default="")
    args = parser.parse_args()

    summary = merge_review_outputs(
        candidates_path=args.candidates,
        review_json_paths=[Path(path) for path in args.review_json],
        output_path=args.output,
        reviewer_manifest_path=Path(args.reviewer_manifest) if args.reviewer_manifest else None,
    )
    result: dict[str, Any] = {"ok": True, "summary": summary}
    if args.materialize_output_dir:
        materialize = materialize_reviewed_candidates(
            candidates_path=args.candidates,
            decisions_path=args.materialize_decisions or args.output,
            output_dir=args.materialize_output_dir,
        )
        result["materialize"] = materialize
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
